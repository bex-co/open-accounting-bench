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


def _disposal_parts(instance):
    from decimal import Decimal

    d = instance.expected["expected_deltas"]
    return (
        Decimal(d["Expenses:Depreciation"]),
        Decimal(d["Assets:AccumulatedDepreciation"]),
        -Decimal(d["Assets:Equipment"]),
        Decimal(d["Assets:Bank:Checking"]),
    )


def test_disposal_without_final_month_depreciation_fails():
    """Trap: compute the gain on last year-end's carrying amount."""
    instance = FAMILIES["ppe-disposal"](111)
    _, acc_open, cost, proceeds = _disposal_parts(instance)
    gain = proceeds - (cost - acc_open)
    wrong = instance.initial_ledger + (
        '\n2026-01-20 * "Buyer" "Disposal"\n'
        f"  Assets:Bank:Checking  {proceeds:.2f} USD\n"
        f"  Assets:AccumulatedDepreciation  {acc_open:.2f} USD\n"
        f"  Assets:Equipment  -{cost:.2f} USD\n"
        f"  Income:GainLossOnDisposal  {-gain:.2f} USD\n"
    )
    report = verify(instance.initial_ledger, wrong, instance.expected)
    assert report.reward == 0
    assert report.layers["structural_validity"].passed
    assert not report.layers["semantic_accuracy"].passed


def test_proceeds_booked_as_income_fails():
    """Trap: treat the sale price as income and leave the asset on the books."""
    instance = FAMILIES["ppe-disposal"](111)
    _, _, _, proceeds = _disposal_parts(instance)
    wrong = instance.initial_ledger + (
        '\n2026-01-20 * "Buyer" "Sale of equipment"\n'
        f"  Assets:Bank:Checking  {proceeds:.2f} USD\n"
        f"  Income:GainLossOnDisposal  -{proceeds:.2f} USD\n"
    )
    report = verify(instance.initial_ledger, wrong, instance.expected)
    assert report.reward == 0
    assert not report.layers["semantic_accuracy"].passed


def test_single_disposal_entry_with_depreciation_is_equivalent():
    instance = FAMILIES["ppe-disposal"](111)
    monthly, acc_open, cost, proceeds = _disposal_parts(instance)
    gain = proceeds - (cost - acc_open - monthly)
    combined = instance.initial_ledger + (
        '\n2026-01-20 * "Buyer" "Depreciate to disposal and derecognize"\n'
        f"  Expenses:Depreciation  {monthly:.2f} USD\n"
        f"  Assets:AccumulatedDepreciation  {acc_open:.2f} USD\n"
        f"  Assets:Equipment  -{cost:.2f} USD\n"
        f"  Assets:Bank:Checking  {proceeds:.2f} USD\n"
        f"  Income:GainLossOnDisposal  {-gain:.2f} USD\n"
    )
    assert verify(instance.initial_ledger, combined, instance.expected).reward == 1


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


def _revenue_entry(hardware, support) -> str:
    return (
        '\n2026-01-31 * "Customer" "January revenue"\n'
        f"  Liabilities:ContractLiability  {hardware + support:.2f} USD\n"
        f"  Income:ProductRevenue  -{hardware:.2f} USD\n"
        f"  Income:SupportRevenue  -{support:.2f} USD\n"
    )


def test_allocating_on_invoice_lines_fails():
    """Trap: use the invoice's line prices instead of standalone selling prices."""
    from decimal import Decimal

    instance = FAMILIES["revenue-bundle-allocation"](113)
    lines = instance.app_files["documents/contract.md"].split("## Invoice lines")[1]
    amounts = [Decimal(x.split("USD ")[1]) for x in lines.splitlines() if "USD" in x]
    wrong = instance.initial_ledger + _revenue_entry(
        amounts[0], (amounts[1] / 12).quantize(Decimal("0.01"))
    )
    report = verify(instance.initial_ledger, wrong, instance.expected)
    assert report.reward == 0
    assert report.layers["structural_validity"].passed
    assert not report.layers["semantic_accuracy"].passed


def test_recognizing_whole_support_term_up_front_fails():
    """Trap: recognize all twelve support months in January."""
    from decimal import Decimal

    instance = FAMILIES["revenue-bundle-allocation"](113)
    d = instance.expected["expected_deltas"]
    hardware = -Decimal(d["Income:ProductRevenue"])
    support_year = -Decimal(d["Income:SupportRevenue"]) * 12
    wrong = instance.initial_ledger + _revenue_entry(hardware, support_year)
    report = verify(instance.initial_ledger, wrong, instance.expected)
    assert report.reward == 0
    assert not report.layers["semantic_accuracy"].passed


