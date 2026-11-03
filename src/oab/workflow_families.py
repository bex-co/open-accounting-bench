"""Dynamic-first professional workflow families.

Workflow families start here rather than in ``oab.families.FAMILIES``.
That separation is the release lifecycle: a workflow generator may be
generated and calibrated on the Dynamic track before maintainers decide
whether to promote it into the Stable registry with a frozen seed.  The
conformance fixture in this module is deliberately small; it exists to
exercise the public generator, Harbor packaging, CLI validation, and
verifier contract end to end.
"""

from __future__ import annotations

import json
import random
from datetime import date
from decimal import Decimal

from oab.evidence import (
    ACCUMULATED_DEPRECIATION,
    NOTES_PAYABLE,
    ZERO,
    _csv,
    generate_company_history,
)
from oab.evidence import EXTRA_ACCOUNTS as EVIDENCE_EXTRA_ACCOUNTS
from oab.families import (
    AP,
    AR,
    BANK,
    CENT,
    CONTRACT_LIABILITY,
    COST_OF_SALES,
    CREDIT_ALLOWANCE,
    CREDIT_LOSS,
    CURRENT_PORTION,
    FAMILIES,
    INTEREST_PAYABLE,
    INVENTORY,
    PRODUCT_REVENUE,
    WRITE_DOWN,
    TaskInstance,
    _chart_md,
    _expected,
    _ledger_header,
    _txn,
    money,
)
from oab.workflow import WORKFLOW_FORMAT, workflow_check, workflow_determination, workflow_spec

PREPAID = "Assets:PrepaidInsurance"
SUSPENSE = "Assets:SuspenseClearing"
CONTRACT = CONTRACT_LIABILITY
SERVICE_REVENUE = "Income:ServiceRevenue"
COGS = COST_OF_SALES
EQUIPMENT = "Assets:Equipment"
BANK_FEES = "Expenses:BankFees"
INSURANCE_EXPENSE = "Expenses:Insurance"
UTILITIES_EXPENSE = "Expenses:Utilities"
REPAIRS_EXPENSE = "Expenses:Repairs"
MONTHLY_INSURANCE = Decimal("100.00")
SUSPENSE_UTILITIES = Decimal("180.00")
SUSPENSE_PAYABLE = Decimal("120.00")

EXTRA_ACCOUNTS = [
    (AR, "Customer receivables"),
    (INVENTORY, "Merchandise inventory"),
    (SUSPENSE, "Suspense/clearing balance awaiting disposition"),
    (AP, "Supplier payables"),
    (CONTRACT, "Customer amounts received before service is earned"),
    (PRODUCT_REVENUE, "Product revenue"),
    (SERVICE_REVENUE, "Service revenue"),
    (COGS, "Cost of products sold"),
]

WORKFLOW_POLICY = """# Accounting policy (workflow conformance fixture)

- Reporting currency: USD. Workflow period: 2026-01-01 through 2026-02-28.
- Append-only ledger: never edit or delete existing transactions in
  `/app/ledger.beancount`; add balanced transactions using only accounts
  in `/app/chart_of_accounts.md`.
- Complete `/app/workflow.json` with an `evidence` object, a `report`
  object, and a `trial_balance` object. Evidence dispositions used by
  this fixture are `recorded`, `cleared`, `earned`,
  `ignored-duplicate`, and `excluded-cutoff`.
- The January bank statement is authoritative for the monthly bank fee.
- A duplicate copy of a supplier invoice is not a second liability.
- A March estimate is outside this workflow period and must not be booked.
- Product revenue is recognized on shipment; the related inventory cost
  is expensed in the same period. Service revenue is recognized when the
  stated milestone is completed.
"""


