"""Task families: parameterized, seed-deterministic accounting scenarios.

Each family is a function ``(seed) -> TaskInstance``. One validated family
yields many distinct instances; the committed tasks under ``tasks/`` are
frozen Stable-track instances (fixed seeds), while the Dynamic track
generates fresh seeds at evaluation time. See docs/task-families.md.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from decimal import Decimal

from oab import GENERATOR_VERSION

CENT = Decimal("0.01")
BANK = "Assets:Bank:Checking"

# Closed vocabularies for the five-axis taxonomy. Extend here (and in
# tasks/manifest.schema.json) before using a new value; never invent
# per-task spellings. `skill` mirrors the AICPA blueprint's revised-Bloom
# levels so crosswalks compare like with like.
TAXONOMY: dict[str, tuple[str, ...]] = {
    "category": (
        "financial-accounting",
        "management-accounting",
        "tax",
        "audit-assurance",
    ),
    "framework": ("core", "ifrs", "us-gaap"),
    "level": ("vocational", "university", "professional"),
    "format": (
        "journal-entry",
        "single-choice",
        "multiple-choice",
        "numeric",
        "open-text",
    ),
    "skill": ("remembering-understanding", "application", "analysis", "evaluation"),
}

# Authoritative-standard references (open vocabulary, fixed shape): the
# stable content anchor that exam crosswalks pivot through.
# e.g. "asc:230", "asc:606-10-25", "ias:23", "ifrs:16".
STANDARD_REF = re.compile(r"^(asc|ias|ifrs|ifric):[0-9]+(-[0-9]+)*$")

CHART = [
    ("Assets:Bank:Checking", "Operating bank account"),
    ("Assets:Equipment", "Capitalized equipment (multi-year useful life)"),
    ("Assets:PrepaidInsurance", "Insurance paid in advance"),
    ("Equity:Opening-Balances", "Opening balances"),
    ("Income:Sales", "Sales revenue"),
    ("Expenses:BankFees", "Bank service charges"),
    ("Expenses:Insurance", "Insurance expense for the current period"),
    ("Expenses:Interest", "Interest expense (non-capitalized borrowing costs)"),
    ("Expenses:OfficeSupplies", "Consumable office supplies"),
    ("Expenses:Rent", "Office rent"),
    ("Expenses:Repairs", "Repairs and maintenance"),
    ("Expenses:Utilities", "Utilities"),
]

POLICY = """# Accounting policy (applies to this task)

- Reporting currency: USD. Reporting period: January 2026.
- Append-only ledger: never edit or delete existing transactions in
  `/app/ledger.beancount`. Record new or correcting entries as new
  transactions so the audit trail is preserved.
- Use only accounts listed in `/app/chart_of_accounts.md`. Do not open
  new accounts.
- Consumable supplies and services consumed in the period are expenses.
  Only items with a useful life over one year are capitalized as assets.
- Every transaction must balance (debits equal credits) and be dated
  within the reporting period unless the task states otherwise.
"""


def money(value: Decimal) -> str:
    return f"{value.quantize(CENT):.2f}"


def _chart_md(extra: list[tuple[str, str]] | None = None) -> str:
    rows = "\n".join(f"- `{account}` — {desc}" for account, desc in CHART + (extra or []))
    return f"# Chart of accounts\n\n{rows}\n"


def _ledger_header(opening_bank: Decimal, extra: list[tuple[str, str]] | None = None) -> str:
    """Opening ledger. `extra` opens family-local accounts without touching CHART,
    so adding a family never changes existing Stable tasks."""
    accounts = CHART + (extra or [])
    opens = "\n".join(f"2026-01-01 open {account} USD" for account, _ in accounts)
    return f"""option "title" "Acme Widgets LLC"
option "operating_currency" "USD"

{opens}

2026-01-01 * "Opening" "Opening bank balance"
  {BANK}  {money(opening_bank)} USD
  Equity:Opening-Balances  -{money(opening_bank)} USD
