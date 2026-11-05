"""Mutation audit: operators are deterministic, declared, and applicable."""

from pathlib import Path

import pytest

from oab.audit import (
    ANSWER_OPERATORS,
    FALSE_ACCEPT,
    FALSE_REJECT,
    LEDGER_OPERATORS,
    load_case,
    probes,
)

TASKS = Path(__file__).resolve().parents[1] / "tasks"
CASES = [
    case
    for d in sorted(TASKS.iterdir())
    if (d / "task.toml").exists() and (case := load_case(d)) is not None
]


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
        Outcome("t", "a", FALSE_ACCEPT, 0, 1, "semantic_accuracy", ()),
        Outcome("t", "b", FALSE_ACCEPT, 0, 0, "semantic_accuracy", ("semantic_accuracy",)),
        Outcome("t", "c", FALSE_REJECT, 1, 0, None, ("structural_validity",)),
    ]
    summary = summarize(outcomes, [])
    assert (summary["false_accepts"], summary["false_accept_probes"]) == (1, 2)
    assert (summary["false_rejects"], summary["false_reject_probes"]) == (1, 1)
    assert summary["tasks"]["t"] == {"probes": 3, "false_accepts": 1, "false_rejects": 1}