def workflow_conformance_fixture(seed: int) -> TaskInstance:
    """Small multi-period workflow exercising every typed rubric check."""

    rng = random.Random(seed)
    opening_bank = Decimal(rng.randrange(10000, 12501, 100))
    opening_ar = Decimal(rng.randrange(1800, 2401, 50))
    opening_inventory = Decimal(rng.randrange(1500, 2101, 50))
    opening_prepaid = Decimal("1200.00")
    opening_suspense = SUSPENSE_UTILITIES + SUSPENSE_PAYABLE
    opening_ap = Decimal("-1800.00")
    opening_contract = Decimal("-900.00")
    opening_equity = -(
        opening_bank
        + opening_ar
        + opening_inventory
        + opening_prepaid
        + opening_suspense
        + opening_ap
        + opening_contract
    )

    bank_fee = Decimal("25.00")
    receipt = Decimal(rng.randrange(600, 851, 25))
    sale = Decimal(rng.randrange(900, 1301, 25))
    cost = (sale * Decimal("0.40")).quantize(Decimal("0.01"))
    supplier_invoice = Decimal(rng.randrange(400, 551, 25))
    service_earned = Decimal("300.00")

    initial = _ledger_header(Decimal("0.00"), EXTRA_ACCOUNTS)
    initial += _txn(
        "2026-01-01",
        "Opening",
        "Opening balances",
        [
            (BANK, opening_bank),
            (AR, opening_ar),
            (INVENTORY, opening_inventory),
            (PREPAID, opening_prepaid),
            (SUSPENSE, opening_suspense),
            (AP, opening_ap),
            (CONTRACT, opening_contract),
            ("Equity:Opening-Balances", opening_equity),
        ],
    )

    solution = initial
    solution += _txn(
        "2026-01-28",
        "Supplier",
        "Unrecorded repairs invoice",
        [(REPAIRS_EXPENSE, supplier_invoice), (AP, -supplier_invoice)],
    )
    solution += _txn(
        "2026-01-31",
        "Bank",
        "Monthly account fee",
        [(BANK_FEES, bank_fee), (BANK, -bank_fee)],
    )
    solution += _txn(
        "2026-01-31",
        "Controller",
        "Clear suspense balance",
        [
            (UTILITIES_EXPENSE, SUSPENSE_UTILITIES),
            (AP, SUSPENSE_PAYABLE),
            (SUSPENSE, -opening_suspense),
        ],
    )
    solution += _txn(
        "2026-01-31",
        "Insurer",
        "January insurance expired",
        [(INSURANCE_EXPENSE, MONTHLY_INSURANCE), (PREPAID, -MONTHLY_INSURANCE)],
    )
    solution += _txn(
        "2026-02-03",
        "Customer",
        "Customer receipt",
        [(BANK, receipt), (AR, -receipt)],
    )
    solution += _txn(
        "2026-02-10",
        "Customer",
        "Product shipment",
        [(AR, sale), (PRODUCT_REVENUE, -sale)],
    )
    solution += _txn(
        "2026-02-10",
        "Warehouse",
        "Cost of product shipment",
        [(COGS, cost), (INVENTORY, -cost)],
    )
    solution += _txn(
        "2026-02-20",
        "Customer",
        "Service milestone earned",
        [(CONTRACT, service_earned), (SERVICE_REVENUE, -service_earned)],
    )
    solution += _txn(
        "2026-02-28",
        "Insurer",
        "February insurance expired",
        [(INSURANCE_EXPENSE, MONTHLY_INSURANCE), (PREPAID, -MONTHLY_INSURANCE)],
    )

    final_bank = opening_bank - bank_fee + receipt
    final_ar = opening_ar - receipt + sale
    final_inventory = opening_inventory - cost
    insurance_expired = MONTHLY_INSURANCE * 2
    final_prepaid = opening_prepaid - insurance_expired
    final_ap = opening_ap + SUSPENSE_PAYABLE - supplier_invoice
    final_contract = opening_contract + service_earned
    total_revenue = sale + service_earned
    gross_profit = total_revenue - cost
    total_expenses = bank_fee + insurance_expired + SUSPENSE_UTILITIES + supplier_invoice

    evidence_doc = f"""# Workflow evidence

| Evidence ID | Date | Fact |
|---|---|---|
| bank-fee | 2026-01-31 | Bank charged a USD {money(bank_fee)} monthly account fee |
| supplier-invoice | 2026-01-28 | Unrecorded repairs invoice USD {money(supplier_invoice)} |
| duplicate-supplier-invoice | 2026-01-29 | Duplicate copy of the supplier invoice |
| suspense-receipt | 2026-01-31 | USD 180 utilities; USD 120 supplier payable |
| customer-receipt | 2026-02-03 | Customer paid USD {money(receipt)} on receivables |
| product-shipment | 2026-02-10 | Shipped USD {money(sale)}; cost USD {money(cost)} |
| service-milestone | 2026-02-20 | USD {money(service_earned)} contract amount earned |
| march-estimate | 2026-03-05 | March cost estimate; outside the workflow period |

Prepaid insurance was USD 1,200.00 for twelve months at 2026-01-01.
Expire one month in January and one month in February.
"""

    solution_workflow = {
        "evidence": {
            "bank-fee": "recorded",
            "supplier-invoice": "recorded",
            "duplicate-supplier-invoice": "ignored-duplicate",
            "suspense-receipt": "cleared",
            "customer-receipt": "recorded",
            "product-shipment": "recorded",
            "service-milestone": "earned",
            "march-estimate": "excluded-cutoff",
        },
        "report": {
            "bank_balance": money(final_bank),
            "product_revenue": money(sale),
            "service_revenue": money(service_earned),
            "total_revenue": money(total_revenue),
            "cost_of_sales": money(cost),
            "gross_profit": money(gross_profit),
            "total_expenses": money(total_expenses),
        },
        "trial_balance": {
            "accounts_receivable": money(final_ar),
            "inventory": money(final_inventory),
            "prepaid_insurance": money(final_prepaid),
            "accounts_payable": money(final_ap),
            "contract_liability": money(final_contract),
        },
    }
    starter_workflow = {"evidence": {}, "report": {}, "trial_balance": {}}

    determinations = [
        workflow_determination(
            "bank-fee", "cash", "Record the January bank fee", evidence=["bank-fee"]
        ),
        workflow_determination(
            "customer-receipt",
            "receivables",
            "Apply the February customer receipt",
            evidence=["customer-receipt"],
        ),
        workflow_determination(
            "product-sale",
            "revenue",
            "Record shipment revenue and cost",
            evidence=["product-shipment"],
        ),
        workflow_determination(
            "prepaid-insurance",
            "deferrals",
            "Expire two months of prepaid insurance",
            evidence=["documents/evidence.md"],
        ),
        workflow_determination(
            "suspense-clearing",
            "clearing",
            "Clear the suspense balance to its causes",
            evidence=["suspense-receipt"],
        ),
        workflow_determination(
            "supplier-invoice",
            "payables",
            "Record the supplier invoice once",
            evidence=["supplier-invoice", "duplicate-supplier-invoice"],
        ),
        workflow_determination(
            "contract-service",
            "revenue",
            "Recognize the earned service milestone",
            evidence=["service-milestone"],
        ),
        workflow_determination(
            "reporting",
            "reporting",
            "Report final balances and performance consistently",
            evidence=["documents/evidence.md"],
        ),
        workflow_determination(
            "integrity",
            "integrity",
            "Respect cutoff and leave unrelated accounts untouched",
            evidence=["march-estimate"],
        ),
    ]

    january = ["2026-01-01", "2026-01-31"]
    february = ["2026-02-01", "2026-02-28"]
    checks = [
        workflow_check(
            "bank-fee-account-delta",
            "account_delta",
            "bank-fee",
            account=BANK_FEES,
            expected=money(bank_fee),
        ),
        workflow_check(
            "bank-fee-january-bank-delta",
            "period_account_delta",
            "bank-fee",
            account=BANK,
            expected=money(-bank_fee),
            period=january,
        ),
        workflow_check(
            "bank-fee-evidence",
            "evidence_disposition",
            "bank-fee",
            path="evidence",
            key="bank-fee",
            expected="recorded",
        ),
        workflow_check(
            "customer-receipt-february-delta",
            "period_account_delta",
            "customer-receipt",
            account=BANK,
            expected=money(receipt),
            period=february,
        ),
        workflow_check(
            "customer-receipt-receivable-delta",
            "account_delta",
            "customer-receipt",
            account=AR,
            expected=money(sale - receipt),
        ),
        workflow_check(
            "customer-receipt-evidence",
            "evidence_disposition",
            "customer-receipt",
            path="evidence",
            key="customer-receipt",
            expected="recorded",
        ),
        workflow_check(
            "product-revenue-delta",
            "account_delta",
            "product-sale",
            account=PRODUCT_REVENUE,
            expected=money(-sale),
        ),
        workflow_check(
            "product-inventory-delta",
            "account_delta",
            "product-sale",
            account=INVENTORY,
            expected=money(-cost),
        ),
        workflow_check(
            "product-cogs-delta",
            "account_delta",
            "product-sale",
            account=COGS,
            expected=money(cost),
        ),
        workflow_check(
            "product-february-revenue",
            "period_account_delta",
            "product-sale",
            account=PRODUCT_REVENUE,
            expected=money(-sale),
            period=february,
        ),
        workflow_check(
            "product-shipment-evidence",
            "evidence_disposition",
            "product-sale",
            path="evidence",
            key="product-shipment",
            expected="recorded",
        ),
        workflow_check(
            "prepaid-delta",
            "account_delta",
            "prepaid-insurance",
            account=PREPAID,
            expected=money(-insurance_expired),
        ),
        workflow_check(
            "insurance-expense-delta",
            "account_delta",
            "prepaid-insurance",
            account=INSURANCE_EXPENSE,
            expected=money(insurance_expired),
        ),
        workflow_check(
            "prepaid-final-balance",
            "final_balance",
            "prepaid-insurance",
            account=PREPAID,
            expected=money(final_prepaid),
        ),
        workflow_check(
            "january-insurance-period-delta",
            "period_account_delta",
            "prepaid-insurance",
            account=INSURANCE_EXPENSE,
            expected=money(MONTHLY_INSURANCE),
            period=january,
        ),
        workflow_check(
            "suspense-cleared", "subledger_cleared", "suspense-clearing", account=SUSPENSE
        ),
        workflow_check(
            "suspense-utilities-delta",
            "account_delta",
            "suspense-clearing",
            account=UTILITIES_EXPENSE,
            expected=money(SUSPENSE_UTILITIES),
        ),
        workflow_check(
            "suspense-evidence",
            "evidence_disposition",
            "suspense-clearing",
            path="evidence",
            key="suspense-receipt",
            expected="cleared",
        ),
        workflow_check(
            "supplier-repairs-delta",
            "account_delta",
            "supplier-invoice",
            account=REPAIRS_EXPENSE,
            expected=money(supplier_invoice),
        ),
        workflow_check(
            "supplier-payable-final-balance",
            "final_balance",
            "supplier-invoice",
            account=AP,
            expected=money(final_ap),
        ),
        workflow_check(
            "supplier-invoice-evidence",
            "evidence_disposition",
            "supplier-invoice",
            path="evidence",
            key="supplier-invoice",
            expected="recorded",
        ),
        workflow_check(
            "duplicate-invoice-evidence",
            "evidence_disposition",
            "supplier-invoice",
            path="evidence",
            key="duplicate-supplier-invoice",
            expected="ignored-duplicate",
        ),
        workflow_check(
            "contract-liability-delta",
            "account_delta",
            "contract-service",
            account=CONTRACT,
            expected=money(service_earned),
        ),
        workflow_check(
            "service-revenue-delta",
            "account_delta",
            "contract-service",
            account=SERVICE_REVENUE,
            expected=money(-service_earned),
        ),
        workflow_check(
            "contract-final-balance",
            "final_balance",
            "contract-service",
            account=CONTRACT,
            expected=money(final_contract),
        ),
        workflow_check(
            "service-evidence",
            "evidence_disposition",
            "contract-service",
            path="evidence",
            key="service-milestone",
            expected="earned",
        ),
        workflow_check(
            "report-bank-balance",
            "json_value",
            "reporting",
            path="report.bank_balance",
            expected=money(final_bank),
        ),
        workflow_check(
            "bank-ledger-report-reconciliation",
            "cross_artifact_balance",
            "reporting",
            path="report.bank_balance",
            account=BANK,
        ),
        workflow_check(
            "report-receivables-balance",
            "json_value",
            "reporting",
            path="trial_balance.accounts_receivable",
            expected=money(final_ar),
        ),
        workflow_check(
            "report-total-revenue",
            "json_value",
            "reporting",
            path="report.total_revenue",
            expected=money(total_revenue),
        ),
        workflow_check(
            "report-gross-profit",
            "json_value",
            "reporting",
            path="report.gross_profit",
            expected=money(gross_profit),
        ),
        workflow_check(
            "report-total-expenses",
            "json_value",
            "reporting",
            path="report.total_expenses",
            expected=money(total_expenses),
        ),
        workflow_check(
            "equipment-forbidden-delta",
            "forbidden_account_delta",
            "integrity",
            account=EQUIPMENT,
        ),
        workflow_check(
            "march-cutoff-no-transactions",
            "cutoff_no_transactions",
            "integrity",
            period=["2026-03-01", "2026-03-31"],
        ),
        workflow_check(
            "march-evidence-disposition",
            "evidence_disposition",
            "integrity",
            path="evidence",
            key="march-estimate",
            expected="excluded-cutoff",
        ),
    ]

    expected_deltas = {
        BANK: money(receipt - bank_fee),
        AR: money(sale - receipt),
        INVENTORY: money(-cost),
        PREPAID: money(-insurance_expired),
        SUSPENSE: money(-opening_suspense),
        AP: money(SUSPENSE_PAYABLE - supplier_invoice),
        CONTRACT: money(service_earned),
        PRODUCT_REVENUE: money(-sale),
        SERVICE_REVENUE: money(-service_earned),
        COGS: money(cost),
        BANK_FEES: money(bank_fee),
        INSURANCE_EXPENSE: money(insurance_expired),
        UTILITIES_EXPENSE: money(SUSPENSE_UTILITIES),
        REPAIRS_EXPENSE: money(supplier_invoice),
    }
    return TaskInstance(
        task_id="workflow-conformance-fixture",
        family="workflow-conformance",
        title="Complete the workflow conformance fixture",
        instruction=(
            "Complete the January–February workflow in `/app/ledger.beancount` "
            "and `/app/workflow.json`, following `/app/policy.md`, "
            "`/app/chart_of_accounts.md`, and `/app/documents/evidence.md`. "
            "Append balanced transactions only; do not edit existing entries. "
            "Populate every evidence disposition and every report/trial-balance "
            "value named by the evidence and final ledger state."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": WORKFLOW_POLICY,
            "chart_of_accounts.md": _chart_md(EXTRA_ACCOUNTS),
            "documents/evidence.md": evidence_doc,
            "workflow.json": json.dumps(starter_workflow, indent=2) + "\n",
        },
        expected=_expected(
            "workflow-conformance-fixture",
            "workflow-conformance",
            seed,
            format=WORKFLOW_FORMAT,
            expected_deltas=expected_deltas,
            expected_new_transactions=[1, 30],
            expected_period=["2026-01-01", "2026-02-28"],
            required_final_balances={
                BANK: money(final_bank),
                AR: money(final_ar),
                INVENTORY: money(final_inventory),
                PREPAID: money(final_prepaid),
                SUSPENSE: "0.00",
                AP: money(final_ap),
                CONTRACT: money(final_contract),
            },
            workflow=workflow_spec(determinations, checks),
        ),
        solution_ledger=solution,
        solution_files={
            "workflow.json": json.dumps(solution_workflow, indent=2) + "\n",
        },
        difficulty="medium",
        keywords=["workflow", "rubric", "multi-artifact", "conformance"],
        level="university",
        format=WORKFLOW_FORMAT,
        skill="analysis",
    )