"""


def _txn(date: str, payee: str, narration: str, postings: list[tuple[str, Decimal]]) -> str:
    lines = [f'\n{date} * "{payee}" "{narration}"']
    for account, amount in postings:
        lines.append(f"  {account}  {money(amount)} USD")
    return "\n".join(lines) + "\n"


@dataclass
class TaskInstance:
    task_id: str
    family: str
    title: str
    instruction: str
    app_files: dict[str, str]
    expected: dict
    solution_ledger: str
    difficulty: str = "easy"
    keywords: list[str] = field(default_factory=list)
    # Five-axis taxonomy (docs/task-families.md). Values must stay within
    # TAXONOMY; `oab validate` enforces it.
    category: str = "financial-accounting"
    framework: str = "core"
    level: str = "university"
    format: str = "journal-entry"
    skill: str = "application"
    # Standard references matching STANDARD_REF; empty for core tasks
    # that rest on no single standard.
    standards: list[str] = field(default_factory=list)
    # Answer-file shape (format != "journal-entry"): reference answer
    # object written to solution/answer.json; solution_ledger unused.
    solution_answer: dict | None = None

    @property
    def initial_ledger(self) -> str:
        return self.app_files["ledger.beancount"]


def _expected(task_id: str, family: str, seed: int, **overrides) -> dict:
    base = {
        "task_id": task_id,
        "family": family,
        "seed": seed,
        "generator_version": GENERATOR_VERSION,
        "format": "journal-entry",
        "currency": "USD",
        "tolerance": "0.01",
        "expected_deltas": {},
        "allowed_extra_accounts": [],
        "expected_new_transactions": 1,
        "expected_period": ["2026-01-01", "2026-01-31"],
        "required_final_balances": {},
        "forbid_new_accounts": True,
    }
    base.update(overrides)
    return base


def classify_operating_expense(seed: int) -> TaskInstance:
    rng = random.Random(seed)
    amount = Decimal(rng.randrange(18000, 95001, 25)) / 100
    vendor = rng.choice(["OfficeMax", "Staples", "Uline", "Quill"])
    day = rng.randint(5, 25)
    opening = Decimal("10000.00")
    initial = _ledger_header(opening)
    date = f"2026-01-{day:02d}"
    receipt = (
        f"# Receipt — {vendor}\n\nDate: {date}\n"
        f"Items: printer paper, toner, pens (consumables)\n"
        f"Total paid from checking: USD {money(amount)}\n"
    )
    solution = initial + _txn(
        date,
        vendor,
        "Office supplies (consumables)",
        [("Expenses:OfficeSupplies", amount), (BANK, -amount)],
    )
    return TaskInstance(
        task_id="classify-operating-expense",
        family="transaction-classification",
        title="Record an operating expense from a receipt",
        instruction=(
            f"Record the purchase evidenced by `/app/documents/receipt.md` "
            f"({vendor}, USD {money(amount)}, {date}, paid from checking) in "
            "`/app/ledger.beancount`, following `/app/policy.md` and "
            "`/app/chart_of_accounts.md`. Append exactly one balanced "
            "transaction; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": POLICY,
            "chart_of_accounts.md": _chart_md(),
            "documents/receipt.md": receipt,
        },
        expected=_expected(
            "classify-operating-expense",
            "transaction-classification",
            seed,
            expected_deltas={
                "Expenses:OfficeSupplies": money(amount),
                BANK: money(-amount),
            },
            required_final_balances={BANK: money(opening - amount)},
        ),
        solution_ledger=solution,
        keywords=["expense", "classification", "journal-entry"],
        level="vocational",
    )


def bank_recon_missing_fee(seed: int) -> TaskInstance:
    rng = random.Random(seed)
    fee = Decimal(rng.randrange(1500, 4501, 25)) / 100
    payment = Decimal(rng.randrange(60000, 120001, 500)) / 100
    vendor = rng.choice(["City Power", "Metro Water", "Comcast Business"])
    opening = Decimal("10000.00")
    pay_txn = _txn(
        "2026-01-10",
        vendor,
        "Utilities payment",
        [("Expenses:Utilities", payment), (BANK, -payment)],
    )
    initial = _ledger_header(opening) + pay_txn + pay_txn  # duplicate import
    statement_balance = opening - payment - fee
    statement = (
        "# Bank statement — Checking, January 2026\n\n"
        f"- 2026-01-10 {vendor} utilities payment: -{money(payment)} USD (once)\n"
        f"- 2026-01-31 Monthly service charge: -{money(fee)} USD\n"
        f"- Statement balance 2026-01-31: {money(statement_balance)} USD\n"
    )
    solution = (
        initial
        + _txn(
            "2026-01-10",
            vendor,
            "Reverse duplicate imported utilities payment",
            [("Expenses:Utilities", -payment), (BANK, payment)],
        )
        + _txn(
            "2026-01-31",
            "Bank",
            "Monthly service charge",
            [("Expenses:BankFees", fee), (BANK, -fee)],
        )
    )
    return TaskInstance(
        task_id="bank-recon-missing-fee",
        family="bank-reconciliation",
        title="Reconcile the bank account (missing fee, duplicate import)",
        instruction=(
            "Reconcile `Assets:Bank:Checking` in `/app/ledger.beancount` to "
            "`/app/documents/bank_statement.md` for January 2026. The ledger "
            "contains a duplicated imported payment and is missing the bank "
            "service charge. Correct both by appending new transactions "
            "(never edit or delete existing lines), following `/app/policy.md`, "
            "so the final bank balance equals the statement balance of "
            f"USD {money(statement_balance)}."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": POLICY,
            "chart_of_accounts.md": _chart_md(),
            "documents/bank_statement.md": statement,
        },
        expected=_expected(
            "bank-recon-missing-fee",
            "bank-reconciliation",
            seed,
            expected_deltas={
                BANK: money(payment - fee),
                "Expenses:Utilities": money(-payment),
                "Expenses:BankFees": money(fee),
            },
            expected_new_transactions=[1, 2],
            required_final_balances={BANK: money(statement_balance)},
            reconciliation={
                "account": BANK,
                "statement_balance": money(statement_balance),
            },
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["bank-reconciliation", "duplicate", "bank-fees"],
        skill="analysis",
    )


def prepaid_insurance_adjustment(seed: int) -> TaskInstance:
    rng = random.Random(seed)
    monthly = Decimal(rng.randrange(15000, 40001, 250)) / 100
    total = monthly * 12
    opening = Decimal("10000.00")
    initial = _ledger_header(opening) + _txn(
        "2026-01-01",
        "SafeGuard Insurance",
        "12-month insurance premium paid in advance",
        [("Assets:PrepaidInsurance", total), (BANK, -total)],
    )
    policy_doc = (
        "# Insurance policy\n\nCoverage: 2026-01-01 to 2026-12-31 (12 months).\n"
        f"Premium paid 2026-01-01: USD {money(total)}. "
        f"Monthly cost: USD {money(monthly)}, recognized evenly per month.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "SafeGuard Insurance",
        "January insurance expense (1 of 12 months)",
        [("Expenses:Insurance", monthly), ("Assets:PrepaidInsurance", -monthly)],
    )
    return TaskInstance(
        task_id="prepaid-insurance-adjustment",
        family="adjustments-corrections",
        title="Record the January prepaid-insurance adjustment",
        instruction=(
            "On 2026-01-01 the company prepaid a 12-month insurance premium "
            f"of USD {money(total)} (see `/app/documents/insurance_policy.md` "
            "and the existing entry in `/app/ledger.beancount`). Record the "
            "month-end adjusting entry for January 2026 only, following "
            "`/app/policy.md`. Append exactly one balanced transaction dated "
            "in January 2026; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": POLICY,
            "chart_of_accounts.md": _chart_md(),
            "documents/insurance_policy.md": policy_doc,
        },
        expected=_expected(
            "prepaid-insurance-adjustment",
            "adjustments-corrections",
            seed,
            expected_deltas={
                "Expenses:Insurance": money(monthly),
                "Assets:PrepaidInsurance": money(-monthly),
            },
            required_final_balances={"Assets:PrepaidInsurance": money(total - monthly)},
        ),
        solution_ledger=solution,
        keywords=["prepayment", "adjusting-entry", "accrual"],
    )


def correct_misclassification(seed: int) -> TaskInstance:
    rng = random.Random(seed)
    amount = Decimal(rng.randrange(200000, 600001, 500)) / 100
    vendor = rng.choice(["Dell", "Lenovo", "HP"])
    opening = Decimal("20000.00")
    initial = _ledger_header(opening) + _txn(
        "2026-01-12",
        vendor,
        "Laptop purchase (as recorded)",
        [("Expenses:Repairs", amount), (BANK, -amount)],
    )
    memo = (
        "# Controller memo\n\n"
        f"The 2026-01-12 payment of USD {money(amount)} to {vendor} bought a "
        "laptop with a 4-year useful life. It was incorrectly recorded as "
        "repairs expense. Under `/app/policy.md` it must be capitalized as "
        "equipment. Correct with new entries only; keep the original entry "
        "intact for audit.\n"
    )
    solution = initial + _txn(
        "2026-01-12",
        vendor,
        "Reclassify laptop from repairs expense to equipment",
        [("Assets:Equipment", amount), ("Expenses:Repairs", -amount)],
    )
    return TaskInstance(
        task_id="correct-misclassification",
        family="ledger-integrity-reporting",
        title="Correct a misclassified capital purchase",
        instruction=(
            "Review `/app/documents/controller_memo.md`. Correct the "
            "misclassified 2026-01-12 transaction in `/app/ledger.beancount` "
            "by appending correcting entries only (the original entry must "
            "remain intact), following `/app/policy.md` and "
            "`/app/chart_of_accounts.md`, so the final balances capitalize "
            f"the USD {money(amount)} laptop as equipment."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": POLICY,
            "chart_of_accounts.md": _chart_md(),
            "documents/controller_memo.md": memo,
        },
        expected=_expected(
            "correct-misclassification",
            "ledger-integrity-reporting",
            seed,
            expected_deltas={
                "Assets:Equipment": money(amount),
                "Expenses:Repairs": money(-amount),
            },
            expected_new_transactions=[1, 2],
            required_final_balances={"Assets:Equipment": money(amount)},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["correction", "capitalization", "audit-trail"],
    )


def mc_capitalization_treatment(seed: int) -> TaskInstance:
    """Answer-file shape example: select all correct treatments (MC)."""
    rng = random.Random(seed)
    amount = Decimal(rng.randrange(200000, 600001, 500)) / 100
    vendor = rng.choice(["Dell", "Lenovo", "HP"])
    life = rng.choice([3, 4, 5])
    amt = money(amount)
    statements: list[tuple[str, bool]] = [
        (
            f"Debit Assets:Equipment {amt} USD and credit Assets:Bank:Checking "
            f"{amt} USD on the purchase date.",
            True,
        ),
        (
            "The purchase does not reduce profit on the acquisition date; "
            "cost is recognized over the useful life.",
            True,
        ),
        (
            f"Debit Expenses:Repairs {amt} USD and credit Assets:Bank:Checking "
            f"{amt} USD, expensing the full cost immediately.",
            False,
        ),
        (
            f"Debit Assets:Bank:Checking {amt} USD and credit Income:Sales "
            f"{amt} USD on the purchase date.",
            False,
        ),
        (
            f"Debit Assets:Equipment {amt} USD and credit Expenses:Repairs "
            f"{amt} USD, with no cash movement on the purchase date.",
            False,
        ),
    ]
    rng.shuffle(statements)
    option_ids = ["A", "B", "C", "D", "E"]
    gold = sorted(oid for oid, (_, ok) in zip(option_ids, statements, strict=True) if ok)
    options_md = "\n".join(
        f"- {oid}. {text}" for oid, (text, _) in zip(option_ids, statements, strict=True)
    )
    question = f"""# Question — capitalization treatment

