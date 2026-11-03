"""Synthetic evidence-pack and company-history toolkit."""

import copy
from decimal import Decimal
from pathlib import Path

from oab.cli import validate_tasks
from oab.evidence import (
    ANOMALY_KINDS,
    clean_example_pack,
    dirty_example_pack,
    generate_company_history,
    validate_evidence_budgets,
    validate_evidence_pack,
)
from oab.generate import write_task
from oab.workflow_families import DYNAMIC_FAMILIES


def test_clean_pack_is_deterministic_and_reconciles():
    first = clean_example_pack(42)
    second = clean_example_pack(42)
    different = clean_example_pack(43)

    assert first.files == second.files
    assert first.files != different.files
    assert validate_evidence_pack(first) == []
    assert validate_evidence_budgets(first) == []
    assert len(first.periods) >= 3
    assert [period.closed for period in first.periods[:-1]] == [True, True]
    assert first.periods[-1].closed is False
    assert first.master.customers
    assert first.master.suppliers
    assert first.master.employees
    assert first.master.items
    assert first.master.assets
    assert first.master.contracts
    assert first.anomalies == []
    assert "ledger.beancount" in first.files
    assert "documents/bank_statements.csv" in first.files
    assert "subledgers/accounts_receivable.csv" in first.files

    for balances in first.trial_balances.values():
        assert sum(balances.values(), Decimal("0")) == Decimal("0.00")


def test_dirty_pack_registers_every_conflict():
    pack = dirty_example_pack(7)
    assert validate_evidence_pack(pack) == []
    assert validate_evidence_budgets(pack) == []
    assert pack.anomalies
    assert {anomaly.kind for anomaly in pack.anomalies} <= set(ANOMALY_KINDS)
    doc_ids = {document.id for document in pack.documents}
    for anomaly in pack.anomalies:
        assert anomaly.determination
        assert anomaly.disposition
        assert anomaly.precedence
        assert anomaly.authoritative_ref in doc_ids
        assert set(anomaly.evidence_refs) <= doc_ids


def test_seed_sweep_clean_and_dirty_packs_validate():
    for seed in [0, 1, 7, 42, 99]:
        assert validate_evidence_pack(generate_company_history(seed, anomalies=())) == []
        assert validate_evidence_pack(dirty_example_pack(seed)) == []


def test_every_anomaly_kind_can_coexist_in_one_pack():
    pack = generate_company_history(12, anomalies=ANOMALY_KINDS)
    assert {anomaly.kind for anomaly in pack.anomalies} == set(ANOMALY_KINDS)
    assert validate_evidence_pack(pack) == []


def test_validator_rejects_orphans_unregistered_breaks_and_missing_precedence():
    pack = dirty_example_pack(11)

    orphan = copy.deepcopy(pack)
    orphan.documents[0].party_id = "syn-customer-missing"
    failures = validate_evidence_pack(orphan)
    assert any("unknown party" in failure for failure in failures)

    broken = copy.deepcopy(pack)
    broken.subledgers["accounts_receivable"][0].amount += Decimal("25.00")
    failures = validate_evidence_pack(broken)
    assert any("accounts receivable" in failure.lower() for failure in failures)

    unresolved = copy.deepcopy(pack)
    unresolved.anomalies[0].precedence = ""
    failures = validate_evidence_pack(unresolved)
    assert any("precedence" in failure for failure in failures)


def test_budget_validator_rejects_oversized_pack():
    pack = clean_example_pack(3)
    pack.files["documents/oversized.txt"] = "x" * 300_001
    failures = validate_evidence_budgets(pack)
    assert any("byte budget" in failure for failure in failures)


def test_validate_tasks_checks_workflow_evidence_files(tmp_path: Path):
    instance = DYNAMIC_FAMILIES["workflow-conformance-fixture"](5)
    task_dir = write_task(instance, tmp_path, track="dynamic")
    evidence = task_dir / "environment" / "app" / "documents" / "evidence.md"
    evidence.unlink()
    failures = validate_tasks(tmp_path)
    assert any("workflow evidence file missing" in failure for failure in failures)
