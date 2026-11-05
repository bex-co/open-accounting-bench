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