On 2026-01-12 the company bought a laptop from {vendor} for USD {amt},
paid from checking. The laptop has a useful life of {life} years.
Accounting policy: see `/app/policy.md` (items with a useful life over
one year are capitalized; consumables are expensed).

Select **all** statements that correctly describe the required
accounting treatment on the purchase date.

{options_md}

## Answer format

Write `/app/answer.json` as a JSON object, for example:

```json
{{"final_answer": ["A", "C"], "confidence": 80}}
```

`final_answer` lists the selected option ids; `confidence` is your
self-assessed probability (0-100) that the selection is fully correct.
Incorrect selections are penalized, so select only statements you
believe are correct.
"""
    return TaskInstance(
        task_id="mc-capitalization-treatment",
        family="transaction-classification",
        title="Select the correct capitalization treatments",
        instruction=(
            "Answer the multiple-choice question in `/app/question.md` "
            "following `/app/policy.md`. Write your selection to "
            "`/app/answer.json` in the exact format shown in the question."
        ),
        app_files={
            "question.md": question,
            "policy.md": POLICY,
            "chart_of_accounts.md": _chart_md(),
            "answer.example.json": '{\n  "final_answer": ["A"],\n  "confidence": 50\n}\n',
        },
        expected=_expected(
            "mc-capitalization-treatment",
            "transaction-classification",
            seed,
            format="multiple-choice",
            scenario_amount=amt,
            gold=gold,
            options=option_ids,
            expected_deltas={},
            expected_new_transactions=0,
            expected_period=None,
        ),
        solution_ledger="",
        solution_answer={"final_answer": gold, "confidence": 100},
        keywords=["multiple-choice", "capitalization"],
        format="multiple-choice",
    )


MGMT_POLICY = """# Management accounting conventions (applies to this task)

