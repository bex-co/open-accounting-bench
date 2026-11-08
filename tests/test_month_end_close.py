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


def _is_withheld(instance) -> bool:
    return "withheld-evidence" in instance.keywords


def _adjusting_instance(seed: int):
    """A full adjustment instance: every issue present and evidenced (not a
    clean-month or insufficient-evidence control)."""
    instance = _instance(seed)
    assert not _is_clean(instance) and not _is_withheld(instance), seed
    return instance


@functools.cache
def _variant(seed: int) -> str:
    """'clean', 'withheld', or 'full' — generated once per seed."""
    instance = _instance(seed)
    return "clean" if _is_clean(instance) else "withheld" if _is_withheld(instance) else "full"


def _seeds(variant: str, limit: int = 40) -> tuple[int, ...]:
    return tuple(seed for seed in range(limit) if _variant(seed) == variant)


def _full_seeds() -> tuple[int, ...]:
    return _seeds("full")


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
    for seed in (seed for seed in _full_seeds() if seed < 8):
        instance = _instance(seed)
        policy = " ".join(instance.app_files["policy.md"].split())
        assert "days past due at period-end" in policy
        assert "annual rate / 12" in policy
        assert "even if it is below USD 100" in policy
        for path in (
            "documents/close_documents.csv",
            "documents/close_debt_schedules.csv",
            "documents/close_timesheets.csv",
            "documents/close_fixed_asset_review.csv",
        ):
            assert path in instance.app_files, (seed, path)
        assert len(instance.expected["workflow"]["checks"]) >= 68

        aging = list(
            csv.DictReader(io.StringIO(instance.app_files["documents/close_ar_aging.csv"]))
        )
        assert any(row["record_id"] == "close-ar-9002" for row in aging)

        def raw(path, files=instance.app_files):
            return list(csv.DictReader(io.StringIO(files[f"documents/{path}"])))

        aging_amounts = {row["record_id"]: row["amount"] for row in aging}
        # Settlements and bankruptcies live only in the raw source documents.
        settled_ids = {
            row["source_refs"]
            for row in raw("customer_receipts.csv")
            if row["date"] <= "2026-02-15"
            and aging_amounts.get(row["source_refs"]) == row["document_total"]
        }
        assert settled_ids
        bankrupt_ids = {
            row["source_refs"]
            for row in raw("other_documents.csv")
            if row["kind"] == "customer_notice" and "bankruptcy" in row["description"]
        }
        assert bankrupt_ids

        def policy_rate(row, bankrupt_ids=bankrupt_ids) -> Decimal:
            # The stated policy alone determines the rate (no source labels).
            if row["record_id"] in bankrupt_ids:
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
        # Draft entries are posted with neutral bookkeeping narrations.
        assert "Cost of sales close-order-001" in instance.initial_ledger
        assert "Milestone billing close-ms-02" in instance.initial_ledger
        assert "Supplier invoice close-equip-inv-02" in instance.initial_ledger
        assert "Depreciation on January additions" in instance.initial_ledger


def test_close_oracle_noop_and_seed_sweep():
    for seed in range(40):
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
    instance = _adjusting_instance(_full_seeds()[0])
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
    instance = _adjusting_instance(_full_seeds()[1])
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
    instance = _adjusting_instance(_full_seeds()[2])
    blocks = _blocks(instance)
    partial = instance.initial_ledger + blocks[0] + "\n"
    report = _grade(instance, ledger=partial)
    clusters = _workflow_details(report)["clusters"]
    assert report.reward == 0
    assert 0 < report.to_reward_json()["rubric_completion"] < 1
    assert any(score == 1.0 for score in clusters.values())
    assert any(score < 1.0 for score in clusters.values())


def test_close_combined_entry_is_equivalent():
    instance = _adjusting_instance(_full_seeds()[3])
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


def _clean_seeds() -> tuple[int, ...]:
    return _seeds("clean")


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
    adjustments = _adjusting_instance(_full_seeds()[0])
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
    instance = _adjusting_instance(_full_seeds()[0])
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
    instance = _adjusting_instance(_full_seeds()[0])
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
        for path, text in instance.app_files.items():
            if path == "policy.md":
                continue
            leaked += [(seed, path, issue) for issue in ISSUE_DETERMINATIONS if issue in text]
        workflow = json.loads(instance.solution_files["workflow.json"])
        sources = "".join(
            text for path, text in instance.app_files.items() if path.startswith("documents/close_")
        )
        assert all(key in sources for key in workflow["evidence"]), seed
    assert leaked == []


