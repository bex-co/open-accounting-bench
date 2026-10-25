"""Generators are seed-deterministic and seed-sensitive."""

from pathlib import Path

from oab.families import FAMILIES
from oab.generate import task_digest, write_task


def test_same_seed_same_instance():
    for fn in FAMILIES.values():
        first, second = fn(42), fn(42)
        assert first.app_files == second.app_files
        assert first.expected == second.expected
        assert first.solution_ledger == second.solution_ledger


def test_different_seeds_differ():
    for fn in FAMILIES.values():
        assert fn(1).expected != fn(2).expected


def test_written_task_is_reproducible(tmp_path: Path):
    instance = FAMILIES["bank-recon-missing-fee"](102)
    first = write_task(instance, tmp_path / "a")
    digest_a = task_digest(first)
    second = write_task(instance, tmp_path / "b")
    assert task_digest(second) == digest_a


def test_ppe_disposal_proceeds_are_positive():
    """Regression: a large loss offset on a small carrying amount gave negative
    sale proceeds (e.g. seed 6589)."""
    from decimal import Decimal

    for seed in [6589, *range(1, 3000)]:
        deltas = FAMILIES["ppe-disposal"](seed).expected["expected_deltas"]
        assert Decimal(deltas["Assets:Bank:Checking"]) > 0, seed


def test_suspense_memo_states_balance_side_without_sign():
    for seed in range(1, 200):
        memo = FAMILIES["suspense-clearance"](seed).app_files["documents/controller_memo.md"]
        assert "USD -" not in memo, seed
        assert "credit balance" in memo or "debit balance" in memo, seed
