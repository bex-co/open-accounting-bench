"""Month-end close professional workflow pilot."""

import csv
import functools
import io
import json
import re
from datetime import date
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
ISSUE_DETERMINATIONS = {
    "revenue-cutoff",
    "revenue-cost-reversal",
    "service-revenue-milestone",
    "receivables-allowance",
    "inventory-valuation",
    "inventory-goods-in-transit",
    "unrecorded-payables",
    "prepayment-cutoff",
    "payroll-cutoff",
    "fixed-asset-treatment",
    "fixed-asset-impairment",
    "debt-interest-accrual",
    "debt-current-classification",
    "bank-reconciliation",
    "bank-fee-reconciliation",
}


NEXT_PERIOD_ACCRUAL = (
    '2026-01-31 * "Supplier" "Accrue February utility invoice"\n'
    "  Expenses:Utilities  400.00 USD\n"
    "  Liabilities:AccountsPayable  -400.00 USD\n"
)


def _instance(seed: int = 42):
    return DYNAMIC_FAMILIES[FAMILY](seed)


def _is_clean(instance) -> bool:
    return "clean-month" in instance.keywords


def _adjusting_instance(seed: int):
    """An instance from the adjustment variant (not a clean-month control)."""
    instance = _instance(seed)
    assert not _is_clean(instance), seed
    return instance


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
    assert 40 <= len(spec["checks"]) <= 72
    clusters = {item["cluster"] for item in spec["determinations"]}
    assert len(clusters & CLUSTERS) >= 9
    assert ISSUE_DETERMINATIONS <= {item["id"] for item in spec["determinations"]}
    assert json.loads(instance.app_files["workflow.json"])["evidence"] == {}
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
        assert "utility service" in instance.app_files["documents/close_documents.csv"].lower()


def test_close_tuned_contract_links_nsf_and_false_alarms():
    for seed in range(8):
        instance = _instance(seed)
        if _is_clean(instance):
            continue
        policy = " ".join(instance.app_files["policy.md"].split())
        assert "days past due at period-end" in policy
        assert "annual rate / 12" in policy
        assert "even if it is below USD 100" in policy
        for path in (
            "documents/close_documents.csv",
            "documents/close_debt_schedules.csv",
            "documents/close_subsequent_receipts.csv",
            "documents/close_timesheets.csv",
            "documents/close_fixed_asset_review.csv",
        ):
            assert path in instance.app_files, (seed, path)
        assert len(instance.expected["workflow"]["checks"]) >= 68

        aging = list(
            csv.DictReader(io.StringIO(instance.app_files["documents/close_ar_aging.csv"]))
        )
        assert any(row["record_id"] == "close-ar-9002" for row in aging)
        subsequent = list(
            csv.DictReader(
                io.StringIO(instance.app_files["documents/close_subsequent_receipts.csv"])
            )
        )
        aging_amounts = {row["record_id"]: row["amount"] for row in aging}
        settled_ids = {
            row["record_id"]
            for row in subsequent
            if aging_amounts.get(row["record_id"]) == row["amount"]
        }
        assert settled_ids

        def policy_rate(row) -> Decimal:
            # The stated policy alone determines the rate (no source labels).
            if "bankruptcy" in row["credit_note"]:
                return Decimal("1.00")
            days = (date(2026, 1, 31) - date.fromisoformat(row["due_date"])).days
            if days <= 0:
                return Decimal("0.01")
            return Decimal("0.05") if days <= 30 else Decimal("0.20")

        expected_allowance = sum(
            (Decimal(row["amount"]) * policy_rate(row)).quantize(Decimal("0.01"))
            for row in aging
            # close-ar-9001 is the premature sale reversed by revenue cutoff.
            if row["record_id"] != "close-ar-9001" and row["record_id"] not in settled_ids
        )
        workflow = json.loads(instance.solution_files["workflow.json"])
        assert Decimal(workflow["trial_balance"]["allowance_for_credit_losses"]) == (
            -expected_allowance
        )
        assert Decimal(workflow["trial_balance"]["goods_in_transit"]) > 0
        # Evidence is keyed by neutral source-document ids.
        assert workflow["evidence"]["close-ms-02"] == "defer-unearned-milestone"
        assert workflow["evidence"]["close-ship-001"] == "record-goods-in-transit"
        assert workflow["evidence"]["doc-timesheets"] == "accrue-earned-wages"
        assert workflow["evidence"]["doc-asset-review"] == "recognize-impairment-loss"
        assert workflow["evidence"]["close-loan-sch-02"] == "accrue-interest"
        assert workflow["evidence"]["close-bank-adv-02"] == "record-bank-fee"
        assert workflow["evidence"]["close-inv-1003"] == "exclude-next-period"
        assert workflow["evidence"]["close-inv-1002"] == "ignore-duplicate-copy"
        assert workflow["evidence"]["close-equip-inv-02"] == "keep-capitalized"
        assert workflow["evidence"]["close-loan-sch-01"] == "use-revised-schedule"
        assert workflow["evidence"]["doc-feb-receipts"] == "no-adjustment"
        # Draft entries are posted with neutral bookkeeping narrations.
        assert "Cost of sales close-order-001" in instance.initial_ledger
        assert "Milestone billing close-ms-02" in instance.initial_ledger
        assert "Supplier invoice close-equip-inv-02" in instance.initial_ledger
        assert "Depreciation on January additions" in instance.initial_ledger