def _block(ledger: str, narration: str) -> str:
    """The ledger entry block with this narration."""
    return next(b for b in ledger.split("\n\n") if narration in b)


def _block_amount(ledger: str, narration: str) -> Decimal:
    """Debit amount of the two-posting block with this narration."""
    return Decimal(_block(ledger, narration).splitlines()[1].split()[1])


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
    for seed in _full_seeds():
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
        oracle_write_down = _block_amount(instance.solution_ledger, "Record inventory write-down")
        unsigned_ledger = _replace_block_amounts(
            instance.solution_ledger,
            "Record inventory write-down",
            oracle_write_down - shortage_cost,
        )
        report = _grade(instance, ledger=unsigned_ledger)
        assert report.reward == 0, seed
        assert report.layers["structural_validity"].passed


def test_close_loss_rate_ladder_matches_policy():
    from decimal import Decimal as D

    from oab.workflow_families import _close_loss_rate

    assert _close_loss_rate(-5) == D("0.01")
    assert _close_loss_rate(0) == D("0.01")  # due on period-end: not yet past due
    assert _close_loss_rate(1) == D("0.05")
    assert _close_loss_rate(30) == D("0.05")
    assert _close_loss_rate(31) == D("0.20")
    assert _close_loss_rate(2, bankrupt=True) == D("1.00")


def test_accruing_the_duplicate_invoice_copy_fails():
    """Without a duplicate flag, the copy is recognised only by matching the
    original; accruing it as a second liability balances but fails."""
    instance = _adjusting_instance(_full_seeds()[0])
    amount = _block_amount(instance.solution_ledger, "Accrue unrecorded supplier service")
    second = (
        '2026-01-31 * "Supplier" "Accrue supplier invoice close-inv-1002"\n'
        f"  Expenses:Utilities  {amount:.2f} USD\n"
        f"  Liabilities:AccountsPayable  {-amount:.2f} USD\n"
    )
    report = _grade(instance, ledger=instance.solution_ledger + "\n" + second)
    assert report.reward == 0
    assert report.layers["structural_validity"].passed
    assert not report.layers["semantic_accuracy"].passed


def _without_block(ledger: str, *narrations: str) -> str:
    return "\n\n".join(
        block for block in ledger.split("\n\n") if not any(n in block for n in narrations)
    )


def _rows(files: dict, path: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(files[path])))


def test_decisive_facts_live_only_in_secondary_sources():
    """Five issues need a secondary source (m7); reading only the close
    register and schedules gives an answer that balances but fails."""
    for seed in _full_seeds()[:6]:
        instance = _adjusting_instance(seed)
        files = instance.app_files
        register = files["documents/close_documents.csv"]
        aging = files["documents/close_ar_aging.csv"]
        # The decisive facts are absent from the primary close sources ...
        assert "ship date" not in register and "FOB" not in register
        assert "-29" not in "".join(
            line for line in register.splitlines() if line.startswith("close-inv-")
        )
        assert "bankruptcy" not in aging
        # ... and present in the secondary ones.
        assert "close-order-001" in files["documents/shipping_log.csv"]
        assert "FOB shipping point" in files["documents/supplier_documents.csv"]
        assert "close-inv-1001" in files["documents/other_documents.csv"]
        assert "bankruptcy" in files["documents/other_documents.csv"]
        assert "syn-receipt-close-001" in files["documents/customer_receipts.csv"]

        oracle = instance.solution_ledger
        primary_only = [
            _without_block(
                oracle, "Reverse premature product sale", "Reverse cost of premature product sale"
            ),
            _without_block(oracle, "Record goods in transit"),
            _without_block(oracle, "Accrue unrecorded supplier service"),
        ]
        rows = {row["record_id"]: row for row in _rows(files, "documents/close_ar_aging.csv")}
        notice = next(
            row
            for row in _rows(files, "documents/other_documents.csv")
            if row["kind"] == "customer_notice"
        )
        receipt = next(
            row
            for row in _rows(files, "documents/customer_receipts.csv")
            if row["document_id"] == "syn-receipt-close-001"
        )
        allowance = _block_amount(oracle, "Record credit-loss allowance")
        bankrupt = Decimal(rows[notice["source_refs"]]["amount"])
        settled = Decimal(receipt["document_total"])
        # Bankrupt row at the ordinary 20% instead of 100%; settled row at 1%.
        primary_only.append(
            _replace_block_amounts(
                oracle, "Record credit-loss allowance", allowance - bankrupt * Decimal("0.80")
            )
        )
        primary_only.append(
            _replace_block_amounts(
                oracle, "Record credit-loss allowance", allowance + settled * Decimal("0.01")
            )
        )
        for ledger in primary_only:
            report = _grade(instance, ledger=ledger)
            assert report.reward == 0, seed
            assert report.layers["structural_validity"].passed, seed


