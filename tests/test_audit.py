"""Mutation audit: operators are deterministic, declared, and applicable."""

import json
from pathlib import Path

import pytest

from oab.audit import (
    ANSWER_OPERATORS,
    FALSE_ACCEPT,
    FALSE_REJECT,
    LEDGER_OPERATORS,
    load_case,
    probes,
    task_dirs,
)

TASKS = Path(__file__).resolve().parents[1] / "tasks"
CASES = [case for d in task_dirs(TASKS) if (case := load_case(d)) is not None]


def test_every_probe_declares_kind_and_layer():
    for case in CASES:
        for probe in probes(case):
            assert probe.kind in {FALSE_ACCEPT, FALSE_REJECT}
            assert (probe.layer is not None) == (probe.kind == FALSE_ACCEPT), probe.operator
            assert probe.artifact != case.oracle, probe.operator


def test_probes_are_deterministic():
    for case in CASES[::25]:
        assert probes(case) == probes(case)


@pytest.mark.parametrize(
    "operator", LEDGER_OPERATORS + ANSWER_OPERATORS, ids=lambda op: op.operator
)
def test_every_operator_applies_to_some_stable_task(operator):
    assert any(operator(case) is not None for case in CASES), operator.operator


def test_audit_cli_writes_identical_reports(tmp_path):
    from oab.cli import main

    first, second = tmp_path / "a", tmp_path / "b"
    main(["audit", "--tasks", str(TASKS), "--sample", "40", "--out", str(first)])
    main(["audit", "--tasks", str(TASKS), "--sample", "40", "--out", str(second)])
    for name in ("audit.json", "audit.md"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_summary_counts_misjudgements_by_kind():
    from oab.audit import Outcome, summarize

    outcomes = [
        Outcome("t", "a", FALSE_ACCEPT, 1, "semantic_accuracy", ()),
        Outcome("t", "b", FALSE_ACCEPT, 0, "semantic_accuracy", ("semantic_accuracy",)),
        Outcome("t", "c", FALSE_REJECT, 0, None, ("structural_validity",)),
        Outcome("t", "d", FALSE_ACCEPT, 0, "semantic_accuracy", ("operational_integrity",)),
    ]
    summary = summarize(outcomes, [])
    assert (summary["false_accepts"], summary["false_accept_probes"]) == (1, 3)
    assert (summary["false_rejects"], summary["false_reject_probes"]) == (1, 1)
    assert summary["tasks"]["t"] == {"probes": 4, "false_accepts": 1, "false_rejects": 1}
    assert summary["layer_mismatches"] == ["t:d"]


def test_audit_fails_when_the_grader_regresses(monkeypatch, tmp_path):
    """CI gate: a grader that accepts everything must make `oab audit` exit 1."""
    import oab.audit as audit
    from oab._verifier_core import LayerResult, Report
    from oab.cli import main

    def accept_everything(*_args):
        return Report(layers={"structural_validity": LayerResult(1.0, True)})

    monkeypatch.setattr(audit, "verify", accept_everything)
    assert main(["audit", "--tasks", str(TASKS), "--sample", "40"]) == 1
    assert main(["audit", "--tasks", str(TASKS), "--sample", "40", "--out", str(tmp_path)]) == 1
    summary = json.loads((tmp_path / "audit.json").read_text())
    assert summary["false_accepts"] > 0


def test_full_audit_has_no_misjudgements_or_layer_mismatches():
    from oab.audit import run_audit, summarize

    summary = summarize(*run_audit(TASKS))
    assert summary["false_accepts"] == 0, summary["operators"]
    assert summary["false_rejects"] == 0, summary["operators"]
    assert summary["layer_mismatches"] == []
    assert summary["tasks_skipped"] == []
