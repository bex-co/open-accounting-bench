"""Verifier behavior: oracle passes, nop fails, traps fail the right layer."""

import pytest

from oab.families import FAMILIES
from oab.verify import parse_ledger, verify

JOURNAL_FAMILIES = [tid for tid in sorted(FAMILIES) if FAMILIES[tid](1).format == "journal-entry"]


@pytest.mark.parametrize("task_id", JOURNAL_FAMILIES)
@pytest.mark.parametrize("seed", [1, 7, 42, 2026])
def test_oracle_passes_and_nop_fails(task_id, seed):
    instance = FAMILIES[task_id](seed)
    oracle = verify(instance.initial_ledger, instance.solution_ledger, instance.expected)
    assert oracle.reward == 1, oracle.to_report_json()
    nop = verify(instance.initial_ledger, instance.initial_ledger, instance.expected)
    assert nop.reward == 0
    assert nop.layers["semantic_accuracy"].score < 1.0


def test_balanced_but_misclassified_fails_semantics_only():
    """Memo §6: capitalizing an operating expense balances but is wrong."""
    instance = FAMILIES["classify-operating-expense"](101)
    # Leading spaces scope the replace to the posting, not the `open` line.
    wrong = instance.solution_ledger.replace("  Expenses:OfficeSupplies", "  Assets:Equipment")
    report = verify(instance.initial_ledger, wrong, instance.expected)
    assert report.reward == 0
    assert report.layers["structural_validity"].passed
    assert not report.layers["semantic_accuracy"].passed
    assert not report.layers["operational_integrity"].passed


def test_unbalanced_entry_fails_structure():
    instance = FAMILIES["classify-operating-expense"](101)
    wrong = instance.solution_ledger.replace("775.00 USD", "700.00 USD", 1)
    report = verify(instance.initial_ledger, wrong, instance.expected)
    assert not report.layers["structural_validity"].passed


def test_unopened_account_fails_structure():
    instance = FAMILIES["classify-operating-expense"](101)
    wrong = instance.solution_ledger.replace("  Expenses:OfficeSupplies", "  Expenses:Travel")
    report = verify(instance.initial_ledger, wrong, instance.expected)
    assert not report.layers["structural_validity"].passed


def test_duplicate_recording_fails_economics():
    instance = FAMILIES["classify-operating-expense"](101)
    added = instance.solution_ledger[len(instance.initial_ledger) :]
    report = verify(instance.initial_ledger, instance.solution_ledger + added, instance.expected)
    assert report.reward == 0
    assert not report.layers["economic_consistency"].passed


def test_editing_history_fails_integrity():
    instance = FAMILIES["correct-misclassification"](104)
    edited = instance.initial_ledger.replace("  Expenses:Repairs", "  Assets:Equipment")
    report = verify(instance.initial_ledger, edited, instance.expected)
    assert report.reward == 0
    assert not report.layers["operational_integrity"].passed


def test_wrong_period_fails_economics():
    instance = FAMILIES["prepaid-insurance-adjustment"](103)
    wrong = instance.solution_ledger.replace("2026-01-31", "2026-02-28")
    report = verify(instance.initial_ledger, wrong, instance.expected)
    assert not report.layers["economic_consistency"].passed


def test_expensing_full_prepayment_fails_semantics():
    instance = FAMILIES["prepaid-insurance-adjustment"](103)
    monthly = instance.expected["expected_deltas"]["Expenses:Insurance"]
    from decimal import Decimal

    total = Decimal(monthly) * 12
    wrong = instance.solution_ledger.replace(f"{monthly} USD", f"{total:.2f} USD").replace(
        f"-{monthly} USD", f"-{total:.2f} USD"
    )
    report = verify(instance.initial_ledger, wrong, instance.expected)
    assert report.reward == 0
    assert not report.layers["semantic_accuracy"].passed


def test_elided_posting_is_accepted_as_equivalent():
    instance = FAMILIES["classify-operating-expense"](101)
    amount = instance.expected["expected_deltas"]["Expenses:OfficeSupplies"]
    equivalent = instance.initial_ledger + (
        f'\n2026-01-22 * "Staples" "Office supplies"\n'
        f"  Expenses:OfficeSupplies  {amount} USD\n"
        "  Assets:Bank:Checking\n"
    )
    assert verify(instance.initial_ledger, equivalent, instance.expected).reward == 1