def test_separate_entries_per_obligation_are_equivalent():
    from decimal import Decimal

    instance = FAMILIES["revenue-bundle-allocation"](113)
    d = instance.expected["expected_deltas"]
    hardware, support = -Decimal(d["Income:ProductRevenue"]), -Decimal(d["Income:SupportRevenue"])
    split = instance.initial_ledger + (
        '\n2026-01-02 * "Customer" "Hardware delivered"\n'
        f"  Liabilities:ContractLiability  {hardware:.2f} USD\n"
        f"  Income:ProductRevenue  -{hardware:.2f} USD\n"
        '\n2026-01-31 * "Customer" "Support, January"\n'
        f"  Liabilities:ContractLiability  {support:.2f} USD\n"
        f"  Income:SupportRevenue  -{support:.2f} USD\n"
    )
    assert verify(instance.initial_ledger, split, instance.expected).reward == 1


def test_clearing_suspense_to_one_plausible_account_fails():
    """Trap: zero the clearing account against sales in one entry, leaving the
    transposed rent uncorrected. Balanced, and the suspense balance hits zero."""
    from decimal import Decimal

    instance = FAMILIES["suspense-clearance"](114)
    clear = Decimal(instance.expected["expected_deltas"]["Assets:Suspense"])
    wrong = instance.initial_ledger + (
        '\n2026-01-31 * "Controller" "Clear suspense"\n'
        f"  Assets:Suspense  {clear:.2f} USD\n"
        f"  Income:Sales  {-clear:.2f} USD\n"
    )
    report = verify(instance.initial_ledger, wrong, instance.expected)
    assert report.reward == 0
    assert report.layers["structural_validity"].passed
    assert not report.layers["semantic_accuracy"].passed


def test_single_suspense_clearing_entry_is_equivalent():
    instance = FAMILIES["suspense-clearance"](114)
    d = instance.expected["expected_deltas"]
    combined = instance.initial_ledger + (
        '\n2026-01-31 * "Controller" "Correct import errors and clear suspense"\n'
        f"  Assets:Suspense  {d['Assets:Suspense']} USD\n"
        f"  Expenses:Rent  {d['Expenses:Rent']} USD\n"
        f"  Income:Sales  {d['Income:Sales']} USD\n"
    )
    assert verify(instance.initial_ledger, combined, instance.expected).reward == 1


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


def _entry(date, payee, postings) -> str:
    lines = [f'\n{date} * "{payee}" "Attempt"']
    lines += [f"  {account}  {amount:.2f} USD" for account, amount in postings]
    return "\n".join(lines) + "\n"


def _deltas(instance):
    from decimal import Decimal

    return {k: Decimal(v) for k, v in instance.expected["expected_deltas"].items()}


def _assert_semantic_trap(instance, wrong):
    report = verify(instance.initial_ledger, wrong, instance.expected)
    assert report.reward == 0
    assert report.layers["structural_validity"].passed
    assert not report.layers["semantic_accuracy"].passed


def test_perpetual_sale_without_cost_of_goods_fails():
    """Trap: record revenue only, leaving inventory untouched."""
    instance = FAMILIES["perpetual-sale-with-cost"](116)
    d = _deltas(instance)
    date = instance.expected["expected_period"][0]
    revenue = d["Assets:AccountsReceivable"]
    wrong = instance.initial_ledger + _entry(
        date,
        "Customer",
        [("Assets:AccountsReceivable", revenue), ("Income:Sales", -revenue)],
    )
    _assert_semantic_trap(instance, wrong)


def test_restocking_returns_at_selling_price_fails():
    """Trap: put returned goods back into inventory at selling price."""
    instance = FAMILIES["sales-return-restock"](117)
    d = _deltas(instance)
    refund = d["Income:SalesReturnsAndAllowances"]
    assert d["Assets:Inventory"] != refund  # cost < selling price by construction
    wrong = instance.initial_ledger + _entry(
        "2026-01-20",
        "Customer",
        [
            ("Income:SalesReturnsAndAllowances", refund),
            ("Assets:AccountsReceivable", -refund),
            ("Assets:Inventory", refund),
            ("Expenses:CostOfSales", -refund),
        ],
    )
    _assert_semantic_trap(instance, wrong)


def test_expensing_supplies_on_hand_fails():
    """Trap: expense the counted remainder instead of the amount used."""
    from decimal import Decimal

    instance = FAMILIES["supplies-adjustment"](118)
    on_hand = Decimal(instance.expected["required_final_balances"]["Assets:Supplies"])
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Adjustment",
        [("Expenses:OfficeSupplies", on_hand), ("Assets:Supplies", -on_hand)],
    )
    _assert_semantic_trap(instance, wrong)


def test_accruing_full_week_of_wages_fails():
    """Trap: accrue the full 5-day week, not the unpaid days since payday."""
    import re
    from decimal import Decimal

    instance = FAMILIES["accrued-wages-adjustment"](119)
    days = int(re.search(r"worked (\d+) day", instance.app_files["documents/payroll_note.md"])[1])
    amount = _deltas(instance)["Expenses:Wages"]
    full_week = (amount / days * 5).quantize(Decimal("0.01"))
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Payroll",
        [("Expenses:Wages", full_week), ("Liabilities:WagesPayable", -full_week)],
    )
    _assert_semantic_trap(instance, wrong)