def test_close_volume_and_distractors_are_consistent():
    from oab.workflow_families import MAX_CLOSE_APP_BYTES, MAX_CLOSE_APP_FILES

    for seed in range(40):
        files = _instance(seed).app_files
        assert 65 <= len(files) <= MAX_CLOSE_APP_FILES, (seed, len(files))
        assert sum(len(text.encode()) for text in files.values()) <= MAX_CLOSE_APP_BYTES, seed
    instance = _adjusting_instance(_full_seeds()[0])
    files = instance.app_files
    payables = list(csv.DictReader(io.StringIO(files["subledgers/accounts_payable.csv"])))
    for path, text in files.items():
        if not path.startswith("documents/vendor_statements/"):
            continue
        rows = list(csv.DictReader(io.StringIO(text)))
        statement = {
            row["bill_id"]: row["open_amount"] for row in rows if row["bill_id"] != "balance"
        }
        # A vendor statement agrees with the payables subledger: no entry.
        for bill_id, amount in statement.items():
            book = next(r for r in payables if r["record_id"] == bill_id)
            assert Decimal(amount) == -Decimal(book["amount"]), (path, bill_id)


def test_accruing_an_unreceived_purchase_order_fails():
    instance = _adjusting_instance(_full_seeds()[0])
    po = next(
        t for p, t in instance.app_files.items() if p.startswith("documents/purchase_orders/")
    )
    quantity, unit_cost = re.search(r"\| (\d+) \| ([\d.]+) \|", po).groups()
    amount = Decimal(quantity) * Decimal(unit_cost)
    accrual = (
        '2026-01-31 * "Supplier" "Accrue open purchase order"\n'
        f"  Assets:Inventory  {amount:.2f} USD\n"
        f"  Liabilities:AccountsPayable  {-amount:.2f} USD\n"
    )
    report = _grade(instance, ledger=instance.solution_ledger + "\n" + accrual)
    assert report.reward == 0
    assert report.layers["structural_validity"].passed


def test_close_generation_enforces_its_file_budget(monkeypatch):
    import pytest

    import oab.workflow_families as workflow_families

    monkeypatch.setattr(workflow_families, "MAX_CLOSE_APP_FILES", 10)
    with pytest.raises(ValueError, match="close app files file count"):
        workflow_families.month_end_close_workflow(8)


def test_paystubs_agree_with_the_payroll_register():
    instance = _adjusting_instance(_full_seeds()[0])
    files = instance.app_files
    register = {
        row["description"]: row["line_amount"]
        for row in _rows(files, "documents/payroll_register.csv")
        if row["period"] == "2026-01"
    }
    stubs = [text for path, text in files.items() if path.startswith("documents/paystubs/")]
    assert stubs
    for text in stubs:
        name = text.splitlines()[0].split(": ", 1)[1]
        salary = re.search(r"Regular salary: ([\d.]+)", text).group(1)
        assert register[name] == salary, name


# Withheld document id -> (issue, estimated entry's narration, debit account,
# check that the deciding document is absent from the evidence).
WITHHELD_ISSUES = {
    "close-ship-001": (
        "goods-in-transit",
        "Record goods in transit",
        "Assets:GoodsInTransit",
        lambda files: "FOB shipping point" not in files["documents/supplier_documents.csv"],
    ),
    "close-inv-1001": (
        "unrecorded-payables",
        "Accrue unrecorded supplier service",
        "Expenses:Utilities",
        lambda files: (
            not any(
                row["kind"] == "service_report" and row["source_refs"] == "close-inv-1001"
                for row in _rows(files, "documents/other_documents.csv")
            )
        ),
    ),
}