ALLOWANCE = CREDIT_ALLOWANCE
PREPAID_RENT = "Assets:PrepaidRent"
CREDIT_LOSS_EXPENSE = CREDIT_LOSS
RENT_EXPENSE = "Expenses:Rent"
INTEREST_EXPENSE = "Expenses:Interest"
INVENTORY_WRITE_DOWN = WRITE_DOWN

CLOSE_EXTRA_ACCOUNTS = [
    (ALLOWANCE, "Allowance for expected credit losses (contra asset)"),
    (PREPAID_RENT, "Rent paid in advance"),
    (INTEREST_PAYABLE, "Accrued interest payable"),
    (CURRENT_PORTION, "Current portion of long-term debt"),
    (CREDIT_LOSS_EXPENSE, "Expected credit-loss expense"),
    (INVENTORY_WRITE_DOWN, "Inventory count shortage and NRV write-down"),
]

CLOSE_CLUSTERS = [
    "revenue-cutoff",
    "receivables-allowance",
    "inventory-valuation",
    "unrecorded-payables",
    "prepayment-cutoff",
    "fixed-asset-treatment",
    "debt-interest-classification",
    "bank-reconciliation",
]

CLOSE_POLICY = """# Month-end close policy

- Close period: the final period in `trial_balances.csv`. The ledger is
  append-only: add balanced entries dated in the close period; never
  edit or delete an existing transaction.
- Materiality for this close: record every known adjustment of USD 100
  or more. Amounts below USD 25 are clearly trivial. The seeded close
  items are all at or above the recording threshold.
- Evidence precedence: signed carrier/shipping logs prevail over sales
  orders for shipment; signed physical counts prevail over unsigned
  count copies; current policy and revised statements prevail over
  stale or superseded copies; itemized reconciliations prevail over
  unexplained statement totals. A duplicate document does not create a
  second asset, liability, revenue, or expense.
- Product revenue is recognized when goods ship. Service revenue is
  recognized when the stated milestone is complete.
- Expected credit losses use the aging schedule: 1% current, 5% at
  1–30 days overdue, 20% over 30 days overdue, and 100% for a customer
  identified as bankrupt. Exclude any receivable that is reversed
  because the related sale was not earned.
- Inventory is carried at the lower of cost and net realizable value.
  A signed count shortage is written down in the close period.
- Goods and services received in the close period are accrued in that
  period even when the supplier invoice arrives afterward.
- Prepayments expire straight-line over their stated service term.
- Capitalize only costs that create a separable future benefit or
  materially extend an asset's life/capacity. Routine maintenance is
  expensed.
- Interest accrues with time. Debt principal due within twelve months
  after period-end is current.
- A customer check returned for insufficient funds reinstates the
  receivable and reduces cash in the period the bank returns it.
"""