def test_close_oracle_noop_and_seed_sweep():
    for seed in range(25):
        instance = _instance(seed)
        oracle = _grade(instance)
        assert oracle.reward == 1, (seed, oracle.to_report_json())
        assert oracle.to_reward_json()["rubric_completion"] == 1.0
        nop = _grade(instance, ledger=instance.initial_ledger)
        if _is_clean(instance):
            # Nothing to adjust: leaving the ledger alone is the oracle.
            assert nop.reward == 1, seed
        else:
            assert nop.reward == 0
            assert nop.to_reward_json()["rubric_completion"] < 0.5
        workflow = json.loads(instance.solution_files["workflow.json"])
        assert Decimal(workflow["trial_balance"]["bank"]) > 0
        assert Decimal(workflow["trial_balance"]["inventory"]) >= 0
        clusters = {item["cluster"] for item in instance.expected["workflow"]["determinations"]}
        assert len(clusters & CLUSTERS) == 9


def test_close_issue_omission_mutants_lose_their_clusters():
    instance = _adjusting_instance(8)
    blocks = _blocks(instance)
    assert len(blocks) >= 15
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
    assert set(issue_determinations) == ISSUE_DETERMINATIONS

    # Omitting one adjustment block at a time must lose at least one
    # determination; across the sweep every issue cluster is lost once.
    lost_clusters = set()
    for index in range(len(blocks)):
        ledger = instance.initial_ledger + "\n\n".join(
            block for other, block in enumerate(blocks) if other != index
        )
        report = _grade(instance, ledger=ledger)
        assert report.reward == 0
        for detail in _workflow_details(report)["determinations"].values():
            if not detail["passed"] and detail["cluster"] in CLUSTERS:
                lost_clusters.add(detail["cluster"])
    assert lost_clusters == CLUSTERS


def test_close_duplicate_wrong_period_and_wrong_disposition_mutants():
    instance = _adjusting_instance(11)
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
    instance = _adjusting_instance(3)
    blocks = _blocks(instance)
    partial = instance.initial_ledger + blocks[0] + "\n"
    report = _grade(instance, ledger=partial)
    clusters = _workflow_details(report)["clusters"]
    assert report.reward == 0
    assert 0 < report.to_reward_json()["rubric_completion"] < 1
    assert any(score == 1.0 for score in clusters.values())
    assert any(score < 1.0 for score in clusters.values())


def test_close_combined_entry_is_equivalent():
    instance = _adjusting_instance(19)
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