def test_combined_bank_recon_entry_is_accepted_as_equivalent():
    instance = FAMILIES["bank-recon-missing-fee"](102)
    deltas = instance.expected["expected_deltas"]
    fee = deltas["Expenses:BankFees"]
    payment = deltas["Expenses:Utilities"].lstrip("-")
    from decimal import Decimal

    bank = Decimal(deltas["Assets:Bank:Checking"])
    equivalent = instance.initial_ledger + (
        '\n2026-01-31 * "Bank" "Reconciliation adjustments"\n'
        f"  Expenses:BankFees  {fee} USD\n"
        f"  Expenses:Utilities  -{payment} USD\n"
        f"  Assets:Bank:Checking  {bank:.2f} USD\n"
    )
    assert verify(instance.initial_ledger, equivalent, instance.expected).reward == 1


def test_ifrs_expensing_qualifying_interest_fails_semantics():
    instance = FAMILIES["ifrs-capitalize-borrowing-costs"](107)
    added = instance.solution_ledger[len(instance.initial_ledger) :]
    wrong = instance.initial_ledger + added.replace("  Assets:Equipment", "  Expenses:Interest")
    report = verify(instance.initial_ledger, wrong, instance.expected)
    assert report.reward == 0
    assert report.layers["structural_validity"].passed
    assert not report.layers["semantic_accuracy"].passed


def test_parser_rejects_unknown_directives():
    ledger = parse_ledger("2026-01-01 open Assets:Cash USD\nfrobnicate x\n")
    assert ledger.errors


def _inventory_entries(cogs, write_down) -> str:
    return (
        '\n2026-01-31 * "Inventory" "Cost of sales"\n'
        f"  Expenses:CostOfSales  {cogs:.2f} USD\n"
        f"  Assets:Inventory  -{cogs:.2f} USD\n"
        '\n2026-01-31 * "Inventory" "NRV write-down"\n'
        f"  Expenses:InventoryWriteDown  {write_down:.2f} USD\n"
        f"  Assets:Inventory  -{write_down:.2f} USD\n"
    )


def test_weighted_average_cost_of_sales_fails_under_fifo_policy():
    """Trap: periodic weighted-average cost of sales when policy says FIFO."""
    from decimal import Decimal

    instance = FAMILIES["inventory-costing-nrv"](112)
    card = instance.app_files["documents/inventory_card.md"]
    rows = [r.split("|")[1:-1] for r in card.splitlines() if r.startswith("| 2026")]
    bought = [(int(r[2]), Decimal(r[3])) for r in rows if r[3].strip()]
    sold = sum(int(r[2]) for r in rows if not r[3].strip())
    average = sum(q * c for q, c in bought) / sum(q for q, _ in bought)
    cogs = (average * sold).quantize(Decimal("0.01"))
    final = Decimal(instance.expected["required_final_balances"]["Assets:Inventory"])
    opening_cost = sum(q * c for q, c in bought)
    wrong = instance.initial_ledger + _inventory_entries(cogs, opening_cost - cogs - final)
    report = verify(instance.initial_ledger, wrong, instance.expected)
    assert report.reward == 0
    assert report.layers["structural_validity"].passed
    assert not report.layers["semantic_accuracy"].passed


def test_skipping_nrv_write_down_fails():
    """Trap: post FIFO cost of sales but leave inventory at cost above NRV."""
    from decimal import Decimal

    instance = FAMILIES["inventory-costing-nrv"](112)
    cogs = Decimal(instance.expected["expected_deltas"]["Expenses:CostOfSales"])
    wrong = instance.initial_ledger + _inventory_entries(cogs, Decimal("0"))
    report = verify(instance.initial_ledger, wrong, instance.expected)
    assert report.reward == 0
    assert not report.layers["semantic_accuracy"].passed


def test_cost_of_sales_per_sale_is_equivalent():
    """Posting cost of sales per sale date instead of one month-end entry."""
    from decimal import Decimal

    instance = FAMILIES["inventory-costing-nrv"](112)
    d = instance.expected["expected_deltas"]
    cogs, write_down = Decimal(d["Expenses:CostOfSales"]), Decimal(d["Expenses:InventoryWriteDown"])
    first = (cogs / 3).quantize(Decimal("0.01"))
    split = (
        instance.initial_ledger
        + (
            '\n2026-01-12 * "Inventory" "Cost of sales, first sale"\n'
            f"  Expenses:CostOfSales  {first:.2f} USD\n"
            f"  Assets:Inventory  -{first:.2f} USD\n"
        )
        + _inventory_entries(cogs - first, write_down)
    )
    assert verify(instance.initial_ledger, split, instance.expected).reward == 1
