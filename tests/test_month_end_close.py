"""Month-end close professional workflow pilot."""

import csv
import io
import json
import re
from decimal import Decimal
from pathlib import Path

from oab.cli import validate_tasks
from oab.generate import write_task
from oab.verify import grade_workflow
from oab.workflow import DEFAULT_WORKFLOW_ARTIFACT, validate_workflow_spec
from oab.workflow_families import CLOSE_CLUSTERS, DYNAMIC_FAMILIES

FAMILY = "month-end-close-workflow"
WORKFLOW_PATH = DEFAULT_WORKFLOW_ARTIFACT
CLUSTERS = set(CLOSE_CLUSTERS)


def _instance(seed: int = 42):
    return DYNAMIC_FAMILIES[FAMILY](seed)


def _grade(instance, ledger=None, workflow=None):
    return grade_workflow(
        instance.initial_ledger,
        instance.solution_ledger if ledger is None else ledger,
        instance.expected,
        {WORKFLOW_PATH: instance.solution_files["workflow.json"] if workflow is None else workflow},
    )


def _added(instance) -> str:
    return instance.solution_ledger[len(instance.initial_ledger) :]


def _blocks(instance) -> list[str]:
    return [block.strip() for block in _added(instance).split("\n\n") if block.strip()]


def _workflow_details(report) -> dict:
    return report.to_report_json()["details"]["workflow"]


def test_close_pilot_shape_and_level():
    instance = _instance()
    assert instance.format == "workflow"
    assert instance.level == "professional"
    assert instance.task_id == FAMILY
    spec = instance.expected["workflow"]
    assert validate_workflow_spec(spec) == []
    assert 40 <= len(spec["checks"]) <= 70
    clusters = {item["cluster"] for item in spec["determinations"]}
    assert len(clusters & CLUSTERS) >= 7
    for path in [
        "ledger.beancount",
        "policy.md",
        "documents/close_evidence.md",
        "documents/close_ar_aging.csv",
        "documents/close_inventory_count.csv",
        "subledgers/accounts_receivable.csv",
        "subledgers/accounts_payable.csv",
        "trial_balances.csv",
    ]:
        assert path in instance.app_files
    policy = instance.app_files["policy.md"].lower()
    assert "materiality" in policy
    assert "signed" in policy
    assert "journal entry" not in policy


def test_close_contract_discloses_codes_and_keeps_all_clusters_in_scope():
    for seed in range(16):
        instance = _instance(seed)
        spec = instance.expected["workflow"]
        clusters = {item["cluster"] for item in spec["determinations"]}
        assert CLUSTERS <= clusters, seed
        policy = instance.app_files["policy.md"]
        expected_codes = {
            check["expected"] for check in spec["checks"] if check["type"] == "evidence_disposition"
        }
        assert expected_codes <= set(re.findall(r"`([^`]+)`", policy)), seed
        assert "utility service" in instance.app_files["documents/close_evidence.md"].lower()


def test_close_tuned_contract_links_nsf_and_false_alarms():
    for seed in range(8):
        instance = _instance(seed)
        policy = " ".join(instance.app_files["policy.md"].split())
        assert "each aging row's `loss_rate`" in policy
        assert "annual rate / 12" in policy
        assert "even if it is below USD 100" in policy
        for path in (
            "documents/close_supplier_invoices.csv",
            "documents/close_debt_schedules.csv",
            "documents/close_equipment_invoices.csv",
            "documents/close_rent_agreement.csv",
            "documents/close_bank_advice.csv",
        ):
            assert path in instance.app_files, (seed, path)
        assert len(instance.expected["workflow"]["checks"]) >= 63

        aging = list(
            csv.DictReader(io.StringIO(instance.app_files["documents/close_ar_aging.csv"]))
        )
        assert any(row["record_id"] == "close-nsf-check" for row in aging)
        expected_allowance = sum(
            (Decimal(row["amount"]) * Decimal(row["loss_rate"])).quantize(Decimal("0.01"))
            for row in aging
            if row["bucket"] != "unshipped"
        )
        workflow = json.loads(instance.solution_files["workflow.json"])
        assert Decimal(workflow["trial_balance"]["allowance_for_credit_losses"]) == (
            -expected_allowance
        )
        assert workflow["evidence"]["february-utility-service"] == "exclude-next-period"
        assert workflow["evidence"]["duplicate-utility-invoice"] == "ignore-duplicate-copy"
        assert workflow["evidence"]["capital-equipment-improvement"] == "keep-capitalized"
        assert workflow["evidence"]["stale-debt-schedule"] == "use-revised-schedule"
        assert "Capital improvement" in instance.initial_ledger
        assert "Depreciation on capitalized" in instance.initial_ledger