def test_insufficient_evidence_controls_flag_and_post_nothing():
    """m8: when the deciding document is withheld, the oracle flags the item
    and posts nothing for it; estimating from partial evidence fails."""
    seeds = _seeds("withheld")
    assert len(seeds) >= 3, seeds
    covered = set()
    for seed in seeds:
        instance = _instance(seed)
        files = instance.app_files
        assert "`insufficient-evidence`" in instance.app_files["policy.md"]
        workflow = json.loads(instance.solution_files["workflow.json"])
        flagged = [
            doc for doc, code in workflow["evidence"].items() if code == "insufficient-evidence"
        ]
        assert len(flagged) == 1, (seed, flagged)
        assert _grade(instance).reward == 1, seed
        document_id = flagged[0]
        issue, narration, debit, missing = WITHHELD_ISSUES[document_id]
        covered.add(issue)
        assert missing(files), seed
        assert narration not in instance.solution_ledger
        amount = Decimal(
            next(
                row["amount"]
                for row in _rows(files, "documents/close_documents.csv")
                if row["document_id"] == document_id
            )
        )
        estimate = (
            f'2026-01-31 * "Supplier" "{narration}"\n'
            f"  {debit}  {amount:.2f} USD\n"
            f"  Liabilities:AccountsPayable  {-amount:.2f} USD\n"
        )
        report = _grade(instance, ledger=instance.solution_ledger + "\n" + estimate)
        assert report.reward == 0, seed
        assert report.layers["structural_validity"].passed, seed
    assert covered == {"goods-in-transit", "unrecorded-payables"}


def test_withheld_entry_must_match_an_oracle_narration(monkeypatch):
    """If an omitted entry's narration drifts, generation fails loudly
    instead of silently posting the withheld entry."""
    import pytest

    import oab.workflow_families as workflow_families

    seed = _seeds("withheld")[0]
    renamed = dict.fromkeys(workflow_families.WITHHELD_ENTRY, "No such narration")
    monkeypatch.setattr(workflow_families, "WITHHELD_ENTRY", renamed)
    with pytest.raises(AssertionError):
        workflow_families.month_end_close_workflow(seed)


def test_close_variants_are_exclusive():
    for seed in range(40):
        instance = _instance(seed)
        assert not (_is_clean(instance) and _is_withheld(instance)), seed


def _determination_passed(report, determination_id: str) -> bool:
    return _workflow_details(report)["determinations"][determination_id]["passed"]


def test_first_link_only_mutants_fail_their_downstream_determination():
    """m9: for each dependency chain, a close that applies only the first
    link fails the determination of the dependent computation."""
    for seed in _full_seeds()[:6]:
        instance = _adjusting_instance(seed)
        files, oracle = instance.app_files, instance.solution_ledger
        allowance = _block_amount(oracle, "Record credit-loss allowance")
        order = next(
            row
            for row in _rows(files, "documents/close_documents.csv")
            if row["document_id"] == "close-order-001"
        )
        returned = next(
            row
            for row in _rows(files, "documents/close_ar_aging.csv")
            if row["record_id"] == "close-ar-9002"
        )
        lender = next(
            row
            for row in _rows(files, "documents/close_debt_schedules.csv")
            if row["prepared_by"] == "Lender"
        )
        opening_interest = (
            Decimal(lender["opening_principal"]) * Decimal(lender["annual_rate_percent"]) / 1200
        ).quantize(Decimal("0.01"))
        repair = _block(oracle, "Expense routine equipment repair")
        repair_amount = _block_amount(oracle, "Expense routine equipment repair")
        repair_kept_depreciation = (
            f"{repair.splitlines()[0]}\n"
            f"  Expenses:Repairs  {repair_amount:.2f} USD\n"
            f"  Assets:Equipment  {-repair_amount:.2f} USD"
        )
        workflow = json.loads(instance.solution_files["workflow.json"])
        statement = workflow["income_statement"]
        statement["total_expenses"] = str(Decimal(statement["total_expenses"]) - allowance)
        # (determination that must fail, label, mutant ledger, mutant schedule)
        cases = [
            (
                "receivables-allowance",
                "1: sale reversed, premature receivable still reserved (1%)",
                _replace_block_amounts(
                    oracle,
                    "Record credit-loss allowance",
                    allowance
                    + (Decimal(order["amount"]) * Decimal("0.01")).quantize(Decimal("0.01")),
                ),
                None,
            ),
            (
                "receivables-allowance",
                "2: returned check recorded but left out of the allowance (20%)",
                _replace_block_amounts(
                    oracle,
                    "Record credit-loss allowance",
                    allowance
                    - (Decimal(returned["amount"]) * Decimal("0.20")).quantize(Decimal("0.01")),
                ),
                None,
            ),
            (
                "debt-interest-accrual",
                "3: interest on opening principal, ignoring the Jan-15 payment",
                _replace_block_amounts(oracle, "Accrue January note interest", opening_interest),
                None,
            ),
            (
                "reporting",
                "4: every adjustment posted, draft total expenses reported",
                None,
                json.dumps(workflow),
            ),
            (
                "fixed-asset-treatment",
                "5: repair expensed but its January depreciation kept",
                oracle.replace(repair, repair_kept_depreciation),
                None,
            ),
        ]
        for determination, label, ledger, schedule in cases:
            report = _grade(instance, ledger=ledger, workflow=schedule)
            assert report.reward == 0, (seed, label)
            assert not _determination_passed(report, determination), (seed, label)


