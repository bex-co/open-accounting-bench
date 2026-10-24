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


AR = "Assets:AccountsReceivable"
ALLOWANCE = "Assets:AllowanceForDoubtfulAccounts"
BAD_DEBTS = "Expenses:BadDebts"
RECEIVABLE_ACCOUNTS = [
    (AR, "Trade receivables (customer invoices on credit)"),
    (ALLOWANCE, "Allowance for doubtful accounts (contra-asset; credit balance)"),
    (BAD_DEBTS, "Bad-debt (credit-loss) expense"),
]
# Aging bucket -> expected loss rate (policy). Bucket amounts are whole
# hundreds, so every rate x amount is exact to the cent.
AGING_RATES = [
    ("Current", Decimal("0.01")),
    ("1-30 days past due", Decimal("0.03")),
    ("31-90 days past due", Decimal("0.10")),
    ("Over 90 days past due", Decimal("0.40")),
]
CUSTOMERS = [
    "Birch & Co",
    "Cobalt Retail",
    "Delta Foods",
    "Evergreen Labs",
    "Fjord Outfitters",
    "Granite Supply",
    "Harbor Clinics",
    "Ivory Studio",
    "Juniper Hotels",
    "Kestrel Media",
]


def receivable_allowance_trueup(seed: int) -> TaskInstance:
    rng = random.Random(seed)
    names = rng.sample(CUSTOMERS, 7)
    # (invoice id, customer, bucket index, amount); January invoices are Current.
    ids = rng.sample(range(1000, 10000), 7)
    invoices = [
        (f"INV-{ids[i]}", name, bucket, Decimal(rng.randrange(8, 61)) * 100)
        for i, (name, bucket) in enumerate(zip(names, [0, 0, 1, 1, 2, 3, 3], strict=True))
    ]
    bad = invoices[-1]  # one over-90-day invoice is uncollectible
    remaining = [inv for inv in invoices if inv is not bad]
    required = sum(AGING_RATES[b][1] * amt for _, _, b, amt in remaining).quantize(CENT)
    write_off = bad[3]
    # Allowance credit balance at 2026-01-01: covers the write-off but falls
    # short of the requirement, so the true-up is always a positive expense.
    low, high = int(write_off) // 25 + 4, int(required + write_off) // 25 - 4
    existing = Decimal(rng.randrange(low, high + 1)) * 25
    opening = Decimal("10000.00")
    prior = [inv for inv in invoices if inv[2] > 0]
    january = [inv for inv in invoices if inv[2] == 0]
    prior_total = sum(inv[3] for inv in prior)
    initial = _ledger_header(opening, RECEIVABLE_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        "Opening receivables (2025 invoices) and allowance",
        [
            (AR, prior_total),
            (ALLOWANCE, -existing),
            ("Equity:Opening-Balances", existing - prior_total),
        ],
    )
    for k, (inv, name, _, amount) in enumerate(january):
        initial += _txn(
            f"2026-01-{12 + 7 * k:02d}",
            name,
            f"Invoice {inv} on credit",
            [(AR, amount), ("Income:Sales", -amount)],
        )
    adjustment = required - (existing - write_off)
    rows = "\n".join(
        f"| {inv} | {name} | {AGING_RATES[b][0]} | {money(amt)} |" for inv, name, b, amt in invoices
    )
    aging = (
        "# Accounts receivable aging — 2026-01-31\n\n"
        "| Invoice | Customer | Bucket | Amount (USD) |\n|---|---|---|---:|\n"
        f"{rows}\n\nTotal: USD {money(sum(inv[3] for inv in invoices))}\n"
    )
    memo = (
        "# Credit memo — write-off approval\n\n"
        f"Customer {bad[1]} filed for liquidation on 2026-01-27. Invoice {bad[0]} "
        f"(USD {money(write_off)}) is uncollectible. Approved for write-off as of 2026-01-31.\n"
    )
    policy = POLICY + (
        "- Receivables are carried net of an allowance for doubtful accounts.\n"
        "  At month-end: first write off invoices approved as uncollectible,\n"
        "  then adjust the allowance so its balance equals the required\n"
        "  allowance: the loss rate for each aging bucket times the bucket's\n"
        "  remaining invoices (Current 1%, 1-30 days 3%, 31-90 days 10%,\n"
        "  over 90 days 40%), summed. The adjustment is bad-debt expense.\n"
    )
    solution = (
        initial
        + _txn(
            "2026-01-31",
            bad[1],
            f"Write off uncollectible invoice {bad[0]}",
            [(ALLOWANCE, write_off), (AR, -write_off)],
        )
        + _txn(
            "2026-01-31",
            "Allowance",
            "Adjust allowance to aging requirement",
            [(BAD_DEBTS, adjustment), (ALLOWANCE, -adjustment)],
        )
    )
    ar_final = sum(inv[3] for inv in remaining)
    return TaskInstance(
        task_id="receivable-allowance-trueup",
        family="receivables",
        title="Write off a bad debt and true up the allowance",
        instruction=(
            "Close January 2026 receivables in `/app/ledger.beancount`: process the write-off "
            "approved in `/app/documents/credit_memo.md` and bring the allowance for doubtful "
            "accounts to the balance `/app/policy.md` requires, using the aging in "
            "`/app/documents/aging.md`. Append new transactions dated 2026-01-31 only; do not "
            "edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(RECEIVABLE_ACCOUNTS),
            "documents/aging.md": aging,
            "documents/credit_memo.md": memo,
        },
        expected=_expected(
            "receivable-allowance-trueup",
            "receivables",
            seed,
            expected_deltas={
                AR: money(-write_off),
                ALLOWANCE: money(existing - required),
                BAD_DEBTS: money(adjustment),
            },
            expected_new_transactions=[1, 2],
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={AR: money(ar_final), ALLOWANCE: money(-required)},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["receivables", "allowance", "bad-debt", "write-off"],
    )


ACCRUED = "Liabilities:AccruedExpenses"
DEFERRED = "Liabilities:DeferredRevenue"
SERVICES = "Income:Services"
ACCRUAL_ACCOUNTS = [
    (ACCRUED, "Expenses incurred but not yet billed (accrued at period end)"),
    (DEFERRED, "Cash received for services not yet delivered"),
    (SERVICES, "Service revenue (recognized as delivered)"),
]


def accrual_deferral_reversal(seed: int) -> TaskInstance:
    rng = random.Random(seed)
    utility = rng.choice(["City Power", "Metro Gas", "Northside Energy"])
    estimate = Decimal(rng.randrange(80, 241)) * 5
    actual = estimate + Decimal(rng.choice([-1, 1])) * Decimal(rng.randrange(4, 31)) * 5
    client = rng.choice(["Orion Dental", "Pike Logistics", "Quarry Arts", "Rowan Legal"])
    sessions = rng.choice([8, 10, 12])
    price = Decimal(rng.randrange(30, 91)) * 10
    delivered = rng.randint(2, 4)
    days = sorted(rng.sample(range(6, 29), delivered))
    opening = Decimal("10000.00")
    deferred_open = price * sessions
    initial = _ledger_header(opening, ACCRUAL_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        "December 2025 closing balances: utilities accrual and workshop prepayment",
        [
            (ACCRUED, -estimate),
            (DEFERRED, -deferred_open),
            ("Equity:Opening-Balances", estimate + deferred_open),
        ],
    )
    close_note = (
        "# December 2025 close — open items carried into January\n\n"
        f"- Accrued utilities: December usage from {utility} not yet billed, "
        f"estimated at USD {money(estimate)} (credit `{ACCRUED}`).\n"
        f"- Deferred revenue: {client} prepaid {sessions} training sessions at "
        f"USD {money(price)} each on 2025-12-20 (credit `{DEFERRED}` "
        f"USD {money(deferred_open)}).\n"
    )
    bill = (
        f"# Utility bill — {utility}\n\n"
        "Service period: 2025-12-01 to 2025-12-31\n"
        f"Amount due: USD {money(actual)}. Paid from checking on 2026-01-15.\n"
    )
    log = (
        f"# Training delivery log — {client}\n\n"
        + "".join(f"- 2026-01-{d:02d}: session delivered\n" for d in days)
        + f"\nSessions remaining after January: {sessions - delivered}\n"
    )
    policy = POLICY + (
        "- Accrued expenses are reversed on the first day of the next period;\n"
        "  the supplier's bill is then recorded in full when received.\n"
        "- Prepaid service contracts are recognized as revenue per session\n"
        "  delivered, at the contract price per session.\n"
    )
    earned = price * delivered
    solution = (
        initial
        + _txn(
            "2026-01-01",
            utility,
            "Reverse December utilities accrual",
            [(ACCRUED, estimate), ("Expenses:Utilities", -estimate)],
        )
        + _txn(
            "2026-01-15",
            utility,
            "December utility bill paid",
            [("Expenses:Utilities", actual), (BANK, -actual)],
        )
        + _txn(
            "2026-01-31",
            client,
            f"Revenue for {delivered} sessions delivered in January",
            [(DEFERRED, earned), (SERVICES, -earned)],
        )
    )
    return TaskInstance(
        task_id="accrual-deferral-reversal",
        family="accruals-deferrals",
        title="Reverse an accrual and release deferred revenue",
        instruction=(
            "Record January 2026 in `/app/ledger.beancount` for the items carried over in "
            "`/app/documents/december_close.md`: the utility bill in "
            "`/app/documents/utility_bill.md` and the sessions in "
            "`/app/documents/delivery_log.md`, following `/app/policy.md`. Append new "
            "transactions dated in January 2026 only; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(ACCRUAL_ACCOUNTS),
            "documents/december_close.md": close_note,
            "documents/utility_bill.md": bill,
            "documents/delivery_log.md": log,
        },
        expected=_expected(
            "accrual-deferral-reversal",
            "accruals-deferrals",
            seed,
            expected_deltas={
                ACCRUED: money(estimate),
                "Expenses:Utilities": money(actual - estimate),
                BANK: money(-actual),
                DEFERRED: money(earned),
                SERVICES: money(-earned),
            },
            expected_new_transactions=[2, 4],
            required_final_balances={
                ACCRUED: "0.00",
                DEFERRED: money(-(deferred_open - earned)),
                BANK: money(opening - actual),
            },
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["accrual", "reversal", "deferred-revenue", "period-end"],
    )


AP = "Liabilities:AccountsPayable"
MATERIALS = "Expenses:Materials"
PAYABLE_ACCOUNTS = [
    (AP, "Trade payables (supplier invoices on credit)"),
    (MATERIALS, "Materials purchased and consumed"),
]


def payables_statement_recon(seed: int) -> TaskInstance:
    rng = random.Random(seed)
    supplier = rng.choice(["Apex Components", "Bolt & Nut Supply", "Crestline Materials"])
    ids = rng.sample(range(200, 1000), 5)
    opening_ap = Decimal(rng.randrange(20, 61)) * 100  # December invoice, unpaid
    inv_a = Decimal(rng.randrange(8, 31)) * 100
    # Transposition: ledger swaps the hundreds and tens digits of the true amount.
    thousands = rng.randint(1, 4)
    hundreds, tens = rng.sample(range(1, 10), 2)
    true_b = Decimal(thousands * 1000 + hundreds * 100 + tens * 10)
    booked_b = Decimal(thousands * 1000 + tens * 100 + hundreds * 10)
    credit_note = Decimal(rng.randrange(2, 9)) * 50
    in_transit = Decimal(rng.randrange(6, 25)) * 100
    payment = opening_ap  # pays the December invoice on 2026-01-30
    dec_inv, a_id, b_id, cn_id, t_id = (f"{n}" for n in ids)
    opening = Decimal("20000.00")
    initial = (
        _ledger_header(opening, PAYABLE_ACCOUNTS)
        + _txn(
            "2026-01-01",
            supplier,
            f"Opening payable: December invoice {dec_inv}",
            [("Equity:Opening-Balances", opening_ap), (AP, -opening_ap)],
        )
        + _txn("2026-01-08", supplier, f"Invoice {a_id}", [(MATERIALS, inv_a), (AP, -inv_a)])
        + _txn("2026-01-16", supplier, f"Invoice {b_id}", [(MATERIALS, booked_b), (AP, -booked_b)])
        + _txn(
            "2026-01-30",
            supplier,
            f"Payment of invoice {dec_inv}",
            [(AP, payment), (BANK, -payment)],
        )
    )
    statement_balance = opening_ap + inv_a + true_b - credit_note + in_transit
    statement = (
        f"# Supplier statement — {supplier}, as at 2026-01-31\n\n"
        "| Date | Reference | Debit (owed) | Credit |\n|---|---|---:|---:|\n"
        f"| 2025-12-18 | Invoice {dec_inv} | {money(opening_ap)} | |\n"
        f"| 2026-01-08 | Invoice {a_id} | {money(inv_a)} | |\n"
        f"| 2026-01-16 | Invoice {b_id} | {money(true_b)} | |\n"
        f"| 2026-01-22 | Credit note {cn_id} (returned goods) | | {money(credit_note)} |\n"
        f"| 2026-01-31 | Invoice {t_id} (goods dispatched 2026-01-31) | {money(in_transit)} | |\n"
        f"\nBalance due: USD {money(statement_balance)}\n"
    )
    receiving = (
        "# Goods received log — January 2026\n\n"
        f"- 2026-01-08: {supplier} delivery, invoice {a_id}, accepted\n"
        f"- 2026-01-16: {supplier} delivery, invoice {b_id}, accepted\n"
        f"- 2026-01-22: returned damaged items to {supplier} (credit note {cn_id} expected)\n"
        f"- No delivery for invoice {t_id} received by 2026-01-31\n"
    )
    policy = POLICY + (
        "- Supplier statements are reconciled at month-end. Correct only errors\n"
        "  in our ledger (unrecorded credit notes, mis-keyed amounts) against\n"
        "  the purchase account. Timing differences are not errors: purchases\n"
        "  are recorded when goods are received, and payments we have sent\n"
        "  may not yet appear on the supplier's statement.\n"
    )
    diff = booked_b - true_b
    solution = (
        initial
        + _txn(
            "2026-01-31",
            supplier,
            f"Credit note {cn_id} for returned goods",
            [(AP, credit_note), (MATERIALS, -credit_note)],
        )
        + _txn(
            "2026-01-31",
            supplier,
            f"Correct mis-keyed invoice {b_id}",
            [(AP, diff), (MATERIALS, -diff)],
        )
    )
    ledger_final = opening_ap + inv_a + true_b - credit_note - payment
    return TaskInstance(
        task_id="payables-statement-recon",
        family="payables-reconciliation",
        title="Reconcile a supplier statement",
        instruction=(
            f"Reconcile the {supplier} balance in `{AP}` in `/app/ledger.beancount` to "
            "`/app/documents/supplier_statement.md` as at 2026-01-31, using "
            "`/app/documents/goods_received.md` and `/app/policy.md`. Append correcting "
            "transactions dated 2026-01-31 for any errors in our ledger; do not edit "
            "existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(PAYABLE_ACCOUNTS),
            "documents/supplier_statement.md": statement,
            "documents/goods_received.md": receiving,
        },
        expected=_expected(
            "payables-statement-recon",
            "payables-reconciliation",
            seed,
            expected_deltas={
                AP: money(credit_note + diff),
                MATERIALS: money(-(credit_note + diff)),
            },
            expected_new_transactions=[1, 2],
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={AP: money(-ledger_final), BANK: money(opening - payment)},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["payables", "supplier-statement", "reconciliation", "timing-differences"],
        skill="analysis",
    )


FAMILIES = {
    "classify-operating-expense": classify_operating_expense,
    "bank-recon-missing-fee": bank_recon_missing_fee,
    "prepaid-insurance-adjustment": prepaid_insurance_adjustment,
    "correct-misclassification": correct_misclassification,
    "mc-capitalization-treatment": mc_capitalization_treatment,
    "mgmt-break-even-units": mgmt_break_even_units,
    "ifrs-capitalize-borrowing-costs": ifrs_capitalize_borrowing_costs,
    "receivable-allowance-trueup": receivable_allowance_trueup,
    "accrual-deferral-reversal": accrual_deferral_reversal,
    "payables-statement-recon": payables_statement_recon,
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
    "receivable-allowance-trueup": 108,
    "accrual-deferral-reversal": 109,
    "payables-statement-recon": 110,
}