# --- Clean-month negative control (w2/m2) -------------------------------


@functools.cache
def _clean_seeds(limit: int = 40) -> tuple[int, ...]:
    return tuple(seed for seed in range(limit) if _is_clean(_instance(seed)))


def test_some_seeds_draw_a_clean_month_and_most_do_not():
    clean = _clean_seeds()
    assert 3 <= len(clean) <= 16, clean


def test_clean_month_noop_is_the_oracle():
    for seed in _clean_seeds():
        instance = _instance(seed)
        assert instance.solution_ledger == instance.initial_ledger
        assert instance.expected["expected_deltas"] == {}
        assert instance.expected["expected_new_transactions"] == 0
        report = _grade(instance)
        assert report.reward == 1, (seed, report.to_report_json())
        workflow = json.loads(instance.solution_files["workflow.json"])
        issue_evidence = [
            check
            for check in instance.expected["workflow"]["checks"]
            if check["type"] == "evidence_disposition"
            and check["determination"] in ISSUE_DETERMINATIONS
        ]
        assert issue_evidence
        for check in issue_evidence:
            assert check["expected"] == "already-recorded"
            assert workflow["evidence"][check["key"]] == "already-recorded"
        # The close is already complete: the adjustments sit in the ledger.
        assert "Record credit-loss allowance" in instance.initial_ledger


def test_clean_month_contract_discloses_already_recorded():
    for seed in _clean_seeds()[:3]:
        policy = " ".join(_instance(seed).app_files["policy.md"].split())
        assert "`already-recorded`" in policy


def test_generated_clean_month_task_validates(tmp_path: Path):
    instance = _instance(_clean_seeds()[0])
    write_task(instance, tmp_path, track="dynamic")
    assert validate_tasks(tmp_path) == []


def test_clean_month_over_action_fails_non_structural_layers():
    """Trap: re-posting an adjustment the ledger already holds, or accruing
    a next-period bill, balances perfectly but must not pass."""
    instance = _instance(_clean_seeds()[0])
    allowance_entry = next(
        block
        for block in instance.initial_ledger.split("\n\n")
        if "Record credit-loss allowance" in block
    )
    for extra in (allowance_entry.strip() + "\n", NEXT_PERIOD_ACCRUAL):
        ledger = instance.initial_ledger + "\n" + extra
        report = _grade(instance, ledger=ledger)
        assert report.reward == 0
        layers = report.layers
        assert layers["structural_validity"].passed
        assert not layers["economic_consistency"].passed
        assert not layers["operational_integrity"].passed
        assert not layers["workflow_rubric"].passed


def test_over_action_diagnostic_only_on_no_action_tasks():
    clean = _instance(_clean_seeds()[0])
    assert _grade(clean).to_reward_json()["over_action"] == 0.0
    over = _grade(clean, ledger=clean.initial_ledger + "\n" + NEXT_PERIOD_ACCRUAL)
    assert over.to_reward_json()["over_action"] == 1.0
    adjustments = _adjusting_instance(8)
    assert "over_action" not in _grade(adjustments).to_reward_json()


def test_is_no_action_accepts_both_encodings_of_zero():
    from oab.verify import is_no_action

    assert is_no_action({"expected_new_transactions": 0})
    assert is_no_action({"expected_new_transactions": [0, 0]})
    assert not is_no_action({"expected_new_transactions": [0, 1]})
    assert not is_no_action({"expected_new_transactions": [1, 40]})
    assert not is_no_action({})


def test_validate_relaxes_only_no_action_controls(tmp_path: Path):
    """An adjustment task whose solution equals its initial ledger, or whose
    deltas are empty, is still rejected; only a declared no-action passes."""
    instance = _adjusting_instance(8)
    task_dir = write_task(instance, tmp_path, track="dynamic")
    (task_dir / "solution" / "ledger.beancount").write_text(instance.initial_ledger)
    expected_path = task_dir / "tests" / "expected.json"
    expected = json.loads(expected_path.read_text())
    expected["expected_deltas"] = {}
    expected_path.write_text(json.dumps(expected))
    failures = "\n".join(validate_tasks(tmp_path))
    assert "workflow expected_deltas must be non-empty" in failures
    assert "solution ledger must differ from initial" in failures


