"""The /loopx Stop-hook guard lists open work in the skill's pick order."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _guard():
    spec = importlib.util.spec_from_file_location(
        "loopx_guard", ROOT / "scripts" / "loopx-guard.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_actionable_orders_milestones_and_notes_numerically(tmp_path, monkeypatch):
    queue = tmp_path / ".pm" / "w9"
    for name in ("m10", "m6", "m9", "done", "blocked"):
        (queue / name).mkdir(parents=True)
    for name in ("010.md", "004.md", "README.md"):
        (queue / name).write_text("x\n")
    guard = _guard()
    monkeypatch.setattr(guard, "project_dir", lambda: tmp_path)
    milestones, notes = guard.actionable("w9")
    assert milestones == ["m6", "m9", "m10"]
    assert notes == ["004.md", "010.md"]
