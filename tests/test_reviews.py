"""Accounting-review registry: drift checks, lapse by content fingerprint."""

import json
import shutil
from pathlib import Path

from oab.cli import main
from oab.families import STABLE_SEEDS
from oab.reviews import (
    effective_status,
    fingerprint,
    load_registry,
    pending_family_ids,
    validate_registry,
)

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "tasks"
TO_REVIEW = (ROOT / "TO_REVIEW.md").read_text()


def test_committed_registry_is_valid():
    rows = load_registry(ROOT / "reviews.toml")
    assert validate_registry(rows, set(STABLE_SEEDS), TO_REVIEW) == []
    assert main(["reviews"]) == 0


def test_registry_drift_is_rejected():
    ids = {"a-family", "b-family", "c-family"}
    rows = [
        {"id": "a-family", "status": "reviewed", "reviewer": "R", "date": "2026-01-01"},
        {"id": "b-family", "status": "approved"},
        {"id": "b-family", "status": "pending"},
        {"id": "z-family", "status": "pending"},
    ]
    failures = "\n".join(validate_registry(rows, ids, ""))
    assert "a-family: reviewed rows need `fingerprint`" in failures
    assert "b-family: status must be one of" in failures
    assert "b-family: listed 2 times" in failures
    assert "z-family: no such Stable family" in failures
    assert "c-family: missing from reviews.toml" in failures


def test_reviewed_family_still_pending_in_to_review_is_rejected():
    to_review = "## Pending\n\n- 2026-11-01 — `a-family` changed.\n\n## Reviewed\n"
    assert pending_family_ids(to_review) == {"a-family"}
    rows = [
        {"id": "a-family", "status": "reviewed", "reviewer": "R", "date": "d", "fingerprint": "f"}
    ]
    assert validate_registry(rows, {"a-family"}, to_review) == [
        "a-family: reviewed in reviews.toml but still listed under Pending in TO_REVIEW.md"
    ]


def test_review_lapses_when_task_content_changes(tmp_path: Path):
    task = shutil.copytree(
        TASKS / "classify-operating-expense", tmp_path / "classify-operating-expense"
    )
    row = {"id": task.name, "status": "reviewed", "fingerprint": fingerprint(task)}
    assert effective_status(row, tmp_path) == "reviewed"

    # Version bumps and grader copies do not lapse a review ...
    expected_path = task / "tests" / "expected.json"
    expected = json.loads(expected_path.read_text())
    expected["generator_version"] = "9.9.9"
    expected_path.write_text(json.dumps(expected))
    (task / "tests" / "grader.py").write_text("# regenerated grader\n")
    assert effective_status(row, tmp_path) == "reviewed"

    # ... but a change to what the reviewer signed off does.
    policy = task / "environment" / "app" / "policy.md"
    policy.write_text(policy.read_text() + "\n- A new rule.\n")
    assert effective_status(row, tmp_path) == "lapsed"
    assert effective_status({"id": task.name, "status": "pending"}, tmp_path) == "pending"


def test_reviews_cli_fails_on_drift(tmp_path: Path):
    registry = tmp_path / "reviews.toml"
    registry.write_text('[[family]]\nid = "classify-operating-expense"\nstatus = "pending"\n')
    assert main(["reviews", "--registry", str(registry)]) == 1


def test_manifest_carries_effective_review_status():
    manifest = json.loads((TASKS / "manifest.json").read_text())
    by_id = {row["id"]: row for row in load_registry(ROOT / "reviews.toml")}
    for entry in manifest["tasks"]:
        assert entry["review"] == effective_status(by_id[entry["task_id"]], TASKS), entry
    schema = json.loads((TASKS / "manifest.schema.json").read_text())
    item = schema["properties"]["tasks"]["items"]
    assert "review" in item["required"]
    assert item["properties"]["review"]["enum"] == ["pending", "reviewed", "lapsed"]


def test_generated_manifest_marks_changed_reviewed_task_lapsed(tmp_path: Path):
    from oab.generate import write_dataset_files

    tasks_root = tmp_path / "tasks"
    task = shutil.copytree(
        TASKS / "classify-operating-expense", tasks_root / "classify-operating-expense"
    )
    (tmp_path / "reviews.toml").write_text(
        f'[[family]]\nid = "{task.name}"\nstatus = "reviewed"\nreviewer = "R"\n'
        f'date = "2026-01-01"\nfingerprint = "{fingerprint(task)}"\n'
    )
    assert write_dataset_files(tasks_root, [task])["tasks"][0]["review"] == "reviewed"
    (task / "instruction.md").write_text("Changed instruction.\n")
    assert write_dataset_files(tasks_root, [task])["tasks"][0]["review"] == "lapsed"
