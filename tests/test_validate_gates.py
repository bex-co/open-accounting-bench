"""validate_tasks must catch broken task metadata, not just pass clean ones."""

import shutil
from pathlib import Path

from oab.cli import validate_tasks

ROOT = Path(__file__).resolve().parent.parent


def _copy_task(tmp_path: Path, task_id: str) -> Path:
    dest = tmp_path / task_id
    shutil.copytree(ROOT / "tasks" / task_id, dest)
    return dest


def test_validate_catches_unknown_taxonomy_value(tmp_path: Path):
    task = _copy_task(tmp_path, "classify-operating-expense")
    toml = task / "task.toml"
    toml.write_text(toml.read_text().replace('framework = "core"', 'framework = "martian"'))
    failures = validate_tasks(tmp_path)
    assert any("metadata.framework" in f for f in failures)


def test_validate_catches_instruction_without_artifact_path(tmp_path: Path):
    task = _copy_task(tmp_path, "mc-capitalization-treatment")
    instruction = task / "instruction.md"
    instruction.write_text(instruction.read_text().replace("/app/answer.json", "answer file"))
    failures = validate_tasks(tmp_path)
    assert any("instruction must name" in f for f in failures)


def test_validate_catches_empty_multiple_choice_gold(tmp_path: Path):
    task = _copy_task(tmp_path, "mc-capitalization-treatment")
    expected = task / "tests" / "expected.json"
    expected.write_text(expected.read_text().replace('"gold": [', '"gold": [], "unused": ['))
    failures = validate_tasks(tmp_path)
    assert any("gold" in f for f in failures)


def test_validate_catches_malformed_standard_reference(tmp_path: Path):
    task = _copy_task(tmp_path, "ifrs-capitalize-borrowing-costs")
    toml = task / "task.toml"
    toml.write_text(toml.read_text().replace('standards = ["ias:23"]', 'standards = ["IAS 23"]'))
    failures = validate_tasks(tmp_path)
    assert any("metadata.standards" in f for f in failures)