def test_depreciating_full_cost_fails():
    """Trap: ignore residual value in the straight-line charge."""
    import re
    from decimal import Decimal

    instance = FAMILIES["straight-line-depreciation"](120)
    doc = instance.app_files["documents/asset_register.md"]
    cost = Decimal(re.search(r"Cost USD ([\d]+\.[\d]{2})", doc)[1])
    life = int(re.search(r"life (\d+) years", doc)[1])
    wrong_amount = (cost / (life * 12)).quantize(Decimal("0.01"))
    assert wrong_amount != _deltas(instance)["Expenses:Depreciation"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Depreciation",
        [
            ("Expenses:Depreciation", wrong_amount),
            ("Assets:AccumulatedDepreciation", -wrong_amount),
        ],
    )
    _assert_semantic_trap(instance, wrong)


def test_accruing_full_note_interest_fails():
    """Trap: accrue all 90 days of note interest in January."""
    instance = FAMILIES["note-interest-accrual"](121)
    interest = _deltas(instance)["Assets:InterestReceivable"] * 3
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Customer",
        [("Assets:InterestReceivable", interest), ("Income:Interest", -interest)],
    )
    _assert_semantic_trap(instance, wrong)


def test_expensing_net_pay_fails():
    """Trap: record net pay as the expense, skipping withholdings."""
    instance = FAMILIES["payroll-withholdings"](122)
    net = -_deltas(instance)["Liabilities:WagesPayable"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Payroll",
        [("Expenses:Wages", net), ("Liabilities:WagesPayable", -net)],
    )
    _assert_semantic_trap(instance, wrong)


def test_bond_coupon_only_interest_fails():
    """Trap: expense the coupon and never amortize the discount."""
    instance = FAMILIES["bond-discount-amortization"](123)
    coupon = -_deltas(instance)["Liabilities:InterestPayable"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Bondholders",
        [("Expenses:Interest", coupon), ("Liabilities:InterestPayable", -coupon)],
    )
    _assert_semantic_trap(instance, wrong)


def test_crediting_full_proceeds_to_common_stock_fails():
    """Trap: credit common stock with the whole issue price, ignoring par/APIC."""
    instance = FAMILIES["equity-issue-above-par"](128)
    d = _deltas(instance)
    proceeds = d["Assets:Bank:Checking"]
    date = instance.expected["expected_period"][0]
    wrong = instance.initial_ledger + _entry(
        date,
        "Investors",
        [("Assets:Bank:Checking", proceeds), ("Equity:CommonStock", -proceeds)],
    )
    _assert_semantic_trap(instance, wrong)


def test_paying_dividend_on_declaration_date_fails():
    """Trap: pay cash in January instead of recording the declared liability."""
    instance = FAMILIES["cash-dividend-declaration"](129)
    total = _deltas(instance)["Equity:RetainedEarnings"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-15",
        "Board",
        [("Equity:RetainedEarnings", total), ("Assets:Bank:Checking", -total)],
    )
    _assert_semantic_trap(instance, wrong)


def test_retiring_repurchased_shares_fails_under_cost_method():
    """Trap: debit common stock at repurchase cost (retirement treatment)."""
    instance = FAMILIES["treasury-stock-repurchase"](130)
    cost = _deltas(instance)["Equity:TreasuryStock"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-18",
        "Broker",
        [("Equity:CommonStock", cost), ("Assets:Bank:Checking", -cost)],
    )
    _assert_semantic_trap(instance, wrong)


def test_closing_revenue_only_fails():
    """Trap: transfer gross revenue to retained earnings, expenses left open."""
    instance = FAMILIES["closing-entries-income-summary"](131)
    revenue = _deltas(instance)["Income:Sales"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Closing",
        [("Income:Sales", revenue), ("Equity:RetainedEarnings", -revenue)],
    )
    _assert_semantic_trap(instance, wrong)


def test_applying_actual_overhead_fails():
    """Trap: apply January's actual overhead instead of the predetermined rate."""
    import re
    from decimal import Decimal

    instance = FAMILIES["job-overhead-applied"](132)
    doc = instance.app_files["documents/job_cost_sheet.md"]
    actual = Decimal(re.search(r"Actual manufacturing overhead.*USD ([\d]+\.[\d]{2})", doc)[1])
    assert actual != _deltas(instance)["Assets:WorkInProcess"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Job",
        [("Assets:WorkInProcess", actual), ("Expenses:ManufacturingOverhead", -actual)],
    )
    _assert_semantic_trap(instance, wrong)


def test_dishonored_note_principal_only_fails():
    """Trap: charge the maker principal only, dropping the interest claim."""
    instance = FAMILIES["note-dishonored"](133)
    principal = -_deltas(instance)["Assets:NotesReceivable"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Customer",
        [("Assets:AccountsReceivable", principal), ("Assets:NotesReceivable", -principal)],
    )
    _assert_semantic_trap(instance, wrong)


