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


def _allowance_parts(instance):
    from decimal import Decimal

    d = instance.expected["expected_deltas"]
    write_off = -Decimal(d["Assets:AccountsReceivable"])
    adjustment = Decimal(d["Expenses:BadDebts"])
    required = -Decimal(
        instance.expected["required_final_balances"]["Assets:AllowanceForDoubtfulAccounts"]
    )
    return write_off, adjustment, required


def test_allowance_booked_in_full_fails_semantics():
    """Trap: expense the whole required allowance, ignoring the existing balance."""
    instance = FAMILIES["receivable-allowance-trueup"](108)
    write_off, _, required = _allowance_parts(instance)
    wrong = instance.initial_ledger + (
        '\n2026-01-31 * "Customer" "Write off"\n'
        f"  Assets:AllowanceForDoubtfulAccounts  {write_off:.2f} USD\n"
        f"  Assets:AccountsReceivable  -{write_off:.2f} USD\n"
        '\n2026-01-31 * "Allowance" "Record required allowance"\n'
        f"  Expenses:BadDebts  {required:.2f} USD\n"
        f"  Assets:AllowanceForDoubtfulAccounts  -{required:.2f} USD\n"
    )
    report = verify(instance.initial_ledger, wrong, instance.expected)
    assert report.reward == 0
    assert report.layers["structural_validity"].passed
    assert not report.layers["semantic_accuracy"].passed


def test_allowance_without_write_off_fails_semantics():
    """Trap: skip the approved write-off and only adjust the allowance."""
    instance = FAMILIES["receivable-allowance-trueup"](108)
    _, adjustment, _ = _allowance_parts(instance)
    wrong = instance.initial_ledger + (
        '\n2026-01-31 * "Allowance" "Adjust allowance"\n'
        f"  Expenses:BadDebts  {adjustment:.2f} USD\n"
        f"  Assets:AllowanceForDoubtfulAccounts  -{adjustment:.2f} USD\n"
    )
    report = verify(instance.initial_ledger, wrong, instance.expected)
    assert report.reward == 0
    assert not report.layers["semantic_accuracy"].passed


def test_direct_write_off_then_true_up_is_equivalent():
    """Charging the write-off to expense and then adjusting the allowance from
    its opening balance reaches the same state as writing off against it."""
    instance = FAMILIES["receivable-allowance-trueup"](108)
    write_off, adjustment, _ = _allowance_parts(instance)
    to_allowance = adjustment - write_off  # opening -> required
    equivalent = instance.initial_ledger + (
        '\n2026-01-31 * "Customer" "Irrecoverable debt written off"\n'
        f"  Expenses:BadDebts  {write_off:.2f} USD\n"
        f"  Assets:AccountsReceivable  -{write_off:.2f} USD\n"
        '\n2026-01-31 * "Allowance" "Increase allowance"\n'
        f"  Expenses:BadDebts  {to_allowance:.2f} USD\n"
        f"  Assets:AllowanceForDoubtfulAccounts  {-to_allowance:.2f} USD\n"
    )
    assert verify(instance.initial_ledger, equivalent, instance.expected).reward == 1


def _accrual_parts(instance):
    from decimal import Decimal

    d = instance.expected["expected_deltas"]
    estimate = Decimal(d["Liabilities:AccruedExpenses"])
    actual = -Decimal(d["Assets:Bank:Checking"])
    earned = Decimal(d["Liabilities:DeferredRevenue"])
    return estimate, actual, earned


def _release(earned) -> str:
    return (
        '\n2026-01-31 * "Client" "Sessions delivered"\n'
        f"  Liabilities:DeferredRevenue  {earned:.2f} USD\n"
        f"  Income:Services  -{earned:.2f} USD\n"
    )


def test_bill_without_reversing_accrual_fails_semantics():
    """Trap: book the full bill without reversing December's accrual (double count)."""
    instance = FAMILIES["accrual-deferral-reversal"](109)
    _, actual, earned = _accrual_parts(instance)
    wrong = (
        instance.initial_ledger
        + (
            '\n2026-01-15 * "Utility" "Bill paid"\n'
            f"  Expenses:Utilities  {actual:.2f} USD\n"
            f"  Assets:Bank:Checking  -{actual:.2f} USD\n"
        )
        + _release(earned)
    )
    report = verify(instance.initial_ledger, wrong, instance.expected)
    assert report.reward == 0
    assert report.layers["structural_validity"].passed
    assert not report.layers["semantic_accuracy"].passed


