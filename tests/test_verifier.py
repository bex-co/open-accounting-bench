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


def _loan_entry(expense, coupon) -> str:
    return (
        '\n2026-01-31 * "Lender" "January interest"\n'
        f"  Expenses:Interest  {expense:.2f} USD\n"
        f"  Liabilities:InterestPayable  -{coupon:.2f} USD\n"
        "  Liabilities:LoanPayable\n"
    )


def test_coupon_rate_interest_fails_amortized_cost():
    """Trap: expense only the coupon, ignoring the effective rate (issue costs
    never amortize)."""
    from decimal import Decimal

    instance = FAMILIES["loan-effective-interest"](115)
    coupon = -Decimal(instance.expected["expected_deltas"]["Liabilities:InterestPayable"])
    wrong = instance.initial_ledger + _loan_entry(coupon, coupon)
    report = verify(instance.initial_ledger, wrong, instance.expected)
    assert report.reward == 0
    assert report.layers["structural_validity"].passed
    assert not report.layers["semantic_accuracy"].passed


def test_effective_rate_on_face_value_fails():
    """Trap: apply the effective rate to face value instead of carrying amount."""
    from decimal import Decimal

    instance = FAMILIES["loan-effective-interest"](115)
    doc = instance.app_files["documents/loan_agreement.md"]
    face = Decimal(doc.split("face value USD ")[1].split(";")[0])
    rate = Decimal(doc.split("cash flows): ")[1].split("%")[0]) / 100
    coupon = -Decimal(instance.expected["expected_deltas"]["Liabilities:InterestPayable"])
    wrong = instance.initial_ledger + _loan_entry((face * rate).quantize(Decimal("0.01")), coupon)
    report = verify(instance.initial_ledger, wrong, instance.expected)
    assert report.reward == 0
    assert not report.layers["semantic_accuracy"].passed


def test_coupon_and_amortization_entries_are_equivalent():
    from decimal import Decimal

    instance = FAMILIES["loan-effective-interest"](115)
    d = instance.expected["expected_deltas"]
    coupon = -Decimal(d["Liabilities:InterestPayable"])
    amortization = -Decimal(d["Liabilities:LoanPayable"])
    split = instance.initial_ledger + (
        '\n2026-01-31 * "Lender" "Coupon accrual"\n'
        f"  Expenses:Interest  {coupon:.2f} USD\n"
        f"  Liabilities:InterestPayable  -{coupon:.2f} USD\n"
        '\n2026-01-31 * "Lender" "Amortize issue costs"\n'
        f"  Expenses:Interest  {amortization:.2f} USD\n"
        f"  Liabilities:LoanPayable  -{amortization:.2f} USD\n"
    )
    assert verify(instance.initial_ledger, split, instance.expected).reward == 1
