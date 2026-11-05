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


def _trial(
    job: Path,
    name: str,
    task_id: str,
    reward: dict,
    answer=None,
    cost=None,
    verifier_report: dict | None = None,
):
    trial = job / name
    (trial / "verifier").mkdir(parents=True)
    (trial / "verifier" / "reward.json").write_text(json.dumps(reward))
    if verifier_report is not None:
        (trial / "verifier" / "report.json").write_text(json.dumps(verifier_report))
    agent_result = {"n_input_tokens": 1000, "n_output_tokens": 500, "cost_usd": cost}
    (trial / "result.json").write_text(
        json.dumps(
            {
                "task_name": f"open-accounting-bench/{task_id}",
                "task_checksum": "abc",
                "config": {"agent": {"name": "test-agent", "model_name": "m/test"}},
                "agent_result": agent_result,
                "started_at": "2026-01-01T00:00:00Z",
                "finished_at": "2026-01-01T00:02:30Z",
            }
        )
    )
    if answer is not None:
        artifact = trial / "artifacts" / "app"
        artifact.mkdir(parents=True)
        (artifact / "answer.json").write_text(json.dumps(answer))
    return trial


def _job(tmp_path: Path) -> Path:
    job = tmp_path / "job"
    job.mkdir()
    (job / "result.json").write_text(json.dumps({"started_at": "2026-01-01T00:00:00"}))
    return job


def make_job(tmp_path: Path) -> Path:
    job = _job(tmp_path)
    _trial(job, "mc-x__a", "mc-x", {"reward": 1, "confidence": 95}, {"final_answer": ["A"]})
    _trial(job, "mc-x__b", "mc-x", {"reward": 1, "confidence": 90}, {"final_answer": ["A"]})
    _trial(job, "mc-x__c", "mc-x", {"reward": 0, "confidence": 40}, {"final_answer": ["B"]})
    _trial(job, "je-y__a", "je-y", {"reward": 0}, cost=0.02)
    # Infrastructure error: exception, no reward file. Must not dilute.
    err = job / "mc-x__err"
    err.mkdir(exist_ok=True)
    (err / "result.json").write_text(
        json.dumps(
            {
                "task_name": "open-accounting-bench/mc-x",
                "config": {"agent": {"name": "test-agent", "model_name": "m/test"}},
                "agent_result": {},
                "exception_info": {"exception_type": "NetworkConnectionError"},
            }
        )
    )
    (err / "verifier").mkdir(exist_ok=True)
    return job


def test_majority_vote_and_grouping(tmp_path: Path):
    rows = load_runs(make_job(tmp_path), MANIFEST)
    errored = [r for r in rows if not r["graded"]]
    assert len(errored) == 1
    assert errored[0]["exception"] == "NetworkConnectionError"
    tasks = aggregate_tasks(rows)
    assert tasks["mc-x"]["score"] == 1.0  # modal answer A was rewarded
    assert tasks["mc-x"]["agreement"] == 2 / 3
    assert tasks["mc-x"]["n_trials"] == 3
    assert tasks["mc-x"]["n_errored"] == 1
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
    assert len(rows) == 5
    # 1000 in @1 + 500 out @2 per 1M = 0.002 for priced trials.
    mc_row = next(r for r in rows if r["trial"] == "mc-x__a")
    assert mc_row["cost_usd"] == 0.002
    board = board_path.read_text()
    assert "Overall verified completion: **50.0%**" in board
    assert "Excluded as infrastructure errors: 1 trial(s)" in board
    assert "## By framework" in board
    assert "## Confidence calibration" in board