def _apply_postings(balances: dict[str, Decimal], postings: list[tuple[str, Decimal]]) -> None:
    for account, amount in postings:
        balances[account] = balances.get(account, ZERO) + amount


def month_end_close_workflow(seed: int) -> TaskInstance:
    """Professional month-end close over a three-period synthetic company."""

    pack = generate_company_history(seed, anomalies=())
    rng = random.Random(seed ^ 0xC105E)
    current = pack.periods[-1]
    next_period = "2026-02"
    balances = dict(pack.trial_balances[current.label])

    omitted = CLOSE_CLUSTERS[seed % len(CLOSE_CLUSTERS)]
    active = [cluster for cluster in CLOSE_CLUSTERS if cluster != omitted]
    active_set = set(active)

    draft_entries: list[tuple[str, str, str, list[tuple[str, Decimal]]]] = []
    oracle_entries: list[tuple[str, str, str, list[tuple[str, Decimal]]]] = []
    draft_balances = dict(balances)

    revenue_customer = rng.choice(pack.master.customers)
    revenue_amount = Decimal(rng.randrange(1000, 2501, 25))
    if "revenue-cutoff" in active_set:
        draft_entries.append(
            (
                f"{current.label}-30",
                revenue_customer.name,
                "Draft product sale",
                [(AR, revenue_amount), (PRODUCT_REVENUE, -revenue_amount)],
            )
        )

    prepaid_total = Decimal(rng.choice([1800, 2400, 3000]))
    prepaid_monthly = prepaid_total / Decimal(6)
    prepaid_defer = prepaid_total - prepaid_monthly
    if "prepayment-cutoff" in active_set:
        draft_entries.append(
            (
                f"{current.label}-02",
                "Landlord",
                "Draft six-month rent payment expensed",
                [(RENT_EXPENSE, prepaid_total), (BANK, -prepaid_total)],
            )
        )

    repair_amount = Decimal(rng.randrange(600, 1401, 25))
    if "fixed-asset-treatment" in active_set:
        draft_entries.append(
            (
                f"{current.label}-12",
                "Supplier",
                "Draft equipment repair capitalized",
                [(EQUIPMENT, repair_amount), (AP, -repair_amount)],
            )
        )

    for _date, _payee, _narration, postings in draft_entries:
        _apply_postings(draft_balances, postings)

    def draft_bal(account: str) -> Decimal:
        return draft_balances.get(account, ZERO)

    # Receivables allowance from the validated pack subledger. The draft
    # premature sale is listed in the aging file but excluded from the
    # expected allowance when revenue cutoff reverses it.
    open_ar = [record for record in pack.subledgers["accounts_receivable"] if record.amount != ZERO]
    specific = rng.choice(open_ar)
    allowance = ZERO
    aging_rows: list[list[object]] = [
        ["record_id", "customer_id", "amount", "due_date", "bucket", "loss_rate", "specific_risk"]
    ]
    period_end = date.fromisoformat(current.end)
    for record in open_ar:
        due = date.fromisoformat(record.due_date or current.end)
        overdue = (period_end - due).days
        if record.id == specific.id:
            bucket, rate, risk = "specific", Decimal("1.00"), "bankrupt"
        elif overdue <= 0:
            bucket, rate, risk = "current", Decimal("0.01"), ""
        elif overdue <= 30:
            bucket, rate, risk = "1-30", Decimal("0.05"), ""
        else:
            bucket, rate, risk = "over-30", Decimal("0.20"), ""
        allowance += (record.amount * rate).quantize(CENT)
        aging_rows.append(
            [
                record.id,
                record.party_id,
                money(record.amount),
                record.due_date,
                bucket,
                str(rate),
                risk,
            ]
        )
    if "revenue-cutoff" in active_set:
        aging_rows.append(
            [
                "close-premature-sale",
                revenue_customer.id,
                money(revenue_amount),
                "2026-02-14",
                "unshipped",
                "0",
                "not-shipped",
            ]
        )
    inventory_record = max(
        pack.subledgers["inventory"], key=lambda record: record.quantity or Decimal("0")
    )
    inventory_item = next(item for item in pack.master.items if item.id == inventory_record.item_id)
    shortage_units = Decimal(rng.randrange(2, 7))
    markdown = Decimal(rng.randrange(3, 9))
    nrv = inventory_item.unit_cost - markdown
    counted_units = (inventory_record.quantity or Decimal("0")) - shortage_units
    write_down = shortage_units * inventory_item.unit_cost + counted_units * markdown

    supplier_amount = Decimal(rng.randrange(350, 901, 25))
    note_principal = -draft_bal(NOTES_PAYABLE)
    annual_rate = Decimal(rng.choice([600, 900, 1200])) / Decimal(10000)
    interest = (note_principal * annual_rate / Decimal(12)).quantize(CENT)
    current_portion = min(note_principal, Decimal(rng.randrange(1000, 2501, 250)))
    nsf_amount = Decimal(rng.randrange(300, 801, 25))

    if "revenue-cutoff" in active_set:
        oracle_entries.append(
            (
                current.end,
                revenue_customer.name,
                "Reverse premature product sale",
                [(PRODUCT_REVENUE, revenue_amount), (AR, -revenue_amount)],
            )
        )
    if "receivables-allowance" in active_set:
        oracle_entries.append(
            (
                current.end,
                "Controller",
                "Record credit-loss allowance",
                [(CREDIT_LOSS_EXPENSE, allowance), (ALLOWANCE, -allowance)],
            )
        )
    if "inventory-valuation" in active_set:
        oracle_entries.append(
            (
                current.end,
                "Warehouse",
                "Record inventory write-down",
                [(INVENTORY_WRITE_DOWN, write_down), (INVENTORY, -write_down)],
            )
        )
    if "unrecorded-payables" in active_set:
        oracle_entries.append(
            (
                current.end,
                "Supplier",
                "Accrue unrecorded supplier service",
                [(UTILITIES_EXPENSE, supplier_amount), (AP, -supplier_amount)],
            )
        )
    if "prepayment-cutoff" in active_set:
        oracle_entries.append(
            (
                current.end,
                "Landlord",
                "Defer unexpired prepaid rent",
                [(PREPAID_RENT, prepaid_defer), (RENT_EXPENSE, -prepaid_defer)],
            )
        )
    if "fixed-asset-treatment" in active_set:
        oracle_entries.append(
            (
                current.end,
                "Supplier",
                "Expense routine equipment repair",
                [(REPAIRS_EXPENSE, repair_amount), (EQUIPMENT, -repair_amount)],
            )
        )
    if "debt-interest-classification" in active_set:
        oracle_entries.append(
            (
                current.end,
                "Lender",
                "Accrue January note interest",
                [(INTEREST_EXPENSE, interest), (INTEREST_PAYABLE, -interest)],
            )
        )
        oracle_entries.append(
            (
                current.end,
                "Lender",
                "Reclassify current portion of note",
                [(NOTES_PAYABLE, current_portion), (CURRENT_PORTION, -current_portion)],
            )
        )
    if "bank-reconciliation" in active_set:
        oracle_entries.append(
            (
                current.end,
                "Bank",
                "Record returned customer check",
                [(AR, nsf_amount), (BANK, -nsf_amount)],
            )
        )

    final_balances = dict(draft_balances)
    for _date, _payee, _narration, postings in oracle_entries:
        _apply_postings(final_balances, postings)

    def final_bal(account: str) -> Decimal:
        return final_balances.get(account, ZERO)

    expected_deltas: dict[str, Decimal] = {}
    for _date, _payee, _narration, postings in oracle_entries:
        _apply_postings(expected_deltas, postings)
    expected_deltas = {
        account: amount for account, amount in sorted(expected_deltas.items()) if amount != 0
    }

    # Current-period statement values from pack activity plus draft and
    # oracle postings. Signs follow ledger presentation internally.
    current_totals: dict[str, Decimal] = {}
    for transaction in pack.transactions:
        if transaction.period == current.label:
            _apply_postings(current_totals, transaction.postings)
    for entries in (draft_entries, oracle_entries):
        for _date, _payee, _narration, postings in entries:
            _apply_postings(current_totals, postings)

    def sum_current(account: str) -> Decimal:
        return current_totals.get(account, ZERO)

    product_revenue = -sum_current(PRODUCT_REVENUE)
    service_revenue = -sum_current(SERVICE_REVENUE)
    total_revenue = product_revenue + service_revenue
    total_expenses = sum(
        (amount for account, amount in current_totals.items() if account.startswith("Expenses:")),
        ZERO,
    )
    cash_change = sum_current(BANK)

    inventory_rows: list[list[object]] = [
        ["item_id", "item", "book_quantity", "signed_count_quantity", "unit_cost", "nrv_per_unit"]
    ]
    items_by_id = {item.id: item for item in pack.master.items}
    for record in pack.subledgers["inventory"]:
        item = items_by_id[record.item_id]
        if record.id == inventory_record.id and "inventory-valuation" in active_set:
            count_quantity, item_nrv = counted_units, nrv
        else:
            count_quantity, item_nrv = record.quantity or Decimal("0"), item.unit_cost
        inventory_rows.append(
            [
                item.id,
                item.name,
                money(record.quantity or Decimal("0")),
                money(count_quantity),
                money(item.unit_cost),
                money(item_nrv),
            ]
        )

    close_evidence = f"""# Current-period close evidence

Current period ends {current.end}. Amounts are USD.

## Revenue and shipment

- Sales order for {revenue_customer.name}: USD {money(revenue_amount)},
  requested ship date {current.label}-30.
- Signed carrier log: the same goods were tendered to the carrier on
  2026-02-02. The draft ledger already contains a {current.label}-30
  product sale for this order.

## Supplier, rent, and equipment documents

- Supplier service was received {current.label}-29 for USD
  {money(supplier_amount)}; the invoice is dated 2026-02-03 and is not
  in the draft accounts-payable subledger. A duplicate copy of the
  same invoice was also received.
- Rent payment of USD {money(prepaid_total)} on {current.label}-02
  covers six months beginning {current.label}-01. The draft ledger
  charged the full payment to rent expense.
- Equipment invoice of USD {money(repair_amount)} on
  {current.label}-12 describes a routine tune-up and replacement of
  worn belts; it does not extend useful life or increase capacity.
  The draft ledger capitalized the invoice.

## Debt schedule

- Note principal in the draft trial balance bears interest at
  {money(annual_rate * Decimal(100))}% per year. January interest has
  not been accrued. USD {money(current_portion)} of principal is due
  within twelve months after {current.end}; the remainder is due
  after that window.

## Bank statement

- The bank returned a customer check for USD {money(nsf_amount)} on
  {current.end} for insufficient funds. The draft ledger has not
  recorded the return.
- A March supplier quote was also received for possible February
  work. No goods or services were received by {current.end}.
"""

    ledger_lines = pack.files["ledger.beancount"].splitlines()
    opens = [
        f"{pack.periods[0].start} open {account} USD"
        for account, _description in CLOSE_EXTRA_ACCOUNTS
    ]
    initial_ledger = "\n".join([ledger_lines[0], *opens, *ledger_lines[1:]]) + "\n"
    for entry_date, payee, narration, postings in draft_entries:
        initial_ledger += _txn(entry_date, payee, narration, postings)
    solution_ledger = initial_ledger
    for entry_date, payee, narration, postings in oracle_entries:
        solution_ledger += _txn(entry_date, payee, narration, postings)

    dispositions = {
        "revenue-cutoff": "reverse-premature-sale",
        "receivables-allowance": "record-allowance",
        "inventory-valuation": "write-down-to-count-nrv",
        "unrecorded-payables": "accrue-current-period",
        "prepayment-cutoff": "defer-unexpired",
        "fixed-asset-treatment": "expense-routine-repair",
        "debt-interest-classification": "accrue-and-reclassify",
        "bank-reconciliation": "record-nsf",
    }
    trial_fields = {
        "bank": BANK,
        "accounts_receivable": AR,
        "allowance_for_credit_losses": ALLOWANCE,
        "inventory": INVENTORY,
        "prepaid_rent": PREPAID_RENT,
        "equipment": EQUIPMENT,
        "accumulated_depreciation": ACCUMULATED_DEPRECIATION,
        "accounts_payable": AP,
        "contract_liability": CONTRACT,
        "notes_payable": NOTES_PAYABLE,
        "current_portion_long_term_debt": CURRENT_PORTION,
        "interest_payable": INTEREST_PAYABLE,
    }
    solution_workflow = {
        "evidence": {cluster: dispositions[cluster] for cluster in active}
        | {"march-supplier-quote": "exclude-next-period"},
        "trial_balance": {
            field: money(final_bal(account)) for field, account in trial_fields.items()
        },
        "income_statement": {
            "product_revenue": money(product_revenue),
            "service_revenue": money(service_revenue),
            "total_revenue": money(total_revenue),
            "total_expenses": money(total_expenses),
            "operating_income": money(total_revenue - total_expenses),
            "cash_change_current_period": money(cash_change),
        },
    }
    starter_workflow = {
        "evidence": {key: "" for key in solution_workflow["evidence"]},
        "trial_balance": {key: "" for key in solution_workflow["trial_balance"]},
        "income_statement": {key: "" for key in solution_workflow["income_statement"]},
    }

    app_files = dict(pack.files)
    app_files.update(
        {
            "ledger.beancount": initial_ledger,
            "chart_of_accounts.md": _chart_md([*EVIDENCE_EXTRA_ACCOUNTS, *CLOSE_EXTRA_ACCOUNTS]),
            "policy.md": CLOSE_POLICY,
            "documents/close_evidence.md": close_evidence,
            "documents/close_ar_aging.csv": _csv(aging_rows),
            "documents/close_inventory_count.csv": _csv(inventory_rows),
            "documents/close_revenue_cutoff.csv": _csv(
                [
                    ["order_id", "customer_id", "amount", "order_date", "signed_ship_date"],
                    [
                        "close-order-001",
                        revenue_customer.id,
                        money(revenue_amount),
                        f"{current.label}-30",
                        "2026-02-02",
                    ],
                ]
            ),
            "workflow.json": json.dumps(starter_workflow, indent=2) + "\n",
        }
    )

    determinations = []
    checks = []
    issue_files = {
        "revenue-cutoff": ["documents/close_revenue_cutoff.csv", "documents/close_evidence.md"],
        "receivables-allowance": [
            "documents/close_ar_aging.csv",
            "subledgers/accounts_receivable.csv",
        ],
        "inventory-valuation": ["documents/close_inventory_count.csv", "subledgers/inventory.csv"],
        "unrecorded-payables": ["documents/close_evidence.md", "subledgers/accounts_payable.csv"],
        "prepayment-cutoff": ["documents/close_evidence.md"],
        "fixed-asset-treatment": ["documents/close_evidence.md", "subledgers/fixed_assets.csv"],
        "debt-interest-classification": ["documents/close_evidence.md", "trial_balances.csv"],
        "bank-reconciliation": ["documents/close_evidence.md", "documents/bank_statements.csv"],
    }
    issue_titles = {
        "revenue-cutoff": "Correct premature revenue cutoff",
        "receivables-allowance": "Measure expected credit losses",
        "inventory-valuation": "Write inventory down to signed count and NRV",
        "unrecorded-payables": "Accrue the unrecorded supplier service",
        "prepayment-cutoff": "Defer unexpired prepaid rent",
        "fixed-asset-treatment": "Expense routine equipment maintenance",
        "debt-interest-classification": "Accrue interest and classify current debt",
        "bank-reconciliation": "Record the returned customer check",
    }
    primary_checks = {
        "revenue-cutoff": (
            PRODUCT_REVENUE,
            revenue_amount,
            PRODUCT_REVENUE,
            revenue_amount,
            AR,
        ),
        "receivables-allowance": (
            CREDIT_LOSS_EXPENSE,
            allowance,
            ALLOWANCE,
            -allowance,
            ALLOWANCE,
        ),
        "inventory-valuation": (
            INVENTORY_WRITE_DOWN,
            write_down,
            INVENTORY,
            -write_down,
            INVENTORY,
        ),
        "unrecorded-payables": (
            UTILITIES_EXPENSE,
            supplier_amount,
            AP,
            -supplier_amount,
            AP,
        ),
        "prepayment-cutoff": (
            PREPAID_RENT,
            prepaid_defer,
            RENT_EXPENSE,
            -prepaid_defer,
            PREPAID_RENT,
        ),
        "fixed-asset-treatment": (
            REPAIRS_EXPENSE,
            repair_amount,
            EQUIPMENT,
            -repair_amount,
            EQUIPMENT,
        ),
        "debt-interest-classification": (
            INTEREST_EXPENSE,
            interest,
            CURRENT_PORTION,
            -current_portion,
            INTEREST_PAYABLE,
        ),
        "bank-reconciliation": (BANK, -nsf_amount, BANK, -nsf_amount, BANK),
    }
    secondary_final = {
        "revenue-cutoff": PRODUCT_REVENUE,
        "receivables-allowance": AR,
        "inventory-valuation": INVENTORY_WRITE_DOWN,
        "unrecorded-payables": UTILITIES_EXPENSE,
        "prepayment-cutoff": RENT_EXPENSE,
        "fixed-asset-treatment": REPAIRS_EXPENSE,
        "debt-interest-classification": NOTES_PAYABLE,
        "bank-reconciliation": AR,
    }
    current_period = [current.start, current.end]
    for cluster in active:
        determination_id = cluster
        determinations.append(
            workflow_determination(
                determination_id,
                cluster,
                issue_titles[cluster],
                evidence=issue_files[cluster],
            )
        )
        primary_account, primary_amount, period_account, period_amount, final_account = (
            primary_checks[cluster]
        )
        checks.extend(
            [
                workflow_check(
                    f"{cluster}-primary-delta",
                    "account_delta",
                    determination_id,
                    account=primary_account,
                    expected=money(primary_amount),
                ),
                workflow_check(
                    f"{cluster}-current-period-delta",
                    "period_account_delta",
                    determination_id,
                    account=period_account,
                    expected=money(period_amount),
                    period=current_period,
                ),
                workflow_check(
                    f"{cluster}-final-balance",
                    "final_balance",
                    determination_id,
                    account=final_account,
                    expected=money(final_bal(final_account)),
                ),
                workflow_check(
                    f"{cluster}-secondary-final-balance",
                    "final_balance",
                    determination_id,
                    account=secondary_final[cluster],
                    expected=money(final_bal(secondary_final[cluster])),
                ),
                workflow_check(
                    f"{cluster}-evidence",
                    "evidence_disposition",
                    determination_id,
                    path="evidence",
                    key=cluster,
                    expected=dispositions[cluster],
                ),
            ]
        )

    determinations.extend(
        [
            workflow_determination(
                "reporting",
                "reporting",
                "Report the adjusted trial balance and current-period performance",
                evidence=["trial_balances.csv", "documents/close_evidence.md"],
            ),
            workflow_determination(
                "integrity",
                "integrity",
                "Respect period cutoff and leave unrelated balances untouched",
                evidence=["documents/close_evidence.md"],
            ),
        ]
    )
    for field, account in trial_fields.items():
        checks.append(
            workflow_check(
                f"reporting-{field.replace('_', '-')}",
                "json_value",
                "reporting",
                path=f"trial_balance.{field}",
                expected=money(final_bal(account)),
            )
        )
    checks.extend(
        [
            workflow_check(
                "reporting-bank-reconciliation",
                "cross_artifact_balance",
                "reporting",
                path="trial_balance.bank",
                account=BANK,
            ),
            workflow_check(
                "reporting-total-revenue",
                "json_value",
                "reporting",
                path="income_statement.total_revenue",
                expected=money(total_revenue),
            ),
            workflow_check(
                "reporting-total-expenses",
                "json_value",
                "reporting",
                path="income_statement.total_expenses",
                expected=money(total_expenses),
            ),
            workflow_check(
                "reporting-operating-income",
                "json_value",
                "reporting",
                path="income_statement.operating_income",
                expected=money(total_revenue - total_expenses),
            ),
            workflow_check(
                "integrity-suspense-forbidden",
                "forbidden_account_delta",
                "integrity",
                account=SUSPENSE,
            ),
            workflow_check(
                "integrity-next-period-cutoff",
                "cutoff_no_transactions",
                "integrity",
                period=[f"{next_period}-01", f"{next_period}-28"],
            ),
            workflow_check(
                "integrity-march-quote",
                "evidence_disposition",
                "integrity",
                path="evidence",
                key="march-supplier-quote",
                expected="exclude-next-period",
            ),
        ]
    )

    required_final = {account: money(final_bal(account)) for account in trial_fields.values()}
    return TaskInstance(
        task_id="month-end-close-workflow",
        family="month-end-close",
        title="Complete the month-end close",
        instruction=(
            f"Complete the {current.label} month-end close in "
            "`/app/ledger.beancount` and `/app/workflow.json`. Review "
            "`/app/policy.md`, `/app/chart_of_accounts.md`, the prior-period "
            "history and trial balances, every subledger, and all documents "
            "including `/app/documents/close_evidence.md`, "
            "`/app/documents/close_ar_aging.csv`, and "
            "`/app/documents/close_inventory_count.csv`. Append balanced "
            f"entries dated no later than {current.end}; never edit existing "
            "transactions. Complete every evidence disposition, adjusted "
            "trial-balance value, and current-period income-statement value "
            "in the workflow schedule."
        ),
        app_files=app_files,
        expected=_expected(
            "month-end-close-workflow",
            "month-end-close",
            seed,
            format=WORKFLOW_FORMAT,
            expected_deltas={account: money(amount) for account, amount in expected_deltas.items()},
            expected_new_transactions=[1, 40],
            expected_period=current_period,
            required_final_balances=required_final,
            workflow=workflow_spec(determinations, checks),
        ),
        solution_ledger=solution_ledger,
        solution_files={"workflow.json": json.dumps(solution_workflow, indent=2) + "\n"},
        difficulty="hard",
        keywords=["month-end-close", "workflow", "cutoff", "accruals", "professional"],
        level="professional",
        format=WORKFLOW_FORMAT,
        skill="evaluation",
    )


DYNAMIC_FAMILIES = {
    "workflow-conformance-fixture": workflow_conformance_fixture,
    "month-end-close-workflow": month_end_close_workflow,
}

# Single registry for callers that generate or crosswalk both tracks.
ALL_FAMILIES = {**FAMILIES, **DYNAMIC_FAMILIES}