def test_close_oracle_noop_and_seed_sweep():
    for seed in range(25):
        instance = _instance(seed)
        oracle = _grade(instance)
        assert oracle.reward == 1, (seed, oracle.to_report_json())
        assert oracle.to_reward_json()["rubric_completion"] == 1.0
        nop = _grade(instance, ledger=instance.initial_ledger)
        assert nop.reward == 0
        assert nop.to_reward_json()["rubric_completion"] < 0.5
        workflow = json.loads(instance.solution_files["workflow.json"])
        assert Decimal(workflow["trial_balance"]["bank"]) > 0
        assert Decimal(workflow["trial_balance"]["inventory"]) >= 0
        clusters = {item["cluster"] for item in instance.expected["workflow"]["determinations"]}
        assert len(clusters & CLUSTERS) == 8


def test_close_issue_omission_mutants_lose_their_clusters():
    instance = _instance(7)
    blocks = _blocks(instance)
    assert len(blocks) >= 8
    details = _workflow_details(_grade(instance))
    determination_clusters = {
        item["id"]: details["determinations"][item["id"]]["cluster"]
        for item in instance.expected["workflow"]["determinations"]
    }
    issue_determinations = [
        determination_id
        for determination_id, cluster in determination_clusters.items()
        if cluster in CLUSTERS
    ]
    assert len(issue_determinations) == 8

    # Omitting one adjustment block at a time must lose at least one
    # determination; across the sweep every issue cluster is lost once.
    lost_clusters = set()
    for index in range(7):
        ledger = instance.initial_ledger + "\n\n".join(
            block for other, block in enumerate(blocks) if other != index
        )
        report = _grade(instance, ledger=ledger)
        assert report.reward == 0
        for detail in _workflow_details(report)["determinations"].values():
            if not detail["passed"] and detail["cluster"] in CLUSTERS:
                lost_clusters.add(detail["cluster"])
    assert len(lost_clusters) >= 5


def test_close_duplicate_wrong_period_and_wrong_disposition_mutants():
    instance = _instance(11)
    blocks = _blocks(instance)

    duplicate = instance.solution_ledger + "\n" + blocks[0] + "\n"
    assert _grade(instance, ledger=duplicate).reward == 0

    wrong_period_block = re.sub(r"^2026-01-31", "2026-02-01", blocks[0], count=1)
    wrong_period = instance.initial_ledger + "\n\n".join([wrong_period_block, *blocks[1:]])
    report = _grade(instance, ledger=wrong_period)
    assert report.reward == 0
    assert any(
        not check["passed"] and check["type"] == "cutoff_no_transactions"
        for check in _workflow_details(report)["checks"]
    )

    workflow = json.loads(instance.solution_files["workflow.json"])
    first_evidence = next(iter(workflow["evidence"]))
    workflow["evidence"][first_evidence] = "wrong-disposition"
    report = _grade(instance, workflow=json.dumps(workflow))
    assert report.reward == 0
    assert any(
        not check["passed"] and check["type"] == "evidence_disposition"
        for check in _workflow_details(report)["checks"]
    )


def test_close_partial_attempt_has_interpretable_cluster_scores():
    instance = _instance(3)
    blocks = _blocks(instance)
    partial = instance.initial_ledger + blocks[0] + "\n"
    report = _grade(instance, ledger=partial)
    clusters = _workflow_details(report)["clusters"]
    assert report.reward == 0
    assert 0 < report.to_reward_json()["rubric_completion"] < 1
    assert any(score == 1.0 for score in clusters.values())
    assert any(score < 1.0 for score in clusters.values())


def test_close_combined_entry_is_equivalent():
    instance = _instance(19)
    blocks = _blocks(instance)
    first, second, *rest = blocks
    postings = []
    for block in [first, second]:
        postings.extend(line for line in block.splitlines() if line.startswith("  "))
    combined = '2026-01-31 * "Controller" "Combined close adjustments"\n' + "\n".join(postings)
    ledger = instance.initial_ledger + "\n\n".join([combined, *rest]) + "\n"
    report = _grade(instance, ledger=ledger)
    assert report.reward == 1, report.to_report_json()


def test_generated_close_task_validates(tmp_path: Path):
    instance = _instance(23)
    task_dir = write_task(instance, tmp_path, track="dynamic")
    assert validate_tasks(tmp_path) == []
    task_toml = (task_dir / "task.toml").read_text()
    assert 'format = "workflow"' in task_toml
    assert 'level = "professional"' in task_toml
    assert 'track = "dynamic"' in task_toml
