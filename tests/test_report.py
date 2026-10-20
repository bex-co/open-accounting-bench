"""oab report: majority vote, grouping, bands, cost, confidence bins."""

import json
from pathlib import Path

from oab.report import aggregate_tasks, band_for, load_runs, write_report

MANIFEST = {
    "tasks": [
        {
            "task_id": "mc-x",
            "family": "f",
            "seed": 1,
            "generator_version": "0.2.0",
            "track": "stable",
            "category": "financial-accounting",
            "framework": "core",
            "level": "university",
            "format": "multiple-choice",
        },
        {
            "task_id": "je-y",
            "family": "f",
            "seed": 2,
            "generator_version": "0.2.0",
            "track": "stable",
            "category": "financial-accounting",
            "framework": "ifrs",
            "level": "professional",
            "format": "journal-entry",
        },
    ]
}


def _trial(job: Path, name: str, task_id: str, reward: dict, answer=None, cost=None):
    trial = job / name
    (trial / "verifier").mkdir(parents=True)
    (trial / "verifier" / "reward.json").write_text(json.dumps(reward))
    agent_result = {"n_input_tokens": 1000, "n_output_tokens": 500, "cost_usd": cost}
    (trial / "result.json").write_text(
        json.dumps(
            {
                "task_name": f"open-accounting-bench/{task_id}",
                "task_checksum": "abc",
                "config": {"agent": {"name": "test-agent", "model_name": "m/test"}},
                "agent_result": agent_result,
            }
        )
    )
    if answer is not None:
        artifact = trial / "artifacts" / "app"
        artifact.mkdir(parents=True)
        (artifact / "answer.json").write_text(json.dumps(answer))
    return trial


def make_job(tmp_path: Path) -> Path:
    job = tmp_path / "job"
    job.mkdir()
    (job / "result.json").write_text(json.dumps({"started_at": "2026-01-01T00:00:00"}))
    _trial(job, "mc-x__a", "mc-x", {"reward": 1, "confidence": 95}, {"final_answer": ["A"]})
    _trial(job, "mc-x__b", "mc-x", {"reward": 1, "confidence": 90}, {"final_answer": ["A"]})
    _trial(job, "mc-x__c", "mc-x", {"reward": 0, "confidence": 40}, {"final_answer": ["B"]})
    _trial(job, "je-y__a", "je-y", {"reward": 0}, cost=0.02)
    return job


def test_majority_vote_and_grouping(tmp_path: Path):
    rows = load_runs(make_job(tmp_path), MANIFEST)
    tasks = aggregate_tasks(rows)
    assert tasks["mc-x"]["score"] == 1.0  # modal answer A was rewarded
    assert tasks["mc-x"]["agreement"] == 2 / 3
    assert tasks["je-y"]["score"] == 0.0


def test_bands():
    assert band_for(95).startswith("Excellent")
    assert band_for(90).startswith("Excellent")
    assert band_for(75).startswith("Strong")
    assert band_for(49).startswith("Poor")


def test_write_report_outputs(tmp_path: Path):
    job = make_job(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(MANIFEST))
    prices = {
        "as_of": "2026-01-01",
        "models": {"m/test": {"input_per_1m": 1.0, "output_per_1m": 2.0}},
    }
    runs_path, board_path = write_report(job, manifest, prices=prices, out_dir=tmp_path / "out")
    rows = [json.loads(line) for line in runs_path.read_text().splitlines()]
    assert len(rows) == 4
    # 1000 in @1 + 500 out @2 per 1M = 0.002 for priced trials.
    mc_row = next(r for r in rows if r["trial"] == "mc-x__a")
    assert mc_row["cost_usd"] == 0.002
    board = board_path.read_text()
    assert "Overall verified completion: **50.0%**" in board
    assert "## By framework" in board
    assert "## Confidence calibration" in board