def test_capitalizing_whole_machine_invoice_fails():
    """Trap: capitalize training and the service plan into the machine cost."""
    instance = FAMILIES["capitalized-cost-bundle"](141)
    d = _deltas(instance)
    total = -d["Assets:Bank:Checking"]
    date = instance.expected["expected_period"][0]
    wrong = instance.initial_ledger + _entry(
        date,
        "Supplier",
        [("Assets:Equipment", total), ("Assets:Bank:Checking", -total)],
    )
    _assert_semantic_trap(instance, wrong)


def test_employer_taxes_deducted_from_wages_fails():
    """Trap: charge employer taxes against wages expense (employee treatment)."""
    instance = FAMILIES["employer-payroll-taxes"](142)
    d = _deltas(instance)
    total = d["Expenses:PayrollTaxes"]
    fica = -d["Liabilities:FICAPayable"]
    futa = -d["Liabilities:UnemploymentTaxPayable"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Payroll",
        [
            ("Expenses:Wages", total),
            ("Liabilities:FICAPayable", -fica),
            ("Liabilities:UnemploymentTaxPayable", -futa),
        ],
    )
    _assert_semantic_trap(instance, wrong)


def test_reclassifying_whole_note_balance_fails():
    """Trap: move the entire note balance to current liabilities."""
    instance = FAMILIES["current-portion-reclass"](143)
    final_lt = instance.expected["required_final_balances"]["Liabilities:LongTermNotePayable"]
    from decimal import Decimal

    annual = _deltas(instance)["Liabilities:LongTermNotePayable"]
    whole = annual - Decimal(final_lt)
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Reporting",
        [
            ("Liabilities:LongTermNotePayable", whole),
            ("Liabilities:CurrentPortionOfLongTermDebt", -whole),
        ],
    )
    _assert_semantic_trap(instance, wrong)


def test_freight_buried_in_purchases_fails():
    """Trap: debit freight-in to purchases instead of its own account."""
    instance = FAMILIES["periodic-purchase-with-freight"](144)
    d = _deltas(instance)
    total = -d["Liabilities:AccountsPayable"]
    date = instance.expected["expected_period"][0]
    wrong = instance.initial_ledger + _entry(
        date,
        "Supplier",
        [("Expenses:Purchases", total), ("Liabilities:AccountsPayable", -total)],
    )
    _assert_semantic_trap(instance, wrong)


def test_percent_of_sales_true_up_fails():
    """Trap: aging-style true-up crediting only the excess over the balance."""
    instance = FAMILIES["bad-debt-percent-of-sales"](145)
    from decimal import Decimal

    expense = _deltas(instance)["Expenses:BadDebts"]
    existing = (
        -Decimal(
            instance.expected["required_final_balances"]["Assets:AllowanceForDoubtfulAccounts"]
        )
        - expense
    )
    shortfall = expense - existing
    if shortfall <= 0:
        shortfall = expense / 2
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Allowance",
        [
            ("Expenses:BadDebts", shortfall),
            ("Assets:AllowanceForDoubtfulAccounts", -shortfall),
        ],
    )
    _assert_semantic_trap(instance, wrong)


def test_discount_left_in_receivable_fails():
    """Trap: credit receivables only with cash received (discount stranded)."""
    instance = FAMILIES["cash-discount-receipt"](146)
    net = _deltas(instance)["Assets:Bank:Checking"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-09",
        "Customer",
        [("Assets:Bank:Checking", net), ("Assets:AccountsReceivable", -net)],
    )
    _assert_semantic_trap(instance, wrong)


def test_expensing_equipment_in_narrative_set_fails():
    """Trap: expense the multi-year equipment in the narrative transaction set."""
    instance = FAMILIES["narrative-multi-transactions"](154)
    added = instance.solution_ledger[len(instance.initial_ledger) :]
    wrong = instance.initial_ledger + added.replace("  Assets:Equipment", "  Expenses:Repairs")
    _assert_semantic_trap(instance, wrong)


def test_units_depreciation_ignoring_residual_fails():
    """Trap: per-unit rate on full cost, ignoring residual value."""
    import re
    from decimal import Decimal

    instance = FAMILIES["units-of-production-depreciation"](155)
    doc = instance.app_files["documents/asset_register.md"]
    cost = Decimal(re.search(r"Cost USD ([\d]+\.[\d]{2})", doc)[1])
    total = int(re.search(r"total output: (\d+)", doc)[1])
    month = int(re.search(r"January output: (\d+)", doc)[1])
    wrong_amount = (cost / total * month).quantize(Decimal("0.01"))
    assert wrong_amount != _deltas(instance)["Expenses:Depreciation"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Depreciation",
        [
            ("Expenses:Depreciation", wrong_amount),
            ("Assets:AccumulatedDepreciation", -wrong_amount),
        ],
    )
    _assert_semantic_trap(instance, wrong)