def test_verifier_report_aggregates_clusters_checks_and_wall_time(tmp_path: Path):
    manifest = {
        "tasks": [
            {
                "task_id": "wf-z",
                "family": "wf",
                "seed": 7,
                "generator_version": "0.7.0",
                "track": "dynamic",
                "category": "financial-accounting",
                "framework": "core",
                "level": "professional",
                "format": "workflow",
            }
        ]
    }
    job = _job(tmp_path)
    reward = {
        "reward": 0,
        "rubric_completion": 0.5,
        "workflow_check_completion": 0.5,
        "parse_failure": 0.0,
    }

    def verifier_report(*, revenue: bool, cluster_score: float) -> dict:
        return {
            "details": {
                "workflow": {
                    "clusters": {"revenue-cutoff": cluster_score, "bank": 1.0},
                    "checks": [
                        {
                            "id": "revenue-primary",
                            "cluster": "revenue-cutoff",
                            "passed": revenue,
                            "actual": "should-not-be-copied",
                        },
                        {"id": "bank-primary", "cluster": "bank", "passed": True},
                    ],
                }
            }
        }

    _trial(
        job,
        "wf-z__a",
        "wf-z",
        reward,
        verifier_report=verifier_report(revenue=True, cluster_score=1.0),
    )
    _trial(
        job,
        "wf-z__b",
        "wf-z",
        {**reward, "rubric_completion": 0.25, "workflow_check_completion": 0.25},
        verifier_report=verifier_report(revenue=False, cluster_score=0.0),
    )
    err = job / "wf-z__err"
    err.mkdir()
    (err / "result.json").write_text(
        json.dumps(
            {
                "task_name": "open-accounting-bench/wf-z",
                "config": {"agent": {"name": "test-agent", "model_name": "m/test"}},
                "agent_result": {},
                "exception_info": {"exception_type": "InstallError"},
            }
        )
    )

    rows = load_runs(job, manifest)
    graded = [row for row in rows if row["graded"]]
    assert graded[0]["wall_seconds"] == 150.0
    assert graded[0]["workflow_clusters"] == {"bank": 1.0, "revenue-cutoff": 1.0}
    assert graded[0]["workflow_checks"] == [
        {"id": "revenue-primary", "cluster": "revenue-cutoff", "passed": True},
        {"id": "bank-primary", "cluster": "bank", "passed": True},
    ]
    task = aggregate_tasks(rows)["wf-z"]
    assert task["n_trials"] == 2
    assert task["n_errored"] == 1
    assert task["rubric_min"] == 0.25
    assert task["rubric_max"] == 0.5
    assert task["mean_wall_seconds"] == 150.0
    assert task["workflow_cluster_means"] == {"bank": 1.0, "revenue-cutoff": 0.5}
    assert task["workflow_check_rates"]["revenue-primary"] == {
        "cluster": "revenue-cutoff",
        "passed": 1,
        "total": 2,
        "rate": 0.5,
    }

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    _, board_path = write_report(job, manifest_path, out_dir=tmp_path / "out")
    board = board_path.read_text()
    assert "## Workflow issue clusters" in board
    assert "| wf-z | revenue-cutoff | 50.0% |" in board
    assert "## Workflow checks" in board
    assert "| wf-z | revenue-primary | revenue-cutoff | 1/2 | 50.0% |" in board
    assert "150.0" in board
    assert "should-not-be-copied" not in board


def test_over_action_rate_from_no_action_trials(tmp_path: Path):
    job = _job(tmp_path)
    _trial(job, "close__a", "month-end-close-workflow", {"reward": 1, "over_action": 0.0})
    _trial(job, "close__b", "month-end-close-workflow", {"reward": 0, "over_action": 1.0})
    _trial(job, "close__c", "month-end-close-workflow", {"reward": 1, "over_action": 0.0})
    _trial(job, "je-y__a", "je-y", {"reward": 1})
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(MANIFEST))
    runs_path, board_path = write_report(job, manifest, out_dir=tmp_path / "out")
    rows = {
        json.loads(line)["trial"]: json.loads(line) for line in runs_path.read_text().splitlines()
    }
    assert rows["close__b"]["over_action"] == 1.0
    assert rows["je-y__a"]["over_action"] is None
    assert (
        "Over-action rate (no-action controls): **33.3%** (1 of 3 trials" in board_path.read_text()
    )


def test_pass_at_k_and_pass_hat_k_estimators():
    from oab.report import pass_at_k, pass_hat_k

    # all pass / all fail
    assert pass_at_k(3, 3, 3) == 1.0 and pass_hat_k(3, 3, 3) == 1.0
    assert pass_at_k(3, 0, 3) == 0.0 and pass_hat_k(3, 0, 3) == 0.0
    # n=4, c=2: pass@2 = 1 - C(2,2)/C(4,2) = 5/6; pass^2 = C(2,2)/C(4,2) = 1/6
    assert pass_at_k(4, 2, 2) == 5 / 6
    assert pass_hat_k(4, 2, 2) == 1 / 6
    # k = 1 reduces to the mean success rate for both
    assert pass_at_k(5, 2, 1) == pass_hat_k(5, 2, 1) == 2 / 5
    # fewer attempts than k: not available, never 0
    assert pass_at_k(2, 2, 3) is None and pass_hat_k(2, 2, 3) is None