def test_releasing_all_deferred_revenue_fails_semantics():
    """Trap: recognize the whole prepayment instead of the sessions delivered."""
    instance = FAMILIES["accrual-deferral-reversal"](109)
    added = instance.solution_ledger[len(instance.initial_ledger) :]
    from decimal import Decimal

    _, _, earned = _accrual_parts(instance)
    balances = instance.expected["required_final_balances"]
    full = -Decimal(balances["Liabilities:DeferredRevenue"]) + earned
    wrong = instance.initial_ledger + added.replace(f"{earned:.2f} USD", f"{full:.2f} USD")
    report = verify(instance.initial_ledger, wrong, instance.expected)
    assert report.reward == 0
    assert not report.layers["semantic_accuracy"].passed


def test_settling_bill_against_accrual_is_equivalent():
    """Charging only the true-up to expense and clearing the accrual in the
    payment entry reaches the same state as reverse-then-record."""
    instance = FAMILIES["accrual-deferral-reversal"](109)
    estimate, actual, earned = _accrual_parts(instance)
    equivalent = (
        instance.initial_ledger
        + (
            '\n2026-01-15 * "Utility" "Bill paid against December accrual"\n'
            f"  Liabilities:AccruedExpenses  {estimate:.2f} USD\n"
            f"  Expenses:Utilities  {actual - estimate:.2f} USD\n"
            f"  Assets:Bank:Checking  -{actual:.2f} USD\n"
        )
        + _release(earned)
    )
    assert verify(instance.initial_ledger, equivalent, instance.expected).reward == 1


def test_forcing_ledger_to_supplier_statement_fails():
    """Trap: book every difference (goods in transit, unpresented payment) so the
    ledger equals the statement, on top of the genuine corrections."""
    instance = FAMILIES["payables-statement-recon"](110)
    statement = instance.app_files["documents/supplier_statement.md"]
    in_transit = statement.split("goods dispatched 2026-01-31) | ")[1].split(" |")[0]
    payment = instance.initial_ledger.split("Payment of invoice")[1].split(
        "Liabilities:AccountsPayable  "
    )[1]
    payment = payment.split(" USD")[0]
    forced = instance.solution_ledger + (
        '\n2026-01-31 * "Supplier" "Invoice in transit"\n'
        f"  Expenses:Materials  {in_transit} USD\n"
        f"  Liabilities:AccountsPayable  -{in_transit} USD\n"
        '\n2026-01-31 * "Supplier" "Payment not on statement"\n'
        f"  Assets:Bank:Checking  {payment} USD\n"
        f"  Liabilities:AccountsPayable  -{payment} USD\n"
    )
    report = verify(instance.initial_ledger, forced, instance.expected)
    assert report.reward == 0
    assert report.layers["structural_validity"].passed
    assert not report.layers["semantic_accuracy"].passed


def test_missing_the_transposition_fails_semantics():
    """Trap: record the credit note but miss the mis-keyed invoice."""
    instance = FAMILIES["payables-statement-recon"](110)
    added = instance.solution_ledger[len(instance.initial_ledger) :]
    credit_note_entry = added.strip("\n").split("\n\n")[0]
    wrong = instance.initial_ledger + "\n" + credit_note_entry + "\n"
    report = verify(instance.initial_ledger, wrong, instance.expected)
    assert report.reward == 0
    assert not report.layers["semantic_accuracy"].passed


def test_combined_payables_correction_is_equivalent():
    instance = FAMILIES["payables-statement-recon"](110)
    delta = instance.expected["expected_deltas"]["Liabilities:AccountsPayable"]
    combined = instance.initial_ledger + (
        '\n2026-01-31 * "Supplier" "Statement reconciliation corrections"\n'
        f"  Liabilities:AccountsPayable  {delta} USD\n"
        "  Expenses:Materials\n"
    )
    assert verify(instance.initial_ledger, combined, instance.expected).reward == 1
