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