- Break-even units = total fixed costs / contribution margin per unit.
- Contribution margin per unit = selling price - variable cost per unit.
- Ignore taxes and financing. Current sales volume is context only.
- Answer with the exact unit count in `/app/answer.json`.
"""


def mgmt_break_even_units(seed: int) -> TaskInstance:
    """Numeric shape example: cost-volume-profit break-even units."""
    rng = random.Random(seed)
    units = rng.randrange(400, 3001, 25)
    margin = Decimal(rng.randrange(500, 5001, 50)) / 100
    variable = Decimal(rng.randrange(1000, 8001, 50)) / 100
    price = variable + margin
    fixed = margin * units
    current_volume = units + rng.randrange(100, 901, 50)
    question = f"""# Question — break-even units

A product line has the following monthly data (see also
`/app/documents/cost_data.md`):

- Selling price: USD {money(price)} per unit
- Variable cost: USD {money(variable)} per unit
- Total fixed costs: USD {money(fixed)} per month
- Current sales volume: {current_volume} units per month

Using the conventions in `/app/policy.md`, compute the monthly
**break-even volume in units**.

## Answer format

Write `/app/answer.json` as a JSON object, for example:

```json
{{"final_answer": 1200, "confidence": 80}}
```

`final_answer` is the unit count (a number); `confidence` is your
self-assessed probability (0-100) that the value is correct.
"""
    cost_data = (
        "# Cost data (monthly)\n\n"
        f"| Item | Value |\n|---|---|\n"
        f"| Selling price / unit | USD {money(price)} |\n"
        f"| Variable cost / unit | USD {money(variable)} |\n"
        f"| Total fixed costs | USD {money(fixed)} |\n"
        f"| Current volume | {current_volume} units |\n"
    )
    return TaskInstance(
        task_id="mgmt-break-even-units",
        family="cost-volume-profit",
        title="Compute monthly break-even units",
        instruction=(
            "Compute the break-even volume asked in `/app/question.md` "
            "using `/app/documents/cost_data.md` and `/app/policy.md`. "
            "Write the result to `/app/answer.json` in the exact format "
            "shown in the question."
        ),
        app_files={
            "question.md": question,
            "policy.md": MGMT_POLICY,
            "documents/cost_data.md": cost_data,
            "answer.example.json": '{\n  "final_answer": 1000,\n  "confidence": 50\n}\n',
        },
        expected=_expected(
            "mgmt-break-even-units",
            "cost-volume-profit",
            seed,
            format="numeric",
            gold=str(units),
            abs_tolerance="1",
            rel_tolerance="0",
            expected_deltas={},
            expected_new_transactions=0,
            expected_period=None,
        ),
        solution_ledger="",
        solution_answer={"final_answer": units, "confidence": 100},
        keywords=["numeric", "break-even", "cvp"],
        category="management-accounting",
        format="numeric",
    )


IFRS_POLICY = (
    POLICY
    + """