def test_chained_depreciation_check_expectations():
    def chained(instance):
        return next(
            check
            for check in instance.expected["workflow"]["checks"]
            if check["id"] == "fixed-asset-treatment-chained-delta"
        )

    full = _adjusting_instance(_full_seeds()[0])
    check = chained(full)
    assert check["account"] == "Expenses:Depreciation"
    draft_depreciation = _block_amount(full.initial_ledger, "Depreciation on January additions")
    assert Decimal(check["expected"]) == -draft_depreciation
    clean = _instance(_clean_seeds()[0])
    assert Decimal(chained(clean)["expected"]) == 0
    assert _grade(clean).reward == 1


def _retarget(ledger: str, narration: str, account: str, near_miss: str) -> str:
    """Move one posting of the block with this narration to a near-miss account."""
    block = _block(ledger, narration)
    assert f"  {account}  " in block, (narration, account)
    return ledger.replace(block, block.replace(f"  {account}  ", f"  {near_miss}  "))


NEAR_MISS_TRAPS = [
    # (oracle narration, right account, near-miss account, diagnosed as)
    (
        "Defer unexpired prepaid rent",
        "Assets:PrepaidRent",
        "Assets:PrepaidExpenses",
        "wrong-account",
    ),
    (
        "Defer unearned February service milestone",
        "Liabilities:ContractLiability",
        "Liabilities:CustomerDeposits",
        "wrong-account",
    ),
    (
        "Reclassify current portion of note",
        "Liabilities:CurrentPortionOfLongTermDebt",
        "Liabilities:ShortTermBorrowings",
        "wrong-account",
    ),
    (
        "Record credit-loss allowance",
        "Expenses:CreditLoss",
        "Expenses:BadDebtWriteOffs",
        "wrong-account",
    ),
    # Payables and receivables move through several entries, so a misposting
    # leaves them moved by the wrong amount rather than not at all.
    (
        "Accrue unrecorded supplier service",
        "Liabilities:AccountsPayable",
        "Liabilities:AccruedLiabilities",
        "wrong-amount",
    ),
    (
        "Record returned customer check",
        "Assets:AccountsReceivable",
        "Assets:OtherReceivables",
        "wrong-amount",
    ),
]


def test_near_miss_account_traps_fail_and_are_diagnosed():
    for seed in _full_seeds()[:4]:
        instance = _adjusting_instance(seed)
        for narration, account, near_miss, diagnosis in NEAR_MISS_TRAPS:
            ledger = _retarget(instance.solution_ledger, narration, account, near_miss)
            report = _grade(instance, ledger=ledger)
            assert report.reward == 0, (seed, narration)
            assert report.layers["structural_validity"].passed, (seed, narration)
            details = report.to_report_json()["details"]["diagnostics"]
            assert details["expected"][account] == diagnosis, (seed, narration, details)
            # A wrong-account diagnosis explains the near-miss movement; otherwise
            # it is reported as an unexplained extra movement.
            assert (near_miss in details["extra"]) == (diagnosis != "wrong-account"), seed


def test_close_ledgers_open_each_account_once():
    from collections import Counter

    for seed in range(40):
        ledger = _instance(seed).initial_ledger
        opened = Counter(
            line.split()[2]
            for line in ledger.splitlines()
            if len(line.split()) > 2 and line.split()[1] == "open"
        )
        assert [a for a, n in opened.items() if n > 1] == [], seed