def test_reliability_columns_in_leaderboard(tmp_path: Path):
    job = _job(tmp_path)
    for suffix, reward in zip("abc", (1, 1, 0), strict=True):
        _trial(job, f"je-y__{suffix}", "je-y", {"reward": reward})
    for suffix in "abc":
        _trial(job, f"mc-x__{suffix}", "mc-x", {"reward": 1}, {"final_answer": ["A"]})
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(MANIFEST))

    _runs, board_path = write_report(job, manifest, out_dir=tmp_path / "out")
    board = board_path.read_text()
    # Default k = fewest graded attempts on any task (3 here).
    assert "Reliability (k=3): pass@3 **100.0%**, pass^3 **50.0%**" in board
    assert "| je-y | journal-entry | 3 | 0 | 66.7% | - | 100.0% | 0.0% |" in board
    assert "| mc-x | multiple-choice | 3 | 0 | 100.0% | 1.00 | 100.0% | 100.0% |" in board

    _runs, board_path = write_report(job, manifest, out_dir=tmp_path / "k4", k=4)
    board = board_path.read_text()
    assert "Reliability (k=4): not available (no task has 4 graded attempts)" in board
    assert "| je-y | journal-entry | 3 | 0 | 66.7% | - | n/a | n/a |" in board


def test_report_cli_passes_k(tmp_path: Path):
    from oab.cli import main

    job = make_job(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(MANIFEST))
    out = tmp_path / "out"
    assert (
        main(
            [
                "report",
                "--job",
                str(job),
                "--manifest",
                str(manifest),
                "--out",
                str(out),
                "--k",
                "2",
            ]
        )
        == 0
    )
    assert "Reliability (k=2)" in (out / "leaderboard.md").read_text()


def test_reliability_ignores_errored_trials_and_groups_by_family(tmp_path: Path):
    job = make_job(tmp_path)  # mc-x: 3 graded (1, 1, 0) + 1 infrastructure error
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(MANIFEST))
    tasks = aggregate_tasks(load_runs(job, MANIFEST), k=3)
    assert tasks["mc-x"]["n_trials"] == 3  # the errored trial is not an attempt
    assert tasks["mc-x"]["pass_hat_k"] == 0.0
    assert tasks["mc-x"]["pass_at_k"] == 1.0
    assert tasks["je-y"]["pass_at_k"] is None  # one attempt < k
    _runs, board_path = write_report(job, manifest, out_dir=tmp_path / "out", k=3)
    board = board_path.read_text()
    assert "## By family" in board
    assert "| f | 2 | 50.0% | 100.0% | 0.0% |" in board


def test_account_amount_diagnostics_by_family(tmp_path: Path):
    job = _job(tmp_path)

    def report(expected: dict, extra: list) -> dict:
        return {"layers": {}, "details": {"diagnostics": {"expected": expected, "extra": extra}}}

    _trial(
        job,
        "je-y__a",
        "je-y",
        {"reward": 1},
        verifier_report=report({"Expenses:A": "correct", "Assets:Bank": "correct"}, []),
    )
    _trial(
        job,
        "je-y__b",
        "je-y",
        {"reward": 0},
        verifier_report=report({"Expenses:A": "wrong-account", "Assets:Bank": "correct"}, []),
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(MANIFEST))
    runs_path, board_path = write_report(job, manifest, out_dir=tmp_path / "out")
    rows = [json.loads(line) for line in runs_path.read_text().splitlines()]
    wrong = next(r for r in rows if r["trial"] == "je-y__b")
    # Counts only: expected account names are held-out verifier data.
    assert wrong["diagnostics"] == {
        "correct": 1,
        "wrong-amount": 0,
        "wrong-account": 1,
        "missing": 0,
        "extra": 0,
    }
    assert "Expenses:A" not in runs_path.read_text()
    board = board_path.read_text()
    assert "## Account-vs-amount diagnostics" in board
    assert "| f | 2 | 4 | 75.0% | 25.0% | 0.0% | 0.0% | 0 |" in board


def test_reviewed_share_and_reviewed_only(tmp_path: Path):
    manifest_data = json.loads(json.dumps(MANIFEST))
    manifest_data["tasks"][0]["review"] = "reviewed"  # mc-x
    manifest_data["tasks"][1]["review"] = "lapsed"  # je-y
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(manifest_data))
    job = make_job(tmp_path)

    runs_path, board_path = write_report(job, manifest, out_dir=tmp_path / "all")
    board = board_path.read_text()
    assert "Accounting review: 1 of 2 graded task(s) (50.0%) reviewed" in board
    rows = [json.loads(line) for line in runs_path.read_text().splitlines()]
    assert {r["task_id"]: r["review"] for r in rows} == {"mc-x": "reviewed", "je-y": "lapsed"}

    _runs, board_path = write_report(job, manifest, out_dir=tmp_path / "rev", reviewed_only=True)
    board = board_path.read_text()
    assert "| mc-x |" in board
    assert "| je-y |" not in board
    assert "restricted to reviewed tasks (--reviewed-only)" in board