def test_expensing_warranty_claims_paid_fails():
    """Trap: cash-basis warranty (expense claims paid, no new estimate)."""
    instance = FAMILIES["warranty-provision-and-claims"](156)
    claims = -_deltas(instance)["Assets:Bank:Checking"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-25",
        "Customers",
        [("Expenses:Warranty", claims), ("Assets:Bank:Checking", -claims)],
    )
    _assert_semantic_trap(instance, wrong)


def test_sales_tax_as_revenue_fails():
    """Trap: record the tax-inclusive receipt as sales revenue."""
    instance = FAMILIES["sales-tax-collection"](157)
    d = _deltas(instance)
    gross = d["Assets:Bank:Checking"]
    date = instance.expected["expected_period"][0]
    wrong = instance.initial_ledger + _entry(
        date,
        "Register",
        [("Assets:Bank:Checking", gross), ("Income:Sales", -gross)],
    )
    _assert_semantic_trap(instance, wrong)


def test_petty_replenish_receipts_only_fails():
    """Trap: replenish only the receipts and ignore the cash shortage."""
    instance = FAMILIES["petty-cash-replenishment"](158)
    d = _deltas(instance)
    receipts = d["Expenses:OfficeSupplies"] + d["Expenses:Postage"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Petty cash",
        [
            ("Expenses:OfficeSupplies", d["Expenses:OfficeSupplies"]),
            ("Expenses:Postage", d["Expenses:Postage"]),
            ("Assets:Bank:Checking", -receipts),
        ],
    )
    _assert_semantic_trap(instance, wrong)


def test_stock_dividend_at_par_only_fails():
    """Trap: capitalize a small stock dividend at par (large-dividend rule)."""
    instance = FAMILIES["small-stock-dividend"](159)
    par_total = -_deltas(instance)["Equity:CommonStock"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-20",
        "Board",
        [("Equity:RetainedEarnings", par_total), ("Equity:CommonStock", -par_total)],
    )
    _assert_semantic_trap(instance, wrong)


def test_note_payment_without_interest_fails():
    """Trap: pay principal only at maturity, omitting the month's interest."""
    instance = FAMILIES["short-term-note-payment"](168)
    principal = _deltas(instance)["Liabilities:NotesPayable"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Bank",
        [("Liabilities:NotesPayable", principal), ("Assets:Bank:Checking", -principal)],
    )
    _assert_semantic_trap(instance, wrong)


def test_card_sale_at_net_deposit_fails():
    """Trap: record the net card deposit as sales (fee netted away)."""
    instance = FAMILIES["credit-card-sale-fee"](169)
    net = _deltas(instance)["Assets:Bank:Checking"]
    date = instance.expected["expected_period"][0]
    wrong = instance.initial_ledger + _entry(
        date,
        "Card processor",
        [("Assets:Bank:Checking", net), ("Income:Sales", -net)],
    )
    _assert_semantic_trap(instance, wrong)


def test_patent_amortized_over_legal_life_fails():
    """Trap: amortize over the longer legal life instead of useful life."""
    import re
    from decimal import Decimal

    instance = FAMILIES["patent-amortization"](170)
    doc = instance.app_files["documents/patent.md"]
    cost = Decimal(re.search(r"Cost: USD ([\d]+\.[\d]{2})", doc)[1])
    legal = int(re.search(r"Legal life remaining: (\d+) years", doc)[1])
    wrong_amount = (cost / (legal * 12)).quantize(Decimal("0.01"))
    assert wrong_amount != _deltas(instance)["Expenses:Amortization"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Amortization",
        [
            ("Expenses:Amortization", wrong_amount),
            ("Assets:AccumulatedAmortization", -wrong_amount),
        ],
    )
    _assert_semantic_trap(instance, wrong)


def test_accruing_remote_contingency_fails():
    """Trap: accrue the remote claim as well as the probable one."""
    import re
    from decimal import Decimal

    instance = FAMILIES["loss-contingency-accrual"](171)
    doc = instance.app_files["documents/litigation_status.md"]
    remote = Decimal(re.search(r"amount claimed is USD ([\d]+\.[\d]{2})", doc)[1])
    wrong = instance.solution_ledger + _entry(
        "2026-01-31",
        "Counsel",
        [
            ("Expenses:LitigationLoss", remote),
            ("Liabilities:EstimatedLitigationLiability", -remote),
        ],
    )
    _assert_semantic_trap(instance, wrong)


def test_bond_liability_at_proceeds_fails():
    """Trap: record bonds payable at proceeds with no premium split."""
    instance = FAMILIES["bond-issued-at-premium"](172)
    proceeds = _deltas(instance)["Assets:Bank:Checking"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-01",
        "Underwriter",
        [("Assets:Bank:Checking", proceeds), ("Liabilities:BondsPayable", -proceeds)],
    )
    _assert_semantic_trap(instance, wrong)