## IFRS policy for this task (IAS 23)

Borrowing costs directly attributable to acquiring or constructing a
qualifying asset (one that necessarily takes a substantial period to
get ready for use) are capitalized as part of the asset's cost during
construction. Other borrowing costs are expensed as interest.
"""
)


def ifrs_capitalize_borrowing_costs(seed: int) -> TaskInstance:
    """IFRS framework example: capitalize qualifying borrowing costs."""
    rng = random.Random(seed)
    interest = Decimal(rng.randrange(80000, 300001, 250)) / 100
    construction = Decimal(rng.randrange(2000000, 4000001, 10000)) / 100
    opening = Decimal("50000.00")
    initial = _ledger_header(opening) + _txn(
        "2026-01-05",
        "BuildCo",
        "Equipment construction costs (qualifying asset, in progress)",
        [("Assets:Equipment", construction), (BANK, -construction)],
    )
    statement = (
        "# Construction loan statement — January 2026\n\n"
        "The loan finances only the equipment under construction above "
        "(completion expected 2026-09). Interest for January, paid from "
        f"checking on 2026-01-20: USD {money(interest)}.\n"
    )
    solution = initial + _txn(
        "2026-01-20",
        "Bank",
        "Capitalize borrowing costs on qualifying asset (IAS 23)",
        [("Assets:Equipment", interest), (BANK, -interest)],
    )
    return TaskInstance(
        task_id="ifrs-capitalize-borrowing-costs",
        family="adjustments-corrections",
        title="Capitalize borrowing costs on a qualifying asset (IFRS)",
        instruction=(
            "Record the January construction-loan interest in "
            "`/app/documents/loan_statement.md` in `/app/ledger.beancount` "
            "under IFRS as stated in `/app/policy.md`. Append exactly one "
            "balanced transaction; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": IFRS_POLICY,
            "chart_of_accounts.md": _chart_md(),
            "documents/loan_statement.md": statement,
        },
        expected=_expected(
            "ifrs-capitalize-borrowing-costs",
            "adjustments-corrections",
            seed,
            expected_deltas={
                "Assets:Equipment": money(interest),
                BANK: money(-interest),
            },
            required_final_balances={
                BANK: money(opening - construction - interest),
                "Assets:Equipment": money(construction + interest),
            },
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["ifrs", "ias-23", "borrowing-costs"],
        framework="ifrs",
        level="professional",
        standards=["ias:23"],
    )


INVENTORY = "Assets:Inventory"
COST_OF_SALES = "Expenses:CostOfSales"
WRITE_DOWN = "Expenses:InventoryWriteDown"
INVENTORY_ACCOUNTS = [
    (INVENTORY, "Inventory of goods held for sale (FIFO cost)"),
    (COST_OF_SALES, "Cost of goods sold"),
    (WRITE_DOWN, "Write-down of inventory to net realizable value"),
]


def _fifo_issue(layers: list[list[Decimal]], units: int) -> Decimal:
    """Consume `units` from FIFO layers [[qty, unit_cost], ...]; return cost."""
    cost = Decimal("0")
    while units:
        take = min(units, int(layers[0][0]))
        cost += take * layers[0][1]
        layers[0][0] -= take
        units -= take
        if not layers[0][0]:
            layers.pop(0)
    return cost


def inventory_costing_nrv(seed: int) -> TaskInstance:
    rng = random.Random(seed)
    item = rng.choice(
        ["ceramic planters", "trail backpacks", "LED desk lamps", "steel water bottles"]
    )
    q0, q1, q2 = rng.randint(20, 60), rng.randint(40, 90), rng.randint(40, 90)
    c0 = Decimal(rng.randrange(1200, 2201, 25)) / 100
    c1 = c0 + Decimal(rng.randrange(50, 301, 25)) / 100
    c2 = c1 + Decimal(rng.randrange(50, 301, 25)) / 100
    s1 = rng.randint(q0 // 2, q0 + q1 // 2)
    s2 = rng.randint(10, q0 + q1 - s1 + q2 // 2)
    price = (c2 * Decimal("1.8")).quantize(Decimal("1"))
    layers = [[Decimal(q0), c0], [Decimal(q1), c1], [Decimal(q2), c2]]
    # Issues happen in date order: purchase 1 arrives before sale 1, purchase 2 after.
    cogs = _fifo_issue(layers, s1) + _fifo_issue(layers, s2)
    ending_units = q0 + q1 + q2 - s1 - s2
    ending_cost = sum(q * c for q, c in layers)
    lowest_layer = min(c for _, c in layers)
    selling = (
        lowest_layer - Decimal(rng.randrange(100, 401, 25)) / 100 + Decimal("2.00")
    ).quantize(CENT)
    selling_costs = Decimal("2.00")
    nrv = selling - selling_costs  # below every remaining layer's cost
    write_down = ending_cost - nrv * ending_units
    opening = Decimal("20000.00")
    initial = (
        _ledger_header(opening, INVENTORY_ACCOUNTS)
        + _txn(
            "2026-01-01",
            "Opening",
            f"Opening inventory: {q0} {item} @ {money(c0)}",
            [(INVENTORY, q0 * c0), ("Equity:Opening-Balances", -q0 * c0)],
        )
        + _txn(
            "2026-01-05",
            "Supplier",
            f"Purchase {q1} {item} @ {money(c1)}",
            [(INVENTORY, q1 * c1), (BANK, -q1 * c1)],
        )
        + _txn(
            "2026-01-12",
            "Customers",
            f"Sales: {s1} {item} @ {money(price)}",
            [(BANK, s1 * price), ("Income:Sales", -s1 * price)],
        )
        + _txn(
            "2026-01-18",
            "Supplier",
            f"Purchase {q2} {item} @ {money(c2)}",
            [(INVENTORY, q2 * c2), (BANK, -q2 * c2)],
        )
        + _txn(
            "2026-01-26",
            "Customers",
            f"Sales: {s2} {item} @ {money(price)}",
            [(BANK, s2 * price), ("Income:Sales", -s2 * price)],
        )
    )
    card = (
        f"# Inventory card — {item}, January 2026\n\n"
        "| Date | Movement | Units | Unit cost (USD) |\n|---|---|---:|---:|\n"
        f"| 2026-01-01 | Opening balance | {q0} | {money(c0)} |\n"
        f"| 2026-01-05 | Purchase | {q1} | {money(c1)} |\n"
        f"| 2026-01-12 | Sale | {s1} | |\n"
        f"| 2026-01-18 | Purchase | {q2} | {money(c2)} |\n"
        f"| 2026-01-26 | Sale | {s2} | |\n"
        f"\nUnits on hand 2026-01-31 (count agrees): {ending_units}\n"
    )
    quote = (
        f"# Month-end market check — {item}\n\n"
        f"A competitor's clearance has cut the market price. Estimated selling price "
        f"at 2026-01-31: USD {money(selling)} per unit; estimated costs to sell: "
        f"USD {money(selling_costs)} per unit.\n"
    )
    policy = POLICY + (
        "- Inventory uses a perpetual FIFO system. Sales are already recorded;\n"
        "  cost of sales has not been posted for January.\n"
        "- At month-end inventory is measured at the lower of FIFO cost and net\n"
        "  realizable value (estimated selling price less costs to sell), item\n"
        "  by item; any write-down goes to `Expenses:InventoryWriteDown`.\n"
    )
    solution = (
        initial
        + _txn(
            "2026-01-31",
            "Inventory",
            "January cost of sales (FIFO)",
            [(COST_OF_SALES, cogs), (INVENTORY, -cogs)],
        )
        + _txn(
            "2026-01-31",
            "Inventory",
            "Write down inventory to net realizable value",
            [(WRITE_DOWN, write_down), (INVENTORY, -write_down)],
        )
    )
    return TaskInstance(
        task_id="inventory-costing-nrv",
        family="inventory",
        title="Post FIFO cost of sales and an NRV write-down",
        instruction=(
            f"Complete January 2026 inventory accounting for {item} in `/app/ledger.beancount`: "
            "post cost of sales and measure month-end inventory, using "
            "`/app/documents/inventory_card.md`, `/app/documents/market_check.md`, and "
            "`/app/policy.md`. Append new transactions dated 2026-01-31 or earlier in January; "
            "do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(INVENTORY_ACCOUNTS),
            "documents/inventory_card.md": card,
            "documents/market_check.md": quote,
        },
        expected=_expected(
            "inventory-costing-nrv",
            "inventory",
            seed,
            expected_deltas={
                COST_OF_SALES: money(cogs),
                WRITE_DOWN: money(write_down),
                INVENTORY: money(-(cogs + write_down)),
            },
            expected_new_transactions=[1, 3],
            required_final_balances={INVENTORY: money(nrv * ending_units)},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["inventory", "fifo", "cost-of-sales", "net-realizable-value"],
    )


FAMILIES = {
    "classify-operating-expense": classify_operating_expense,
    "bank-recon-missing-fee": bank_recon_missing_fee,
    "prepaid-insurance-adjustment": prepaid_insurance_adjustment,
    "correct-misclassification": correct_misclassification,
    "mc-capitalization-treatment": mc_capitalization_treatment,
    "mgmt-break-even-units": mgmt_break_even_units,
    "ifrs-capitalize-borrowing-costs": ifrs_capitalize_borrowing_costs,
    "inventory-costing-nrv": inventory_costing_nrv,
}

# Frozen Stable-track seeds for the committed tasks under tasks/.
STABLE_SEEDS = {
    "classify-operating-expense": 101,
    "bank-recon-missing-fee": 102,
    "prepaid-insurance-adjustment": 103,
    "correct-misclassification": 104,
    "mc-capitalization-treatment": 105,
    "mgmt-break-even-units": 106,
    "ifrs-capitalize-borrowing-costs": 107,
    "inventory-costing-nrv": 112,
}
