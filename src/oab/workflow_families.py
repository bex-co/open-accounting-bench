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
from decimal import Decimal

from oab.families import (
    AP,
    AR,
    BANK,
    CONTRACT_LIABILITY,
    COST_OF_SALES,
    FAMILIES,
    INVENTORY,
    PRODUCT_REVENUE,
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


DYNAMIC_FAMILIES = {
    "workflow-conformance-fixture": workflow_conformance_fixture,
}

# Single registry for callers that generate or crosswalk both tracks.
ALL_FAMILIES = {**FAMILIES, **DYNAMIC_FAMILIES}