def test_closing_drawings_to_income_summary_fails():
    """Trap: close drawings through income summary (as if an expense)."""
    instance = FAMILIES["closing-drawing-account"](173)
    drawn = _deltas(instance)["Equity:OwnerCapital"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Closing",
        [("Equity:IncomeSummary", drawn), ("Equity:OwnerDrawing", -drawn)],
    )
    _assert_semantic_trap(instance, wrong)


def test_trading_gain_routed_to_sales_fails():
    """Trap: credit the unrealized trading gain to sales revenue."""
    instance = FAMILIES["trading-securities-fair-value"](174)
    gain = _deltas(instance)["Assets:TradingSecurities"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Broker",
        [("Assets:TradingSecurities", gain), ("Income:Sales", -gain)],
    )
    _assert_semantic_trap(instance, wrong)


def test_shrinkage_at_selling_price_fails():
    """Trap: write shrinkage off at selling price instead of cost."""
    import re
    from decimal import Decimal

    instance = FAMILIES["inventory-shrinkage-adjustment"](181)
    doc = instance.app_files["documents/inventory_count.md"]
    recorded = int(re.search(r"records: (\d+) units", doc)[1])
    counted = int(re.search(r"Physical count: (\d+) units", doc)[1])
    price = Decimal(re.search(r"selling price USD ([\d]+\.[\d]{2})", doc)[1])
    wrong_amount = (recorded - counted) * price
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Count",
        [("Expenses:CostOfSales", wrong_amount), ("Assets:Inventory", -wrong_amount)],
    )
    _assert_semantic_trap(instance, wrong)


def test_purchase_return_at_selling_price_fails():
    """Trap: credit inventory at selling price on a purchase return."""
    import re
    from decimal import Decimal

    instance = FAMILIES["purchase-return-perpetual"](182)
    doc = instance.app_files["documents/return_memo.md"]
    returned = int(re.search(r"\n(\d+) of the", doc)[1])
    price = Decimal(re.search(r"would have sold for\s+USD ([\d]+\.[\d]{2})", doc)[1])
    wrong_amount = returned * price
    wrong = instance.initial_ledger + _entry(
        "2026-01-14",
        "Supplier",
        [("Liabilities:AccountsPayable", wrong_amount), ("Assets:Inventory", -wrong_amount)],
    )
    _assert_semantic_trap(instance, wrong)


def test_overhead_treated_as_overapplied_fails():
    """Trap: reverse the underapplied-overhead closing entry."""
    instance = FAMILIES["overhead-variance-disposition"](183)
    under = _deltas(instance)["Expenses:CostOfSales"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Overhead",
        [("Expenses:ManufacturingOverhead", under), ("Expenses:CostOfSales", -under)],
    )
    _assert_semantic_trap(instance, wrong)


def test_releasing_full_advance_fails():
    """Trap: recognize the whole 4-month advance in January."""
    instance = FAMILIES["unearned-revenue-release"](184)
    monthly = _deltas(instance)["Liabilities:DeferredRevenue"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Client",
        [("Liabilities:DeferredRevenue", monthly * 4), ("Income:Services", -monthly * 4)],
    )
    _assert_semantic_trap(instance, wrong)


def test_bond_loss_measured_against_face_fails():
    """Trap: loss = call price - face, abandoning the unamortized discount."""
    instance = FAMILIES["bond-early-retirement"](185)
    d = _deltas(instance)
    face = d["Liabilities:BondsPayable"]
    call = -d["Assets:Bank:Checking"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-15",
        "Bondholders",
        [
            ("Liabilities:BondsPayable", face),
            ("Expenses:LossOnBondRetirement", call - face),
            ("Assets:Bank:Checking", -call),
        ],
    )
    _assert_semantic_trap(instance, wrong)


def test_fvoci_gain_to_income_fails():
    """Trap: credit the FVOCI gain to income (trading treatment)."""
    instance = FAMILIES["fvoci-fair-value-adjustment"](186)
    gain = _deltas(instance)["Assets:FVOCIInvestments"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Broker",
        [("Assets:FVOCIInvestments", gain), ("Income:UnrealizedGainLoss", -gain)],
    )
    _assert_semantic_trap(instance, wrong)


def test_basket_split_evenly_fails():
    """Trap: split the lump sum 50/50 instead of by relative appraised values."""
    instance = FAMILIES["basket-purchase-allocation"](187)
    lump = -_deltas(instance)["Assets:Bank:Checking"]
    half = lump / 2
    date = instance.expected["expected_period"][0]
    wrong = instance.initial_ledger + _entry(
        date,
        "Seller",
        [("Assets:Land", half), ("Assets:Building", half), ("Assets:Bank:Checking", -lump)],
    )
    _assert_semantic_trap(instance, wrong)