def test_workflow_report_carries_ledger_diagnostics():
    instance = _adjusting_instance(8)
    details = _grade(instance).to_report_json()["details"]
    assert "workflow" in details
    assert set(details["diagnostics"]["expected"].values()) == {"correct"}
    nop = _grade(instance, ledger=instance.initial_ledger).to_report_json()["details"]
    assert "missing" in set(nop["diagnostics"]["expected"].values())


def test_close_sources_do_not_name_issues():
    """De-labelled evidence (w2/m6): no app file except the policy names a
    determination, and evidence is keyed by source-document ids."""
    leaked = []
    for seed in range(40):
        instance = _instance(seed)
        issue_ids = ISSUE_DETERMINATIONS
        for path, text in instance.app_files.items():
            if path == "policy.md":
                continue
            leaked += [(seed, path, issue) for issue in issue_ids if issue in text]
        workflow = json.loads(instance.solution_files["workflow.json"])
        sources = "".join(
            text for path, text in instance.app_files.items() if path.startswith("documents/close_")
        )
        assert all(key in sources for key in workflow["evidence"]), seed
    assert leaked == []


def _replace_block_amounts(ledger: str, narration: str, new_amount: Decimal) -> str:
    """Rewrite a two-posting oracle block to a new (balanced) amount."""
    blocks = ledger.split("\n\n")
    for index, block in enumerate(blocks):
        if narration in block:
            lines = block.splitlines()
            header, debit, credit = lines[0], lines[1], lines[2]
            debit_account = debit.split()[0]
            credit_account = credit.split()[0]
            blocks[index] = (
                f"{header}\n  {debit_account}  {new_amount:.2f} USD\n"
                f"  {credit_account}  {-new_amount:.2f} USD"
            )
            return "\n\n".join(blocks)
    raise AssertionError(narration)


def test_precedence_traps_fail_without_source_labels():
    """Relying on the client's superseded loan schedule, or on the unsigned
    count copy, balances but fails non-structural layers."""
    for seed in (3, 8, 11):
        instance = _adjusting_instance(seed)
        schedules = list(
            csv.DictReader(io.StringIO(instance.app_files["documents/close_debt_schedules.csv"]))
        )
        draft = next(row for row in schedules if row["prepared_by"].startswith("Client"))
        stale_interest = (
            Decimal(draft["opening_principal"]) * Decimal(draft["annual_rate_percent"]) / 1200
        ).quantize(Decimal("0.01"))
        stale = _replace_block_amounts(
            instance.solution_ledger, "Accrue January note interest", stale_interest
        )
        report = _grade(instance, ledger=stale)
        assert report.reward == 0, seed
        assert report.layers["structural_validity"].passed

        counts = list(
            csv.DictReader(io.StringIO(instance.app_files["documents/close_inventory_count.csv"]))
        )
        unsigned = next(row for row in counts if not row["signed_by"])
        signed = next(
            row for row in counts if row["item_id"] == unsigned["item_id"] and row["signed_by"]
        )
        shortage_cost = (
            Decimal(unsigned["count_quantity"]) - Decimal(signed["count_quantity"])
        ) * Decimal(signed["unit_cost"])
        assert shortage_cost > 0
        oracle_write_down = next(
            Decimal(line.split()[1])
            for block in instance.solution_ledger.split("\n\n")
            if "Record inventory write-down" in block
            for line in block.splitlines()[1:2]
        )
        unsigned_ledger = _replace_block_amounts(
            instance.solution_ledger,
            "Record inventory write-down",
            oracle_write_down - shortage_cost,
        )
        report = _grade(instance, ledger=unsigned_ledger)
        assert report.reward == 0, seed
        assert report.layers["structural_validity"].passed
