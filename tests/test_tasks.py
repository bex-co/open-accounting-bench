"""Committed Harbor tasks under tasks/ stay healthy and in sync."""

import json
import subprocess
import sys
from pathlib import Path

from oab.cli import validate_tasks

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "tasks"


def test_committed_tasks_validate():
    assert validate_tasks(TASKS) == []


def test_manifest_matches_task_dirs():
    manifest = json.loads((TASKS / "manifest.json").read_text())
    on_disk = sorted(p.name for p in TASKS.iterdir() if (p / "task.toml").exists())
    assert [entry["task_id"] for entry in manifest["tasks"]] == on_disk


def test_metric_aggregation(tmp_path: Path):
    rewards = tmp_path / "rewards.jsonl"
    rewards.write_text(
        '{"reward": 1, "operational_integrity": 1.0, "partial": 1.0}\n'
        '{"reward": 0, "operational_integrity": 0.0, "partial": 0.4}\n'
        "null\n"
    )
    out = tmp_path / "metrics.json"
    subprocess.run(
        [sys.executable, str(TASKS / "metric.py"), "-i", str(rewards), "-o", str(out)],
        check=True,
    )
    metrics = json.loads(out.read_text())
    assert metrics["n_tasks"] == 3
    assert metrics["verified_task_completion_rate"] == 1 / 3
    assert metrics["unauthorized_modification_rate"] == 1 - (1 / 3)