def test_treasury_reissuance_gain_to_income_fails():
    """Trap: recognize the excess over treasury cost as income."""
    instance = FAMILIES["treasury-stock-reissuance"](194)
    d = _deltas(instance)
    proceeds = d["Assets:Bank:Checking"]
    cost = -d["Equity:TreasuryStock"]
    excess = -d["Equity:AdditionalPaidInCapital"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-20",
        "Investors",
        [
            ("Assets:Bank:Checking", proceeds),
            ("Equity:TreasuryStock", -cost),
            ("Income:Sales", -excess),
        ],
    )
    _assert_semantic_trap(instance, wrong)


def test_lease_treated_as_rent_expense_fails():
    """Trap: debit rent expense instead of recognizing a right-of-use asset."""
    instance = FAMILIES["lease-initial-recognition"](195)
    present_value = _deltas(instance)["Assets:RightOfUseAsset"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-01",
        "Lessor",
        [("Expenses:Rent", present_value), ("Liabilities:LeaseLiability", -present_value)],
    )
    _assert_semantic_trap(instance, wrong)


def test_fx_adjustment_to_inventory_fails():
    """Trap: remeasure the nonmonetary inventory along with the payable."""
    instance = FAMILIES["fx-payable-remeasurement"](196)
    loss = _deltas(instance)["Expenses:ForeignExchangeLoss"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Supplier",
        [("Assets:Inventory", loss), ("Liabilities:AccountsPayable", -loss)],
    )
    _assert_semantic_trap(instance, wrong)


def test_capitalizing_all_project_costs_fails():
    """Trap: capitalize research, pre-feasibility work, and training too."""
    instance = FAMILIES["development-cost-capitalization"](197)
    total = -_deltas(instance)["Assets:Bank:Checking"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Project",
        [("Assets:DevelopmentCosts", total), ("Assets:Bank:Checking", -total)],
    )
    _assert_semantic_trap(instance, wrong)


def test_inventory_error_through_current_cogs_fails():
    """Trap: run a prior-period inventory correction through current COGS."""
    instance = FAMILIES["inventory-error-correction"](198)
    error = _deltas(instance)["Assets:Inventory"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-01",
        "Audit",
        [("Assets:Inventory", error), ("Expenses:CostOfSales", -error)],
    )
    _assert_semantic_trap(instance, wrong)


def test_impairment_to_lower_measure_fails():
    """Trap: write down to the LOWER of FVLCD and value in use."""
    import re
    from decimal import Decimal

    instance = FAMILIES["long-lived-asset-impairment"](199)
    doc = instance.app_files["documents/impairment_review.md"]
    carrying = Decimal(re.search(r"carrying amount USD ([\d]+\.[\d]{2})", doc)[1])
    fvlcd = Decimal(re.search(r"costs of disposal: USD ([\d]+\.[\d]{2})", doc)[1])
    viu = Decimal(re.search(r"Value in use \(discounted\): USD ([\d]+\.[\d]{2})", doc)[1])
    wrong_amount = carrying - min(fvlcd, viu)
    assert wrong_amount != _deltas(instance)["Expenses:ImpairmentLoss"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Impairment review",
        [
            ("Expenses:ImpairmentLoss", wrong_amount),
            ("Assets:AccumulatedImpairment", -wrong_amount),
        ],
    )
    _assert_semantic_trap(instance, wrong)


def test_goodwill_pushed_into_equipment_fails():
    """Trap: allocate the acquisition excess to equipment, not goodwill."""
    instance = FAMILIES["business-combination-acquisition"](208)
    added = instance.solution_ledger[len(instance.initial_ledger) :]
    wrong = instance.initial_ledger + added.replace("  Assets:Goodwill", "  Assets:Equipment")
    _assert_semantic_trap(instance, wrong)


def test_eliminating_only_parent_share_fails():
    """Trap: eliminate only 80% of the intercompany sale (ownership share)."""
    from decimal import Decimal

    instance = FAMILIES["consolidation-intercompany-elimination"](209)
    d = _deltas(instance)
    factor = Decimal("0.8")
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Consolidation",
        [
            ("Income:Sales", d["Income:Sales"] * factor),
            ("Expenses:CostOfSales", d["Expenses:CostOfSales"] * factor),
            ("Assets:Inventory", d["Assets:Inventory"] * factor),
        ],
    )
    _assert_semantic_trap(instance, wrong)


def test_held_for_sale_without_writedown_fails():
    """Trap: reclassify the asset at carrying amount, ignoring FVLCS."""
    instance = FAMILIES["held-for-sale-measurement"](210)
    d = _deltas(instance)
    acc_dep = d["Assets:AccumulatedDepreciation"]
    carrying = d["Assets:AssetHeldForSale"] + d["Expenses:ImpairmentLoss"]
    cost = -d["Assets:Equipment"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-20",
        "Management",
        [
            ("Assets:AccumulatedDepreciation", acc_dep),
            ("Assets:AssetHeldForSale", carrying),
            ("Assets:Equipment", -cost),
        ],
    )
    _assert_semantic_trap(instance, wrong)


def test_expensing_whole_share_award_fails():
    """Trap: expense the full grant-date fair value in the first month."""
    import re
    from decimal import Decimal

    instance = FAMILIES["share-based-compensation-monthly"](211)
    doc = instance.app_files["documents/award_grant.md"]
    total = Decimal(re.search(r"fair value\s+USD ([\d]+\.[\d]{2})", doc)[1])
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Compensation committee",
        [
            ("Expenses:ShareBasedCompensation", total),
            ("Equity:AdditionalPaidInCapital", -total),
        ],
    )
    _assert_semantic_trap(instance, wrong)


def test_revaluation_uplift_to_income_fails():
    """Trap: credit an upward revaluation to profit or loss, not OCI."""
    instance = FAMILIES["asset-revaluation-surplus"](212)
    added = instance.solution_ledger[len(instance.initial_ledger) :]
    wrong = instance.initial_ledger + added.replace(
        "  Equity:RevaluationSurplus", "  Income:GainLossOnDisposal"
    )
    _assert_semantic_trap(instance, wrong)


def test_bad_debt_recovery_as_revenue_fails():
    """Trap: credit a recovery of a write-off directly to revenue."""
    instance = FAMILIES["written-off-receivable-recovery"](213)
    recovery = _deltas(instance)["Assets:Bank:Checking"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-18",
        "Customer",
        [("Assets:Bank:Checking", recovery), ("Income:Sales", -recovery)],
    )
    _assert_semantic_trap(instance, wrong)


def test_conditional_grant_as_revenue_fails():
    """Trap: recognize conditional grant cash as contribution revenue."""
    instance = FAMILIES["nfp-conditional-vs-unconditional"](214)
    added = instance.solution_ledger[len(instance.initial_ledger) :]
    wrong = instance.initial_ledger + added.replace(
        "  Liabilities:RefundableAdvance",
        "  Income:ContributionRevenueWithDonorRestrictions",
    )
    _assert_semantic_trap(instance, wrong)


def test_recognizing_whole_government_grant_fails():
    """Trap: release the entire asset grant to income in month one."""
    from decimal import Decimal

    instance = FAMILIES["government-grant-release"](222)
    monthly = _deltas(instance)["Liabilities:DeferredGovernmentGrant"]
    remaining = -Decimal(
        instance.expected["required_final_balances"]["Liabilities:DeferredGovernmentGrant"]
    )
    total = monthly + remaining
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Government grant",
        [("Liabilities:DeferredGovernmentGrant", total), ("Income:GovernmentGrant", -total)],
    )
    _assert_semantic_trap(instance, wrong)


def test_investment_property_gain_to_oci_fails():
    """Trap: route an IAS 40 fair-value gain to OCI like a PPE revaluation."""
    instance = FAMILIES["investment-property-fair-value"](223)
    added = instance.solution_ledger[len(instance.initial_ledger) :]
    wrong = instance.initial_ledger + added.replace(
        "  Income:UnrealizedGainLoss", "  Equity:AccumulatedOtherComprehensiveIncome"
    )
    _assert_semantic_trap(instance, wrong)


def test_goodwill_impairment_charged_to_equipment_fails():
    """Trap: allocate a CGU impairment to equipment before goodwill."""
    instance = FAMILIES["goodwill-impairment"](224)
    added = instance.solution_ledger[len(instance.initial_ledger) :]
    wrong = instance.initial_ledger + added.replace("  Assets:Goodwill", "  Assets:Equipment")
    _assert_semantic_trap(instance, wrong)


def test_translation_gain_to_income_fails():
    """Trap: credit a foreign-operation translation gain to income."""
    instance = FAMILIES["fx-translation-adjustment"](225)
    gain = _deltas(instance)["Assets:InvestmentInForeignSubsidiary"]
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Translation",
        [("Assets:InvestmentInForeignSubsidiary", gain), ("Income:Sales", -gain)],
    )
    _assert_semantic_trap(instance, wrong)


def test_deferring_sale_leaseback_gain_fails():
    """Trap: defer the gain although the transfer qualifies as a sale."""
    instance = FAMILIES["sale-and-leaseback-entry"](226)
    added = instance.solution_ledger[len(instance.initial_ledger) :]
    wrong = instance.initial_ledger + added.replace(
        "  Income:GainLossOnDisposal", "  Liabilities:DeferredRevenue"
    )
    _assert_semantic_trap(instance, wrong)


def test_credit_allowance_for_full_fv_decline_fails():
    """Trap: provide for the rate-driven fair-value decline, not credit losses."""
    import re
    from decimal import Decimal

    instance = FAMILIES["debt-security-credit-loss"](227)
    doc = instance.app_files["documents/credit_review.md"]
    decline = Decimal(re.search(r"fallen USD ([\d]+\.[\d]{2})", doc)[1])
    wrong = instance.initial_ledger + _entry(
        "2026-01-31",
        "Credit review",
        [("Expenses:CreditLoss", decline), ("Assets:AllowanceForCreditLosses", -decline)],
    )
    _assert_semantic_trap(instance, wrong)
