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
        level="vocational",
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
        level="vocational",
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
        level="vocational",
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
        level="vocational",
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
        level="vocational",
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
        level="vocational",
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


ACC_DEP = "Assets:AccumulatedDepreciation"
DEPRECIATION = "Expenses:Depreciation"
DISPOSAL = "Income:GainLossOnDisposal"
DISPOSAL_ACCOUNTS = [
    (ACC_DEP, "Accumulated depreciation on equipment (contra-asset; credit balance)"),
    (DEPRECIATION, "Depreciation expense"),
    (DISPOSAL, "Gain (credit) or loss (debit) on disposal of non-current assets"),
]


def ppe_disposal(seed: int) -> TaskInstance:
    rng = random.Random(seed)
    asset = rng.choice(["delivery van", "CNC router", "forklift", "packaging line"])
    buyer = rng.choice(["Lumen Fleet", "Northgate Machinery", "Oakridge Auctions"])
    life_years = rng.choice([3, 4, 5])
    monthly = Decimal(rng.randrange(150, 601))  # whole dollars per month
    residual = Decimal(rng.randrange(5, 31)) * 100
    cost = monthly * 12 * life_years + residual
    held = rng.randint(10, life_years * 12 - 6)  # months depreciated through 2025-12-31
    # First depreciated month is the acquisition month; `held` months run
    # through December 2025 inclusive.
    first = 2025 * 12 + 11 - (held - 1)
    acquired_year, acquired_month = first // 12, first % 12 + 1
    acc_open = monthly * held
    carrying = cost - monthly * (held + 1)  # after January's depreciation
    sign, offset = rng.choice([-1, 1]), Decimal(rng.randrange(2, 41)) * 50
    if sign < 0:  # a loss never exceeds half the carrying amount: proceeds stay positive
        offset = min(offset, (carrying / 2 // 50) * 50)
    proceeds = carrying + sign * offset
    gain = proceeds - carrying
    sale_day = rng.randint(8, 27)
    sale_date = f"2026-01-{sale_day:02d}"
    opening = Decimal("10000.00")
    initial = _ledger_header(opening, DISPOSAL_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        f"Opening fixed asset: {asset}",
        [
            ("Assets:Equipment", cost),
            (ACC_DEP, -acc_open),
            ("Equity:Opening-Balances", acc_open - cost),
        ],
    )
    register = (
        "# Fixed asset register (extract)\n\n"
        f"- Asset: {asset}\n"
        f"- Acquired: {acquired_year}-{acquired_month:02d}-01, cost USD {money(cost)}\n"
        f"- Useful life {life_years} years, residual value USD {money(residual)}, straight-line\n"
        f"- Accumulated depreciation through 2025-12-31: USD {money(acc_open)} ({held} months)\n"
    )
    sale = (
        f"# Sale agreement — {asset}\n\n"
        f"Sold to {buyer} on {sale_date} for USD {money(proceeds)}, "
        "received in full into checking the same day.\n"
    )
    policy = POLICY + (
        "- Equipment is depreciated straight-line per month: (cost - residual)\n"
        "  / useful life in months. A full month's depreciation is charged in\n"
        "  the month of acquisition and in the month of disposal.\n"
        "- On disposal, remove the asset's cost and accumulated depreciation;\n"
        "  the difference between proceeds and carrying amount is a gain or\n"
        "  loss on disposal.\n"
    )
    solution = (
        initial
        + _txn(
            sale_date,
            "Depreciation",
            f"January depreciation, {asset}",
            [(DEPRECIATION, monthly), (ACC_DEP, -monthly)],
        )
        + _txn(
            sale_date,
            buyer,
            f"Disposal of {asset}",
            [
                (BANK, proceeds),
                (ACC_DEP, acc_open + monthly),
                ("Assets:Equipment", -cost),
                (DISPOSAL, -gain),
            ],
        )
    )
    return TaskInstance(
        task_id="ppe-disposal",
        family="fixed-assets",
        title="Record the disposal of a depreciated asset",
        instruction=(
            f"Record the sale of the {asset} described in `/app/documents/sale_agreement.md` "
            "in `/app/ledger.beancount`, using `/app/documents/asset_register.md` and "
            "`/app/policy.md`. Append new transactions dated in January 2026 only; do not "
            "edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(DISPOSAL_ACCOUNTS),
            "documents/asset_register.md": register,
            "documents/sale_agreement.md": sale,
        },
        expected=_expected(
            "ppe-disposal",
            "fixed-assets",
            seed,
            expected_deltas={
                DEPRECIATION: money(monthly),
                ACC_DEP: money(acc_open),
                "Assets:Equipment": money(-cost),
                BANK: money(proceeds),
                DISPOSAL: money(-gain),
            },
            expected_new_transactions=[1, 2],
            required_final_balances={"Assets:Equipment": "0.00", ACC_DEP: "0.00"},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["fixed-assets", "depreciation", "disposal", "gain-loss"],
        level="vocational",
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
        level="vocational",
    )


CONTRACT_LIABILITY = "Liabilities:ContractLiability"
PRODUCT_REVENUE = "Income:ProductRevenue"
SUPPORT_REVENUE = "Income:SupportRevenue"
REVENUE_ACCOUNTS = [
    (CONTRACT_LIABILITY, "Consideration received for obligations not yet satisfied"),
    (PRODUCT_REVENUE, "Revenue from hardware delivered"),
    (SUPPORT_REVENUE, "Revenue from support services rendered"),
]


def revenue_bundle_allocation(seed: int) -> TaskInstance:
    rng = random.Random(seed)
    customer = rng.choice(["Summit Clinics", "Tidewater Schools", "Uplands Logistics"])
    product = rng.choice(["point-of-sale terminals", "network appliances", "label printers"])
    ssp_hw = Decimal(rng.randrange(40, 151)) * 100
    ssp_support = Decimal(rng.randrange(2, 9)) * 1200
    factor = rng.choice([Decimal("0.80"), Decimal("0.85"), Decimal("0.90")])
    price = (ssp_hw + ssp_support) * factor
    alloc_hw = ssp_hw * factor
    alloc_support = ssp_support * factor
    monthly = alloc_support / 12  # exact: ssp_support is a multiple of 1200
    # The invoice prices the support line low and loads the discount elsewhere.
    invoice_support = (ssp_support * Decimal("0.25")).quantize(Decimal("1"))
    invoice_hw = price - invoice_support
    opening = Decimal("10000.00")
    initial = _ledger_header(opening, REVENUE_ACCOUNTS) + _txn(
        "2026-01-02",
        customer,
        "Contract signed; full consideration received in advance",
        [(BANK, price), (CONTRACT_LIABILITY, -price)],
    )
    contract = (
        f"# Contract summary — {customer}\n\n"
        f"Signed 2026-01-02. Single price USD {money(price)}, paid in full on signing, for:\n\n"
        f"1. {product.capitalize()} — delivered and accepted 2026-01-02.\n"
        "2. Support and software updates for 12 months, 2026-01-01 to 2026-12-31.\n\n"
        "## Invoice lines (as billed)\n\n"
        f"- {product.capitalize()}: USD {money(invoice_hw)}\n"
        f"- 12-month support: USD {money(invoice_support)}\n"
    )
    prices = (
        "# Standalone selling prices (price list, sold separately)\n\n"
        f"- {product.capitalize()}: USD {money(ssp_hw)}\n"
        f"- 12-month support: USD {money(ssp_support)}\n"
    )
    policy = POLICY + (
        "- Revenue (ASC 606 / IFRS 15): allocate a contract's price to each\n"
        "  performance obligation in proportion to standalone selling prices.\n"
        "  Hardware revenue is recognized on delivery; support is recognized\n"
        "  evenly over its term by month. Unearned consideration stays in\n"
        "  `Liabilities:ContractLiability`.\n"
    )
    earned = alloc_hw + monthly
    solution = initial + _txn(
        "2026-01-31",
        customer,
        "January revenue: hardware delivered, 1 of 12 support months",
        [(CONTRACT_LIABILITY, earned), (PRODUCT_REVENUE, -alloc_hw), (SUPPORT_REVENUE, -monthly)],
    )
    return TaskInstance(
        task_id="revenue-bundle-allocation",
        family="revenue-recognition",
        title="Allocate a bundled contract price and recognize January revenue",
        instruction=(
            f"Recognize January 2026 revenue on the {customer} contract in "
            "`/app/ledger.beancount`, using `/app/documents/contract.md`, "
            "`/app/documents/standalone_prices.md`, and `/app/policy.md`. Append new "
            "transactions dated in January 2026 only; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(REVENUE_ACCOUNTS),
            "documents/contract.md": contract,
            "documents/standalone_prices.md": prices,
        },
        expected=_expected(
            "revenue-bundle-allocation",
            "revenue-recognition",
            seed,
            expected_deltas={
                CONTRACT_LIABILITY: money(earned),
                PRODUCT_REVENUE: money(-alloc_hw),
                SUPPORT_REVENUE: money(-monthly),
            },
            expected_new_transactions=[1, 2],
            required_final_balances={CONTRACT_LIABILITY: money(-(price - earned))},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["revenue", "performance-obligations", "allocation", "contract-liability"],
        standards=["asc:606", "ifrs:15"],
    )


SUSPENSE = "Assets:Suspense"
SUSPENSE_ACCOUNTS = [
    (SUSPENSE, "Clearing account for unbalanced imports (must be zero at month-end)")
]


def suspense_clearance(seed: int) -> TaskInstance:
    rng = random.Random(seed)
    takings = Decimal(rng.randrange(400, 1501)) * 2
    lessor = rng.choice(["Parkside Properties", "Quayside Estates", "Redwood Realty"])
    hundreds, tens = rng.sample(range(1, 10), 2)
    thousands = rng.randint(1, 3)
    rent = Decimal(thousands * 1000 + hundreds * 100 + tens * 10)
    keyed = Decimal(thousands * 1000 + tens * 100 + hundreds * 10)  # transposed expense side
    opening = Decimal("15000.00")
    initial = (
        _ledger_header(opening, SUSPENSE_ACCOUNTS)
        + _txn(
            "2026-01-05",
            lessor,
            "January rent (bank import)",
            [("Expenses:Rent", keyed), (BANK, -rent), (SUSPENSE, rent - keyed)],
        )
        + _txn(
            "2026-01-09",
            "Deposit",
            "Counter deposit (bank import, no counter-entry)",
            [(BANK, takings), (SUSPENSE, -takings)],
        )
        + _txn(
            "2026-01-20",
            "City Power",
            "Utilities (bank import)",
            [("Expenses:Utilities", Decimal("212.40")), (BANK, Decimal("-212.40"))],
        )
    )
    balance = (rent - keyed) - takings
    statement = (
        "# Bank statement extract — Checking, January 2026\n\n"
        f"- 2026-01-05 {lessor}, rent January: -{money(rent)} USD\n"
        f"- 2026-01-09 Deposit, shop counter takings (cash sales): +{money(takings)} USD\n"
        "- 2026-01-20 City Power: -212.40 USD\n"
    )
    lease = f"# Lease summary — {lessor}\n\nMonthly rent: USD {money(rent)}, due on the 5th.\n"
    memo = (
        "# Controller memo — month-end\n\n"
        f"`{SUSPENSE}` shows a {'debit' if balance > 0 else 'credit'} balance of "
        f"USD {money(abs(balance))} after the January bank "
        "import. Investigate, correct the underlying postings, and leave the clearing "
        "account at zero.\n"
    )
    policy = POLICY + (
        f"- `{SUSPENSE}` is a temporary clearing account and must be zero at\n"
        "  month-end. Clear it by correcting the postings that created it.\n"
        "- Shop counter takings are cash sales (`Income:Sales`).\n"
    )
    solution = (
        initial
        + _txn(
            "2026-01-31",
            lessor,
            "Correct transposed rent expense",
            [(SUSPENSE, keyed - rent), ("Expenses:Rent", rent - keyed)],
        )
        + _txn(
            "2026-01-31",
            "Deposit",
            "Record counter takings as cash sales",
            [(SUSPENSE, takings), ("Income:Sales", -takings)],
        )
    )
    return TaskInstance(
        task_id="suspense-clearance",
        family="ledger-integrity-reporting",
        title="Clear a suspense balance by correcting its causes",
        instruction=(
            "Follow up the controller memo in `/app/documents/controller_memo.md` for "
            "`/app/ledger.beancount`, using `/app/documents/bank_statement.md`, "
            "`/app/documents/lease.md`, and `/app/policy.md`. Append correcting "
            "transactions dated 2026-01-31; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(SUSPENSE_ACCOUNTS),
            "documents/controller_memo.md": memo,
            "documents/bank_statement.md": statement,
            "documents/lease.md": lease,
        },
        expected=_expected(
            "suspense-clearance",
            "ledger-integrity-reporting",
            seed,
            expected_deltas={
                SUSPENSE: money(-balance),
                "Expenses:Rent": money(rent - keyed),
                "Income:Sales": money(-takings),
            },
            expected_new_transactions=[1, 2],
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={SUSPENSE: "0.00", "Expenses:Rent": money(rent)},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["suspense", "clearing-account", "error-correction", "transposition"],
        skill="analysis",
    )


LOAN = "Liabilities:LoanPayable"
INTEREST_PAYABLE = "Liabilities:InterestPayable"
LOAN_ACCOUNTS = [
    (LOAN, "Term loan at amortized cost (face value less unamortized issue costs)"),
    (INTEREST_PAYABLE, "Coupon interest accrued, not yet paid"),
]


def _monthly_effective_rate(net: Decimal, coupon: Decimal, face: Decimal, months: int) -> Decimal:
    """Monthly rate equating the coupon stream plus face repayment to `net` proceeds."""
    lo, hi = Decimal("0"), Decimal("0.05")
    for _ in range(80):
        mid = (lo + hi) / 2
        pv = sum(coupon / (1 + mid) ** t for t in range(1, months + 1)) + face / (1 + mid) ** months
        lo, hi = (mid, hi) if pv > net else (lo, mid)
    return ((lo + hi) / 2).quantize(Decimal("0.000001"))


def loan_effective_interest(seed: int) -> TaskInstance:
    rng = random.Random(seed)
    lender = rng.choice(["Keystone Bank", "Lakeshore Credit Union", "Meridian Capital"])
    face = Decimal(rng.randrange(5, 21)) * 12000
    annual = rng.choice([Decimal("0.060"), Decimal("0.072"), Decimal("0.084")])
    coupon = face * annual / 12  # exact by construction
    years = rng.choice([3, 4, 5])
    costs = (face * Decimal(rng.randrange(15, 41)) / 1000).quantize(Decimal("1"))
    net = face - costs
    rate = _monthly_effective_rate(net, coupon, face, years * 12)
    expense = (net * rate).quantize(CENT)
    amortization = expense - coupon
    opening = Decimal("5000.00")
    initial = _ledger_header(opening, LOAN_ACCOUNTS) + _txn(
        "2026-01-01",
        lender,
        "Term loan drawn, net of issue costs",
        [(BANK, net), (LOAN, -net)],
    )
    agreement = (
        f"# Loan agreement summary — {lender}\n\n"
        f"- Drawn 2026-01-01; face value USD {money(face)}; "
        f"term {years} years, repaid at maturity\n"
        f"- Coupon {annual * 100:.1f}% a year on face value, paid monthly in arrears "
        "on the 5th of the next month\n"
        f"- Issue costs USD {money(costs)} deducted from proceeds; cash received USD {money(net)}\n"
        f"- Effective interest rate (computed by treasury from these cash flows): "
        f"{rate * 100:.4f}% per month\n"
    )
    policy = POLICY + (
        "- Borrowings are measured at amortized cost using the effective\n"
        "  interest method: monthly interest expense = carrying amount at the\n"
        "  start of the month x the effective monthly rate, rounded to the\n"
        "  cent. Coupon interest due but unpaid is accrued in\n"
        "  `Liabilities:InterestPayable`; the difference adjusts the loan's\n"
        "  carrying amount. Use the effective rate stated in the loan\n"
        "  agreement as given; do not recompute it.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        lender,
        "January interest (effective interest method)",
        [("Expenses:Interest", expense), (INTEREST_PAYABLE, -coupon), (LOAN, -amortization)],
    )
    return TaskInstance(
        task_id="loan-effective-interest",
        family="borrowings",
        title="Accrue January interest on a loan at amortized cost",
        instruction=(
            "Record January 2026 interest on the loan in `/app/ledger.beancount`, using "
            "`/app/documents/loan_agreement.md` and `/app/policy.md`. Append new "
            "transactions dated 2026-01-31; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(LOAN_ACCOUNTS),
            "documents/loan_agreement.md": agreement,
        },
        expected=_expected(
            "loan-effective-interest",
            "borrowings",
            seed,
            expected_deltas={
                "Expenses:Interest": money(expense),
                INTEREST_PAYABLE: money(-coupon),
                LOAN: money(-amortization),
            },
            expected_new_transactions=[1, 2],
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={LOAN: money(-(net + amortization))},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["borrowings", "effective-interest", "amortized-cost", "issue-costs"],
        standards=["asc:835-30", "ifrs:9"],
    )


WAGES = "Expenses:Wages"
WAGES_PAYABLE = "Liabilities:WagesPayable"
SUPPLIES_ASSET = "Assets:Supplies"
SALES_RETURNS = "Income:SalesReturnsAndAllowances"
MERCH_ACCOUNTS = [
    (AR, "Trade receivables (customer invoices on credit)"),
    (INVENTORY, "Inventory of goods held for sale (perpetual)"),
    (COST_OF_SALES, "Cost of goods sold"),
]
MERCH_POLICY = POLICY + (
    "- Perpetual inventory: every sale records revenue at the selling\n"
    "  price and cost of goods sold at unit cost in the same period.\n"
)


def perpetual_sale_with_cost(seed: int) -> TaskInstance:
    """Scenario: credit sale under perpetual inventory (revenue + COGS pair).

    Oracle: AR/Sales at qty x price; COGS/Inventory at qty x unit cost.
    Trap: recording revenue only and leaving inventory/cost untouched.
    Equivalent: one combined transaction or two transactions.
    Level scores R/S/I/E/J/C/D = V/U/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    item = rng.choice(["trail backpacks", "ceramic planters", "LED desk lamps"])
    customer = rng.choice(["Cobalt Retail", "Harbor Clinics", "Juniper Hotels"])
    on_hand = rng.randint(80, 160)
    qty = rng.randint(15, 60)
    unit_cost = Decimal(rng.randrange(1200, 4001, 25)) / 100
    price = (unit_cost * Decimal("1.7")).quantize(CENT)
    day = rng.randint(4, 26)
    date = f"2026-01-{day:02d}"
    opening = Decimal("10000.00")
    revenue, cost = qty * price, qty * unit_cost
    initial = _ledger_header(opening, MERCH_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        f"Opening inventory: {on_hand} {item}",
        [(INVENTORY, on_hand * unit_cost), ("Equity:Opening-Balances", -on_hand * unit_cost)],
    )
    invoice = (
        f"# Sales invoice — {customer}\n\nDate: {date}\n"
        f"Item: {item}\nQuantity: {qty} units\n"
        f"Selling price: USD {money(price)} per unit\n"
        f"Unit cost (perpetual records): USD {money(unit_cost)}\n"
        "Terms: on account, due in 30 days. Goods shipped same day.\n"
    )
    solution = (
        initial
        + _txn(
            date,
            customer,
            f"Credit sale of {qty} {item}",
            [(AR, revenue), ("Income:Sales", -revenue)],
        )
        + _txn(date, customer, "Cost of goods sold", [(COST_OF_SALES, cost), (INVENTORY, -cost)])
    )
    return TaskInstance(
        task_id="perpetual-sale-with-cost",
        family="inventory",
        title="Record a credit sale under perpetual inventory",
        instruction=(
            "Record the sale evidenced by `/app/documents/sales_invoice.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md` and "
            "`/app/chart_of_accounts.md`. Append new balanced transactions dated "
            f"{date}; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": MERCH_POLICY,
            "chart_of_accounts.md": _chart_md(MERCH_ACCOUNTS),
            "documents/sales_invoice.md": invoice,
        },
        expected=_expected(
            "perpetual-sale-with-cost",
            "inventory",
            seed,
            expected_deltas={
                AR: money(revenue),
                "Income:Sales": money(-revenue),
                COST_OF_SALES: money(cost),
                INVENTORY: money(-cost),
            },
            expected_new_transactions=[1, 2],
            expected_period=[date, date],
            required_final_balances={INVENTORY: money((on_hand - qty) * unit_cost)},
        ),
        solution_ledger=solution,
        keywords=["perpetual-inventory", "credit-sale", "cost-of-goods-sold"],
        level="vocational",
    )


RETURN_ACCOUNTS = MERCH_ACCOUNTS + [(SALES_RETURNS, "Contra-revenue: sales returns and allowances")]


def sales_return_restock(seed: int) -> TaskInstance:
    """Scenario: customer returns part of a recorded credit sale; goods restock.

    Oracle: SalesReturns/AR at selling price; Inventory/COGS at unit cost.
    Trap: restocking inventory at selling price (inflates inventory, hides
    the margin reversal). Equivalent: combined or split entries.
    Level scores R/S/I/E/J/C/D = V/U/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    item = rng.choice(["steel water bottles", "trail backpacks", "LED desk lamps"])
    customer = rng.choice(["Delta Foods", "Evergreen Labs", "Kestrel Media"])
    sold = rng.randint(30, 80)
    returned = rng.randint(3, 12)
    on_hand = sold + rng.randint(20, 60)
    unit_cost = Decimal(rng.randrange(1000, 3001, 25)) / 100
    price = (unit_cost * Decimal("1.8")).quantize(CENT)
    opening = Decimal("10000.00")
    initial = (
        _ledger_header(opening, RETURN_ACCOUNTS)
        + _txn(
            "2026-01-01",
            "Opening",
            f"Opening inventory: {on_hand} {item}",
            [(INVENTORY, on_hand * unit_cost), ("Equity:Opening-Balances", -on_hand * unit_cost)],
        )
        + _txn(
            "2026-01-10",
            customer,
            f"Credit sale of {sold} {item}",
            [(AR, sold * price), ("Income:Sales", -sold * price)],
        )
        + _txn(
            "2026-01-10",
            customer,
            "Cost of goods sold",
            [(COST_OF_SALES, sold * unit_cost), (INVENTORY, -sold * unit_cost)],
        )
    )
    memo = (
        f"# Return authorization — {customer}\n\n"
        f"On 2026-01-20 the customer returned {returned} {item} from the "
        "2026-01-10 sale (wrong size). The goods are undamaged and restocked. "
        "A credit is issued against the customer's account balance; no cash refund.\n"
        f"Selling price was USD {money(price)} per unit; unit cost USD {money(unit_cost)}.\n"
    )
    refund, restock = returned * price, returned * unit_cost
    solution = (
        initial
        + _txn(
            "2026-01-20",
            customer,
            "Sales return credited to account",
            [(SALES_RETURNS, refund), (AR, -refund)],
        )
        + _txn(
            "2026-01-20",
            customer,
            "Restock returned goods at cost",
            [(INVENTORY, restock), (COST_OF_SALES, -restock)],
        )
    )
    return TaskInstance(
        task_id="sales-return-restock",
        family="inventory",
        title="Record a sales return and restock the goods",
        instruction=(
            "Record the return described in `/app/documents/return_memo.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md` and "
            "`/app/chart_of_accounts.md`. Append new balanced transactions dated "
            "2026-01-20; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": MERCH_POLICY,
            "chart_of_accounts.md": _chart_md(RETURN_ACCOUNTS),
            "documents/return_memo.md": memo,
        },
        expected=_expected(
            "sales-return-restock",
            "inventory",
            seed,
            expected_deltas={
                SALES_RETURNS: money(refund),
                AR: money(-refund),
                INVENTORY: money(restock),
                COST_OF_SALES: money(-restock),
            },
            expected_new_transactions=[1, 2],
            expected_period=["2026-01-20", "2026-01-20"],
            required_final_balances={AR: money((sold - returned) * price)},
        ),
        solution_ledger=solution,
        keywords=["sales-return", "perpetual-inventory", "contra-revenue"],
        level="vocational",
    )


SUPPLIES_ACCOUNTS = [(SUPPLIES_ASSET, "Office supplies on hand (asset until used)")]


def supplies_adjustment(seed: int) -> TaskInstance:
    """Scenario: supplies bought as an asset; month-end count.

    Oracle: expense = purchases - counted on hand.
    Trap: expensing the counted amount (the remainder) instead of the usage.
    Level scores V/V/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    bought = Decimal(rng.randrange(40, 161)) * 25
    on_hand = Decimal(rng.randrange(4, int(bought) // 50)) * 25
    used = bought - on_hand
    opening = Decimal("10000.00")
    initial = _ledger_header(opening, SUPPLIES_ACCOUNTS) + _txn(
        "2026-01-03",
        "Staples",
        "Office supplies purchased",
        [(SUPPLIES_ASSET, bought), (BANK, -bought)],
    )
    count = (
        "# Supplies count — 2026-01-31\n\n"
        f"Supplies purchased 2026-01-03: USD {money(bought)} (none on hand before).\n"
        f"Physical count at 2026-01-31: USD {money(on_hand)} still on hand.\n"
    )
    policy = POLICY + (
        "- Supplies are recorded as an asset when purchased and expensed as\n"
        "  used; the month-end adjustment expenses the amount used (purchases\n"
        "  less the counted balance on hand) to `Expenses:OfficeSupplies`.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Adjustment",
        "Supplies used in January",
        [("Expenses:OfficeSupplies", used), (SUPPLIES_ASSET, -used)],
    )
    return TaskInstance(
        task_id="supplies-adjustment",
        family="adjustments-corrections",
        title="Adjust supplies to the month-end count",
        instruction=(
            "Record the month-end supplies adjustment in `/app/ledger.beancount` "
            "using `/app/documents/supplies_count.md` and `/app/policy.md`. Append "
            "exactly one balanced transaction dated 2026-01-31; do not edit "
            "existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(SUPPLIES_ACCOUNTS),
            "documents/supplies_count.md": count,
        },
        expected=_expected(
            "supplies-adjustment",
            "adjustments-corrections",
            seed,
            expected_deltas={
                "Expenses:OfficeSupplies": money(used),
                SUPPLIES_ASSET: money(-used),
            },
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={SUPPLIES_ASSET: money(on_hand)},
        ),
        solution_ledger=solution,
        keywords=["adjusting-entry", "supplies", "deferral"],
        level="vocational",
    )


WAGE_ACCOUNTS = [
    (WAGES, "Wages expense"),
    (WAGES_PAYABLE, "Wages earned by staff but not yet paid (accrual)"),
]


def accrued_wages_adjustment(seed: int) -> TaskInstance:
    """Scenario: staff worked unpaid days after the last payday at month-end.

    Oracle: daily payroll x unpaid days accrued to wages payable.
    Trap: accruing the full 5-day week instead of the unpaid days only.
    Level scores V/V/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    daily = Decimal(rng.randrange(40, 161)) * 10
    days = rng.randint(2, 4)
    amount = daily * days
    opening = Decimal("10000.00")
    initial = _ledger_header(opening, WAGE_ACCOUNTS)
    note = (
        "# Payroll note — January 2026\n\n"
        f"Total daily payroll: USD {money(daily)} for a 5-day work week.\n"
        f"At 2026-01-31 staff had worked {days} day(s) since the last payday\n"
        "and had not been paid for them. No wages entry has been made for "
        "those days.\n"
    )
    policy = POLICY + (
        "- Wages are expensed as staff work; at month-end accrue pay earned\n"
        "  but unpaid (daily payroll x unpaid working days) to wages payable.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Payroll",
        f"Accrue {days} unpaid working day(s)",
        [(WAGES, amount), (WAGES_PAYABLE, -amount)],
    )
    return TaskInstance(
        task_id="accrued-wages-adjustment",
        family="accruals-deferrals",
        title="Accrue wages earned but unpaid at month-end",
        instruction=(
            "Record the wages accrual in `/app/ledger.beancount` using "
            "`/app/documents/payroll_note.md` and `/app/policy.md`. Append "
            "exactly one balanced transaction dated 2026-01-31; do not edit "
            "existing entries (no cash is paid in this entry)."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(WAGE_ACCOUNTS),
            "documents/payroll_note.md": note,
        },
        expected=_expected(
            "accrued-wages-adjustment",
            "accruals-deferrals",
            seed,
            expected_deltas={WAGES: money(amount), WAGES_PAYABLE: money(-amount)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={WAGES_PAYABLE: money(-amount)},
        ),
        solution_ledger=solution,
        keywords=["accrual", "wages-payable", "adjusting-entry"],
        level="vocational",
    )


DEPR_ACCOUNTS = [
    (ACC_DEP, "Accumulated depreciation on equipment (contra-asset; credit balance)"),
    (DEPRECIATION, "Depreciation expense"),
]


def straight_line_depreciation(seed: int) -> TaskInstance:
    """Scenario: first month straight-line depreciation on a new asset.

    Oracle: (cost - residual) / (life years x 12) for January.
    Trap: depreciating full cost (ignoring residual value).
    Level scores V/U/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    asset = rng.choice(["packaging machine", "delivery van", "server rack"])
    life = rng.choice([4, 5, 6])
    monthly = Decimal(rng.randrange(100, 501))
    residual = Decimal(rng.randrange(5, 41)) * 100
    cost = monthly * 12 * life + residual
    opening = Decimal("50000.00")
    initial = _ledger_header(opening, DEPR_ACCOUNTS) + _txn(
        "2026-01-02",
        "Vendor",
        f"Purchase of {asset}",
        [("Assets:Equipment", cost), (BANK, -cost)],
    )
    register = (
        f"# Asset register — {asset}\n\n"
        f"Placed in service 2026-01-02. Cost USD {money(cost)}.\n"
        f"Estimated useful life {life} years; residual value USD {money(residual)}.\n"
        "Method: straight-line.\n"
    )
    policy = POLICY + (
        "- Depreciation is straight-line monthly: (cost - residual value) /\n"
        "  useful life in months. A full month is charged in the month the\n"
        "  asset is placed in service.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Depreciation",
        f"January depreciation, {asset}",
        [(DEPRECIATION, monthly), (ACC_DEP, -monthly)],
    )
    return TaskInstance(
        task_id="straight-line-depreciation",
        family="fixed-assets",
        title="Record the first month of straight-line depreciation",
        instruction=(
            f"Record January 2026 depreciation for the {asset} in "
            "`/app/ledger.beancount`, using `/app/documents/asset_register.md` "
            "and `/app/policy.md`. Append exactly one balanced transaction "
            "dated 2026-01-31; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(DEPR_ACCOUNTS),
            "documents/asset_register.md": register,
        },
        expected=_expected(
            "straight-line-depreciation",
            "fixed-assets",
            seed,
            expected_deltas={DEPRECIATION: money(monthly), ACC_DEP: money(-monthly)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={ACC_DEP: money(-monthly)},
        ),
        solution_ledger=solution,
        keywords=["depreciation", "straight-line", "fixed-assets"],
        level="vocational",
    )


NOTE = "Assets:NotesReceivable"
INTEREST_REC = "Assets:InterestReceivable"
INTEREST_INCOME = "Income:Interest"
NOTE_ACCOUNTS = [
    (AR, "Trade receivables (customer invoices on credit)"),
    (NOTE, "Notes receivable (formal promissory notes)"),
    (INTEREST_REC, "Interest earned but not yet received"),
    (INTEREST_INCOME, "Interest income earned"),
]


def note_interest_accrual(seed: int) -> TaskInstance:
    """Scenario: note accepted Jan 1; accrue January interest (30/360).

    Oracle: principal x annual rate x 30/360 for January only.
    Trap: accruing the note's full 90-day interest at acceptance/month-end.
    Level scores V/U/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    customer = rng.choice(["Birch & Co", "Granite Supply", "Ivory Studio"])
    principal = Decimal(rng.randrange(2, 11)) * 12000
    annual = rng.choice([Decimal("0.06"), Decimal("0.09"), Decimal("0.12")])
    interest = principal * annual * Decimal(30) / Decimal(360)
    opening = Decimal("10000.00")
    initial = (
        _ledger_header(opening, NOTE_ACCOUNTS)
        + _txn(
            "2026-01-01",
            "Opening",
            "Opening receivable from customer",
            [(AR, principal), ("Equity:Opening-Balances", -principal)],
        )
        + _txn(
            "2026-01-01",
            customer,
            "90-day note accepted in settlement of receivable",
            [(NOTE, principal), (AR, -principal)],
        )
    )
    note = (
        f"# Promissory note — {customer}\n\n"
        f"Principal: USD {money(principal)}. Dated 2026-01-01, due in 90 days.\n"
        f"Interest: {annual * 100:.0f}% per year, payable at maturity.\n"
    )
    policy = POLICY + (
        "- Interest is accrued monthly using a 360-day year and 30-day months\n"
        "  (30/360): monthly interest = principal x annual rate x 30/360.\n"
        "  Interest not yet received is an interest receivable.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        customer,
        "January interest on note",
        [(INTEREST_REC, interest), (INTEREST_INCOME, -interest)],
    )
    return TaskInstance(
        task_id="note-interest-accrual",
        family="receivables",
        title="Accrue one month of interest on a note receivable",
        instruction=(
            "Record the January 2026 interest on the note in "
            "`/app/documents/promissory_note.md` in `/app/ledger.beancount`, "
            "following `/app/policy.md`. Append exactly one balanced "
            "transaction dated 2026-01-31; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(NOTE_ACCOUNTS),
            "documents/promissory_note.md": note,
        },
        expected=_expected(
            "note-interest-accrual",
            "receivables",
            seed,
            expected_deltas={INTEREST_REC: money(interest), INTEREST_INCOME: money(-interest)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={NOTE: money(principal)},
        ),
        solution_ledger=solution,
        keywords=["notes-receivable", "interest-accrual", "30-360"],
        level="vocational",
    )


FIT_PAYABLE = "Liabilities:IncomeTaxWithholdingPayable"
FICA_PAYABLE = "Liabilities:FICAPayable"
DUES_PAYABLE = "Liabilities:UnionDuesPayable"
PAYROLL_ACCOUNTS = [
    (WAGES, "Gross wages expense"),
    (WAGES_PAYABLE, "Net wages payable to staff"),
    (FIT_PAYABLE, "Employee income tax withheld, due to tax authority"),
    (FICA_PAYABLE, "Employee social contributions withheld, due to authority"),
    (DUES_PAYABLE, "Union dues withheld from staff, due to the union"),
]


def payroll_withholdings(seed: int) -> TaskInstance:
    """Scenario: January payroll register, gross pay not yet recorded or paid.

    Oracle: wage expense at gross; credits split between the three
    withholdings and net wages payable. Trap: expensing net pay, which
    understates both expense and liabilities. Level V/U/V/V/V/V/V.
    """
    rng = random.Random(seed)
    gross = Decimal(rng.randrange(6, 21)) * 2000
    fit_rate = rng.choice([Decimal("0.10"), Decimal("0.12"), Decimal("0.15")])
    fica_rate = Decimal("0.0765")
    fit = gross * fit_rate
    fica = gross * fica_rate
    dues = Decimal(rng.randrange(2, 9)) * 25
    net = gross - fit - fica - dues
    opening = Decimal("10000.00")
    initial = _ledger_header(opening, PAYROLL_ACCOUNTS)
    register = (
        "# Payroll register — January 2026\n\n"
        f"- Gross wages earned in January: USD {money(gross)}\n"
        f"- Employee income tax withheld: {fit_rate * 100:.0f}% of gross\n"
        "- Employee social contributions withheld: 7.65% of gross\n"
        f"- Union dues withheld: USD {money(dues)} (flat total)\n"
        "- Net pay is owed to staff at 2026-01-31 (paid in February).\n"
    )
    policy = POLICY + (
        "- Payroll expense is the gross amount earned. Amounts withheld from\n"
        "  staff are liabilities to the authorities/union until remitted; the\n"
        "  remainder is net wages payable. Nothing is paid in this entry.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Payroll",
        "January gross payroll and withholdings",
        [
            (WAGES, gross),
            (FIT_PAYABLE, -fit),
            (FICA_PAYABLE, -fica),
            (DUES_PAYABLE, -dues),
            (WAGES_PAYABLE, -net),
        ],
    )
    return TaskInstance(
        task_id="payroll-withholdings",
        family="payroll",
        title="Record gross payroll and employee withholdings",
        instruction=(
            "Record the January payroll from `/app/documents/payroll_register.md` "
            "in `/app/ledger.beancount`, following `/app/policy.md`. Append one "
            "or more balanced transactions dated 2026-01-31; do not edit "
            "existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(PAYROLL_ACCOUNTS),
            "documents/payroll_register.md": register,
        },
        expected=_expected(
            "payroll-withholdings",
            "payroll",
            seed,
            expected_deltas={
                WAGES: money(gross),
                FIT_PAYABLE: money(-fit),
                FICA_PAYABLE: money(-fica),
                DUES_PAYABLE: money(-dues),
                WAGES_PAYABLE: money(-net),
            },
            expected_new_transactions=[1, 2],
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={WAGES_PAYABLE: money(-net)},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["payroll", "withholdings", "gross-pay"],
        level="vocational",
    )


BONDS = "Liabilities:BondsPayable"
BOND_DISCOUNT = "Liabilities:DiscountOnBondsPayable"
BOND_ACCOUNTS = [
    (BONDS, "Bonds payable at face value"),
    (BOND_DISCOUNT, "Unamortized discount on bonds (contra-liability; debit balance)"),
    (INTEREST_PAYABLE, "Coupon interest accrued, not yet paid"),
]


def bond_discount_amortization(seed: int) -> TaskInstance:
    """Scenario: bonds issued at a discount Jan 1 (recorded); accrue January.

    Oracle: interest expense = issue price x stated effective monthly rate
    (rounded to cents); coupon payable = face x coupon rate / 12; the
    difference amortizes the discount. Trap: expensing the coupon only,
    leaving the discount untouched. Level V/U/V/V/V/V/U -> vocational.
    """
    rng = random.Random(seed)
    face = Decimal(rng.randrange(5, 21)) * 12000
    discount = (face * Decimal(rng.randrange(15, 41)) / 1000).quantize(Decimal("1"))
    price = face - discount
    coupon_annual = Decimal("0.06")
    coupon = face * coupon_annual / 12
    eff_monthly = Decimal("0.006")
    expense = (price * eff_monthly).quantize(CENT)
    amortization = expense - coupon
    opening = Decimal("5000.00")
    initial = _ledger_header(opening, BOND_ACCOUNTS) + _txn(
        "2026-01-01",
        "Underwriter",
        "Bonds issued at a discount",
        [(BANK, price), (BOND_DISCOUNT, discount), (BONDS, -face)],
    )
    terms = (
        "# Bond terms\n\n"
        f"- Issued 2026-01-01; face value USD {money(face)}; 5-year term\n"
        f"- Issue price USD {money(price)} (discount USD {money(discount)})\n"
        "- Coupon 6.0% a year on face value, paid each 30 June and 31 December\n"
        "- Effective interest rate: 0.60% per month on the carrying amount\n"
    )
    policy = POLICY + (
        "- Bonds are measured at amortized cost (effective interest method):\n"
        "  monthly interest expense = carrying amount at the start of the\n"
        "  month x the effective monthly rate stated in the bond terms,\n"
        "  rounded to the cent. Coupon accrued for the month (face x coupon\n"
        "  rate / 12) is credited to interest payable; the difference\n"
        "  amortizes the discount. Do not recompute the effective rate.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Bondholders",
        "January interest and discount amortization",
        [
            ("Expenses:Interest", expense),
            (BOND_DISCOUNT, -amortization),
            (INTEREST_PAYABLE, -coupon),
        ],
    )
    return TaskInstance(
        task_id="bond-discount-amortization",
        family="borrowings",
        title="Accrue January interest on bonds issued at a discount",
        instruction=(
            "Record January 2026 interest on the bonds in `/app/ledger.beancount`, "
            "using `/app/documents/bond_terms.md` and `/app/policy.md`. Append "
            "new transactions dated 2026-01-31; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(BOND_ACCOUNTS),
            "documents/bond_terms.md": terms,
        },
        expected=_expected(
            "bond-discount-amortization",
            "borrowings",
            seed,
            expected_deltas={
                "Expenses:Interest": money(expense),
                BOND_DISCOUNT: money(-amortization),
                INTEREST_PAYABLE: money(-coupon),
            },
            expected_new_transactions=[1, 2],
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={BOND_DISCOUNT: money(discount - amortization)},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["bonds-payable", "discount-amortization", "effective-interest"],
        level="vocational",
        standards=["asc:835-30", "ifrs:9"],
    )


def _numeric_instance(
    *,
    task_id: str,
    family: str,
    title: str,
    question: str,
    policy: str,
    data_name: str,
    data: str,
    gold: Decimal,
    seed: int,
    category: str,
    keywords: list[str],
    abs_tolerance: str = "1",
    standards: list[str] | None = None,
    **extra_expected,
) -> TaskInstance:
    return TaskInstance(
        task_id=task_id,
        family=family,
        title=title,
        instruction=(
            f"Compute the value asked in `/app/question.md` using "
            f"`/app/documents/{data_name}` and `/app/policy.md`. Write the "
            "result to `/app/answer.json` in the exact format shown in the question."
        ),
        app_files={
            "question.md": question,
            "policy.md": policy,
            f"documents/{data_name}": data,
            "answer.example.json": '{\n  "final_answer": 1000,\n  "confidence": 50\n}\n',
        },
        expected=_expected(
            task_id,
            family,
            seed,
            format="numeric",
            gold=format(gold, "f"),
            abs_tolerance=abs_tolerance,
            rel_tolerance="0",
            expected_deltas={},
            expected_new_transactions=0,
            expected_period=None,
            **extra_expected,
        ),
        solution_ledger="",
        solution_answer={"final_answer": float(gold), "confidence": 100},
        keywords=keywords,
        level="vocational",
        category=category,
        format="numeric",
        standards=standards or [],
    )


def _numeric_question(heading: str, body: str, answer_label: str) -> str:
    return f"""# Question — {heading}

{body}

## Answer format

Write `/app/answer.json` as a JSON object, for example:

```json
{{"final_answer": 1200, "confidence": 80}}
```

`final_answer` is {answer_label} (a number); `confidence` is your
self-assessed probability (0-100) that the value is correct.
"""


def cvp_target_profit_units(seed: int) -> TaskInstance:
    """Numeric: units needed for a target profit. Trap: break-even units."""
    rng = random.Random(seed)
    breakeven = rng.randrange(400, 2001, 25)
    extra = rng.randrange(100, 901, 25)
    units = breakeven + extra
    margin = Decimal(rng.randrange(500, 4001, 50)) / 100
    variable = Decimal(rng.randrange(1000, 7001, 50)) / 100
    price = variable + margin
    fixed = margin * breakeven
    target = margin * extra
    data = (
        "# Cost data (monthly)\n\n| Item | Value |\n|---|---:|\n"
        f"| Selling price / unit | USD {money(price)} |\n"
        f"| Variable cost / unit | USD {money(variable)} |\n"
        f"| Total fixed costs | USD {money(fixed)} |\n"
        f"| Target monthly profit | USD {money(target)} |\n"
    )
    policy = MGMT_POLICY + (
        "- Units for a target profit = (fixed costs + target profit) /\n"
        "  contribution margin per unit.\n"
    )
    question = _numeric_question(
        "units for a target profit",
        "Using `/app/documents/cost_data.md` and `/app/policy.md`, compute the "
        "monthly **sales volume in units** needed to earn the target profit.",
        "the unit count",
    )
    return _numeric_instance(
        task_id="cvp-target-profit-units",
        family="cost-volume-profit",
        title="Compute units needed for a target profit",
        question=question,
        policy=policy,
        data_name="cost_data.md",
        data=data,
        gold=Decimal(units),
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "cvp", "target-profit"],
        trap_value=str(breakeven),
    )


def process_costing_equivalent_units(seed: int) -> TaskInstance:
    """Numeric: weighted-average EU for conversion. Trap: FIFO EU."""
    rng = random.Random(seed)
    bwip = rng.randrange(200, 1201, 100)
    bwip_pct = rng.choice([20, 30, 40, 60])
    completed = bwip + rng.randrange(2000, 8001, 100)
    ewip = rng.randrange(200, 1501, 100)
    ewip_pct = rng.choice([20, 40, 50, 60, 80])
    gold = Decimal(completed) + Decimal(ewip * ewip_pct) / 100
    fifo = gold - Decimal(bwip * bwip_pct) / 100
    data = (
        "# Production data — January (single process)\n\n| Item | Units |\n|---|---:|\n"
        f"| Beginning work in process | {bwip} |\n"
        f"| Completed and transferred out | {completed} |\n"
        f"| Ending work in process | {ewip} |\n\n"
        f"Beginning WIP is {bwip_pct}% complete for conversion costs; ending "
        f"WIP is {ewip_pct}% complete for conversion costs. Materials are "
        "added at the start of the process.\n"
    )
    policy = """# Process costing conventions (applies to this task)

- Use the weighted-average method.
- Equivalent units (conversion) = units completed and transferred out
  + ending WIP units x their conversion completion percentage.
  Beginning WIP completion is irrelevant under weighted-average.
- Answer with the equivalent-unit count in `/app/answer.json`.
"""
    question = _numeric_question(
        "equivalent units (weighted-average)",
        "Using `/app/documents/production_data.md` and `/app/policy.md`, compute "
        "January **equivalent units for conversion costs**.",
        "the equivalent-unit count",
    )
    return _numeric_instance(
        task_id="process-costing-equivalent-units",
        family="process-costing",
        title="Compute weighted-average equivalent units for conversion",
        question=question,
        policy=policy,
        data_name="production_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "process-costing", "equivalent-units"],
        trap_value=format(fifo, "f"),
    )


def operating_cash_flow_indirect(seed: int) -> TaskInstance:
    """Numeric: CFO indirect. Trap: adding back the gain on disposal."""
    rng = random.Random(seed)

    def amt(lo: int, hi: int) -> Decimal:
        return Decimal(rng.randrange(lo, hi)) * 100

    net_income = amt(200, 801)
    depreciation = amt(40, 161)
    gain = amt(10, 61)
    ar_increase = amt(20, 121)
    inv_increase = amt(15, 101)
    ap_increase = amt(10, 91)
    gold = net_income + depreciation - gain - ar_increase - inv_increase + ap_increase
    data = (
        "# Extracts for the year ended 2025-12-31\n\n| Item | USD |\n|---|---:|\n"
        f"| Net income | {money(net_income)} |\n"
        f"| Depreciation expense | {money(depreciation)} |\n"
        f"| Gain on sale of equipment (in net income) | {money(gain)} |\n"
        f"| Increase in accounts receivable | {money(ar_increase)} |\n"
        f"| Increase in inventory | {money(inv_increase)} |\n"
        f"| Increase in accounts payable | {money(ap_increase)} |\n"
    )
    policy = """# Indirect method conventions (applies to this task)

- Start from net income. Add back non-cash depreciation.
- Deduct gains on disposal (the proceeds are investing cash flow).
- Increases in operating assets (receivables, inventory) use cash:
  deduct. Increases in operating liabilities (payables) provide cash: add.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "operating cash flow (indirect method)",
        "Using `/app/documents/extracts.md` and `/app/policy.md`, compute "
        "**net cash provided by operating activities** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="operating-cash-flow-indirect",
        family="cash-flow-statement",
        title="Compute operating cash flow by the indirect method",
        question=question,
        policy=policy,
        data_name="extracts.md",
        data=data,
        gold=gold,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "cash-flow", "indirect-method"],
        abs_tolerance="0.01",
        trap_value=money(gold + 2 * gain),
        standards=["asc:230", "ias:7"],
    )


def inventory_days_on_hand(seed: int) -> TaskInstance:
    """Numeric: days' inventory on hand using average. Trap: ending-based."""
    rng = random.Random(seed)
    days = rng.randrange(20, 91, 5)
    step = rng.randint(1, 4)
    daily = Decimal(rng.randrange(20, 101)) * 10
    average = daily * days
    cogs = daily * 365
    delta = daily * step
    beginning, ending = average - delta, average + delta
    data = (
        "# Inventory data — year ended 2025-12-31\n\n| Item | USD |\n|---|---:|\n"
        f"| Inventory, 2025-01-01 | {money(beginning)} |\n"
        f"| Inventory, 2025-12-31 | {money(ending)} |\n"
        f"| Cost of goods sold | {money(cogs)} |\n"
    )
    policy = """# Ratio conventions (applies to this task)

- Days' inventory on hand = average inventory / cost of goods sold x 365.
- Average inventory = (opening + closing inventory) / 2.
- Answer with the number of days in `/app/answer.json`.
"""
    question = _numeric_question(
        "days' inventory on hand",
        "Using `/app/documents/inventory_data.md` and `/app/policy.md`, compute "
        "**days' inventory on hand**.",
        "the number of days",
    )
    return _numeric_instance(
        task_id="inventory-days-on-hand",
        family="financial-analysis",
        title="Compute days' inventory on hand",
        question=question,
        policy=policy,
        data_name="inventory_data.md",
        data=data,
        gold=Decimal(days),
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "inventory-ratio", "days-on-hand"],
        abs_tolerance="0",
        trap_value=str(days + step),
    )


COMMON_STOCK = "Equity:CommonStock"
APIC = "Equity:AdditionalPaidInCapital"
RETAINED = "Equity:RetainedEarnings"
TREASURY = "Equity:TreasuryStock"
DIVIDENDS_PAYABLE = "Liabilities:DividendsPayable"
INCOME_SUMMARY = "Equity:IncomeSummary"
EQUITY_ACCOUNTS = [
    (COMMON_STOCK, "Common stock at par value"),
    (APIC, "Additional paid-in capital (amounts above par)"),
    (RETAINED, "Retained earnings"),
]
EQUITY_POLICY = POLICY + (
    "- Share capital is credited at par value; amounts received above par\n"
    "  are additional paid-in capital.\n"
)


def equity_issue_above_par(seed: int) -> TaskInstance:
    """Scenario: new shares issued for cash above par.

    Oracle: Bank at proceeds; CommonStock at par x shares; APIC for rest.
    Trap: crediting common stock with the full proceeds.
    Level V/U/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    shares = rng.randrange(1000, 9001, 250)
    par = Decimal(rng.choice([1, 2, 5]))
    price = par + Decimal(rng.randrange(2, 21))
    proceeds = shares * price
    par_total = shares * par
    day = rng.randint(3, 25)
    date = f"2026-01-{day:02d}"
    opening = Decimal("10000.00")
    initial = _ledger_header(opening, EQUITY_ACCOUNTS)
    doc = (
        "# Share subscription — January 2026\n\n"
        f"Investors subscribed for {shares} new common shares on {date}.\n"
        f"Par value: USD {money(par)} per share. Issue price: USD {money(price)} "
        "per share, received in full into checking the same day.\n"
    )
    solution = initial + _txn(
        date,
        "Investors",
        f"Issued {shares} common shares above par",
        [(BANK, proceeds), (COMMON_STOCK, -par_total), (APIC, -(proceeds - par_total))],
    )
    return TaskInstance(
        task_id="equity-issue-above-par",
        family="equity",
        title="Record a share issue above par value",
        instruction=(
            "Record the share issue in `/app/documents/subscription.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md`. Append new "
            f"balanced transactions dated {date}; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": EQUITY_POLICY,
            "chart_of_accounts.md": _chart_md(EQUITY_ACCOUNTS),
            "documents/subscription.md": doc,
        },
        expected=_expected(
            "equity-issue-above-par",
            "equity",
            seed,
            expected_deltas={
                BANK: money(proceeds),
                COMMON_STOCK: money(-par_total),
                APIC: money(-(proceeds - par_total)),
            },
            expected_new_transactions=[1, 2],
            expected_period=[date, date],
            required_final_balances={BANK: money(opening + proceeds)},
        ),
        solution_ledger=solution,
        keywords=["equity", "share-issue", "par-value", "paid-in-capital"],
        level="vocational",
    )


DIVIDEND_ACCOUNTS = EQUITY_ACCOUNTS + [(DIVIDENDS_PAYABLE, "Dividends declared but not yet paid")]


def cash_dividend_declaration(seed: int) -> TaskInstance:
    """Scenario: board declares a cash dividend in January, payable February.

    Oracle: RetainedEarnings / DividendsPayable at shares x per-share amount.
    Trap: recording the February payment (or an expense) in January.
    Level V/V/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    shares = rng.randrange(2000, 12001, 250)
    per_share = (Decimal(rng.randrange(25, 201, 25)) / 100).quantize(CENT)
    total = shares * per_share
    retained_open = total * rng.randint(3, 6)
    opening = Decimal("50000.00")
    initial = _ledger_header(opening, DIVIDEND_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        "Opening retained earnings",
        [("Equity:Opening-Balances", retained_open), (RETAINED, -retained_open)],
    )
    doc = (
        "# Board resolution — 2026-01-15\n\n"
        f"The board declared a cash dividend of USD {money(per_share)} per share "
        f"on the {shares} common shares outstanding, payable 2026-02-12 to "
        "shareholders of record on 2026-01-30.\n"
    )
    policy = POLICY + (
        "- A declared cash dividend is a liability on the declaration date:\n"
        "  debit retained earnings, credit dividends payable. Dividends are\n"
        "  never an expense. Payment is recorded when paid (here, February).\n"
    )
    solution = initial + _txn(
        "2026-01-15",
        "Board",
        "Cash dividend declared",
        [(RETAINED, total), (DIVIDENDS_PAYABLE, -total)],
    )
    return TaskInstance(
        task_id="cash-dividend-declaration",
        family="equity",
        title="Record the declaration of a cash dividend",
        instruction=(
            "Record the January accounting for the dividend in "
            "`/app/documents/board_resolution.md` in `/app/ledger.beancount`, "
            "following `/app/policy.md`. Append new balanced transactions dated "
            "2026-01-15; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(DIVIDEND_ACCOUNTS),
            "documents/board_resolution.md": doc,
        },
        expected=_expected(
            "cash-dividend-declaration",
            "equity",
            seed,
            expected_deltas={RETAINED: money(total), DIVIDENDS_PAYABLE: money(-total)},
            expected_period=["2026-01-15", "2026-01-15"],
            required_final_balances={
                RETAINED: money(-(retained_open - total)),
                BANK: money(opening),
            },
        ),
        solution_ledger=solution,
        keywords=["dividends", "declaration-date", "retained-earnings"],
        level="vocational",
    )


TREASURY_ACCOUNTS = EQUITY_ACCOUNTS + [
    (TREASURY, "Treasury stock at cost (contra-equity; debit balance)")
]


def treasury_stock_repurchase(seed: int) -> TaskInstance:
    """Scenario: company buys back its own shares (cost method).

    Oracle: TreasuryStock debited at repurchase cost against bank.
    Trap: debiting common stock (retirement treatment) or an asset.
    Level V/V/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    shares = rng.randrange(200, 2001, 100)
    price = Decimal(rng.randrange(8, 41))
    cost = shares * price
    stock_open = Decimal(rng.randrange(8000, 20001, 500))
    opening = Decimal("80000.00")
    initial = _ledger_header(opening, TREASURY_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        "Opening common stock (par USD 1.00)",
        [("Equity:Opening-Balances", stock_open), (COMMON_STOCK, -stock_open)],
    )
    doc = (
        "# Share repurchase — 2026-01-18\n\n"
        f"The company repurchased {shares} of its own common shares on the open "
        f"market at USD {money(price)} per share, paid from checking. The shares "
        "are held in treasury for possible reissue (not retired).\n"
    )
    policy = POLICY + (
        "- Treasury stock is accounted for by the cost method: the full\n"
        "  repurchase price is debited to `Equity:TreasuryStock` (a\n"
        "  contra-equity account, not an asset). Common stock and APIC are\n"
        "  unchanged until the shares are reissued or retired.\n"
    )
    solution = initial + _txn(
        "2026-01-18",
        "Broker",
        f"Repurchased {shares} shares into treasury",
        [(TREASURY, cost), (BANK, -cost)],
    )
    return TaskInstance(
        task_id="treasury-stock-repurchase",
        family="equity",
        title="Record a treasury stock repurchase (cost method)",
        instruction=(
            "Record the repurchase in `/app/documents/repurchase.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated 2026-01-18; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(TREASURY_ACCOUNTS),
            "documents/repurchase.md": doc,
        },
        expected=_expected(
            "treasury-stock-repurchase",
            "equity",
            seed,
            expected_deltas={TREASURY: money(cost), BANK: money(-cost)},
            expected_period=["2026-01-18", "2026-01-18"],
            required_final_balances={COMMON_STOCK: money(-stock_open)},
        ),
        solution_ledger=solution,
        keywords=["treasury-stock", "cost-method", "equity"],
        level="vocational",
    )


CLOSING_ACCOUNTS = [
    (INCOME_SUMMARY, "Income summary (temporary closing account)"),
    (RETAINED, "Retained earnings"),
]


def closing_entries_income_summary(seed: int) -> TaskInstance:
    """Scenario: close January revenue and expenses into retained earnings.

    Oracle: Sales closed to IncomeSummary, expenses closed to
    IncomeSummary, net profit closed to RetainedEarnings; all nominal
    accounts end at zero. Trap: closing revenue only (expenses left open)
    or transferring gross revenue to retained earnings.
    Level V/U/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    revenue = Decimal(rng.randrange(300, 901)) * 25
    rent = Decimal(rng.randrange(40, 121)) * 25
    utilities = Decimal(rng.randrange(20, 81)) * 25
    profit = revenue - rent - utilities
    opening = Decimal("10000.00")
    initial = (
        _ledger_header(opening, CLOSING_ACCOUNTS)
        + _txn(
            "2026-01-20",
            "Customers",
            "January cash sales",
            [(BANK, revenue), ("Income:Sales", -revenue)],
        )
        + _txn(
            "2026-01-05",
            "Landlord",
            "January rent",
            [("Expenses:Rent", rent), (BANK, -rent)],
        )
        + _txn(
            "2026-01-22",
            "City Power",
            "January utilities",
            [("Expenses:Utilities", utilities), (BANK, -utilities)],
        )
    )
    doc = (
        "# Pre-closing balances — 2026-01-31\n\n| Account | Balance (USD) |\n|---|---:|\n"
        f"| Income:Sales (credit) | {money(revenue)} |\n"
        f"| Expenses:Rent (debit) | {money(rent)} |\n"
        f"| Expenses:Utilities (debit) | {money(utilities)} |\n"
        "| Equity:RetainedEarnings | 0.00 (first month of operations) |\n"
    )
    policy = POLICY + (
        "- Month-end closing: close revenue and expense accounts into\n"
        "  `Equity:IncomeSummary`, then close the income summary balance\n"
        "  (net profit) into `Equity:RetainedEarnings`. After closing, all\n"
        "  revenue and expense accounts have zero balances.\n"
    )
    solution = (
        initial
        + _txn(
            "2026-01-31",
            "Closing",
            "Close revenue to income summary",
            [("Income:Sales", revenue), (INCOME_SUMMARY, -revenue)],
        )
        + _txn(
            "2026-01-31",
            "Closing",
            "Close expenses to income summary",
            [
                (INCOME_SUMMARY, rent + utilities),
                ("Expenses:Rent", -rent),
                ("Expenses:Utilities", -utilities),
            ],
        )
        + _txn(
            "2026-01-31",
            "Closing",
            "Close net profit to retained earnings",
            [(INCOME_SUMMARY, profit), (RETAINED, -profit)],
        )
    )
    return TaskInstance(
        task_id="closing-entries-income-summary",
        family="ledger-integrity-reporting",
        title="Close January revenue and expenses via income summary",
        instruction=(
            "Record the closing entries for January 2026 in "
            "`/app/ledger.beancount`, using `/app/documents/preclosing.md` and "
            "`/app/policy.md`. Append new balanced transactions dated "
            "2026-01-31; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(CLOSING_ACCOUNTS),
            "documents/preclosing.md": doc,
        },
        expected=_expected(
            "closing-entries-income-summary",
            "ledger-integrity-reporting",
            seed,
            expected_deltas={
                "Income:Sales": money(revenue),
                "Expenses:Rent": money(-rent),
                "Expenses:Utilities": money(-utilities),
                INCOME_SUMMARY: "0.00",
                RETAINED: money(-profit),
            },
            expected_new_transactions=[1, 4],
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={
                "Income:Sales": "0.00",
                "Expenses:Rent": "0.00",
                "Expenses:Utilities": "0.00",
                RETAINED: money(-profit),
            },
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["closing-entries", "income-summary", "retained-earnings"],
        level="vocational",
    )


WIP = "Assets:WorkInProcess"
RAW_MATERIALS = "Assets:RawMaterials"
MFG_OVERHEAD = "Expenses:ManufacturingOverhead"
JOB_ACCOUNTS = [
    (WIP, "Work in process inventory (job costs)"),
    (RAW_MATERIALS, "Raw materials inventory"),
    (WAGES, "Direct labor cost"),
    (MFG_OVERHEAD, "Manufacturing overhead control (actual debited, applied credited)"),
]


def job_overhead_applied(seed: int) -> TaskInstance:
    """Scenario: apply overhead to a job at the predetermined rate on DL cost.

    Oracle: applied = direct-labor cost x rate; debit WIP, credit MfgOH.
    Trap: applying the actual overhead incurred (given in the document).
    Level V/U/V/U/V/V/V -> vocational (borderline).
    """
    rng = random.Random(seed)
    job = f"Job {rng.randint(40, 99)}"
    materials = Decimal(rng.randrange(100, 401)) * 25
    labor = Decimal(rng.randrange(50, 201)) * 25
    rate_pct = rng.choice([80, 100, 120, 150])
    applied = (labor * rate_pct / 100).quantize(CENT)
    actual = applied + Decimal(rng.choice([-1, 1]) * rng.randrange(4, 21)) * 25
    opening = Decimal("30000.00")
    raw_opening = materials + Decimal("5000.00")
    initial = (
        _ledger_header(opening, JOB_ACCOUNTS)
        + _txn(
            "2026-01-01",
            "Opening",
            "Opening raw materials inventory",
            [(RAW_MATERIALS, raw_opening), ("Equity:Opening-Balances", -raw_opening)],
        )
        + _txn(
            "2026-01-12",
            "Stores",
            f"Direct materials issued to {job}",
            [(WIP, materials), (RAW_MATERIALS, -materials)],
        )
        + _txn(
            "2026-01-20",
            "Payroll",
            f"Direct labor charged to {job}",
            [(WIP, labor), (BANK, -labor)],
        )
        + _txn(
            "2026-01-28",
            "Suppliers",
            "Actual manufacturing overhead incurred in January",
            [(MFG_OVERHEAD, actual), (BANK, -actual)],
        )
    )
    doc = (
        f"# Job cost sheet extract — {job}\n\n"
        f"- Direct materials: USD {money(materials)}\n"
        f"- Direct labor: USD {money(labor)}\n"
        f"- Actual manufacturing overhead for January (all jobs): USD {money(actual)}\n"
        f"- Overhead is applied to jobs at {rate_pct}% of direct-labor cost.\n"
    )
    policy = POLICY + (
        "- Job-order costing: overhead is applied to each job using the\n"
        "  predetermined rate on direct-labor cost stated on the job cost\n"
        "  sheet (debit work in process, credit manufacturing overhead).\n"
        "  Actual overhead is recorded separately and is never the amount\n"
        "  applied.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        job,
        "Apply overhead at predetermined rate",
        [(WIP, applied), (MFG_OVERHEAD, -applied)],
    )
    return TaskInstance(
        task_id="job-overhead-applied",
        family="job-order-costing",
        title="Apply manufacturing overhead to a job",
        instruction=(
            f"Apply January overhead to {job} in `/app/ledger.beancount`, using "
            "`/app/documents/job_cost_sheet.md` and `/app/policy.md`. Append "
            "new balanced transactions dated 2026-01-31; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(JOB_ACCOUNTS),
            "documents/job_cost_sheet.md": doc,
        },
        expected=_expected(
            "job-overhead-applied",
            "job-order-costing",
            seed,
            expected_deltas={WIP: money(applied), MFG_OVERHEAD: money(-applied)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={WIP: money(materials + labor + applied)},
        ),
        solution_ledger=solution,
        keywords=["job-order-costing", "predetermined-overhead", "work-in-process"],
        level="vocational",
        category="management-accounting",
    )


def note_dishonored(seed: int) -> TaskInstance:
    """Scenario: note receivable dishonored at maturity in January.

    Oracle: charge the maker the maturity value: AR debited for principal
    + total interest; credits clear the note, the January-1 interest
    receivable (one month accrued), and January's interest income.
    Trap: transferring principal only and dropping the interest claim.
    Level V/U/V/V/V/U/V -> vocational.
    """
    rng = random.Random(seed)
    customer = rng.choice(["Birch & Co", "Fjord Outfitters", "Granite Supply"])
    principal = Decimal(rng.randrange(2, 11)) * 12000
    annual = rng.choice([Decimal("0.06"), Decimal("0.09"), Decimal("0.12")])
    monthly = principal * annual / 12
    accrued = monthly  # one month accrued at 2026-01-01
    maturity = principal + 2 * monthly
    opening = Decimal("10000.00")
    initial = _ledger_header(opening, NOTE_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        "Opening note and accrued interest (one month)",
        [
            (NOTE, principal),
            (INTEREST_REC, accrued),
            ("Equity:Opening-Balances", -(principal + accrued)),
        ],
    )
    doc = (
        f"# Note status — {customer}\n\n"
        f"The customer's 2-month note (principal USD {money(principal)}, "
        f"{annual * 100:.0f}% a year) was accepted on 2025-12-01 and accrued "
        "for one month at 2026-01-01. It matured on 2026-01-31 and was "
        "dishonored: the maker did not pay. Charge the maker's account the "
        "full maturity value (principal plus 2 months of interest).\n"
    )
    policy = POLICY + (
        "- A dishonored note is transferred back to accounts receivable at\n"
        "  its maturity value (principal plus all interest to maturity).\n"
        "  Interest for the current month is recognized as interest income;\n"
        "  interest accrued in earlier months clears the interest receivable.\n"
        "  Interest uses a 12-month year (monthly = principal x rate / 12).\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        customer,
        "Dishonored note charged to customer account",
        [
            (AR, maturity),
            (NOTE, -principal),
            (INTEREST_REC, -accrued),
            (INTEREST_INCOME, -monthly),
        ],
    )
    return TaskInstance(
        task_id="note-dishonored",
        family="receivables",
        title="Record a dishonored note receivable",
        instruction=(
            "Record the dishonor described in `/app/documents/note_status.md` "
            "in `/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated 2026-01-31; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(NOTE_ACCOUNTS),
            "documents/note_status.md": doc,
        },
        expected=_expected(
            "note-dishonored",
            "receivables",
            seed,
            expected_deltas={
                AR: money(maturity),
                NOTE: money(-principal),
                INTEREST_REC: money(-accrued),
                INTEREST_INCOME: money(-monthly),
            },
            expected_new_transactions=[1, 2],
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={NOTE: "0.00", INTEREST_REC: "0.00"},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["notes-receivable", "dishonored-note", "maturity-value"],
        level="vocational",
    )


def lifo_ending_inventory(seed: int) -> TaskInstance:
    """Numeric: periodic LIFO ending inventory. Trap: FIFO value."""
    rng = random.Random(seed)
    q0 = rng.randrange(100, 401, 25)
    q1 = rng.randrange(150, 501, 25)
    q2 = rng.randrange(150, 501, 25)
    c0 = Decimal(rng.randrange(800, 1801, 25)) / 100
    c1 = c0 + Decimal(rng.randrange(100, 401, 25)) / 100
    c2 = c1 + Decimal(rng.randrange(100, 401, 25)) / 100
    total = q0 + q1 + q2
    ending = rng.randrange(q0 // 2, q0 + q1, 25)
    sold = total - ending

    def value(layers, units):  # layers oldest-first; take `units` from the front
        out, left = Decimal("0"), units
        for q, c in layers:
            take = min(q, left)
            out += take * c
            left -= take
            if not left:
                break
        return out

    layers = [(q0, c0), (q1, c1), (q2, c2)]
    gold = value(layers, ending)  # LIFO ending = earliest layers
    fifo = value(list(reversed(layers)), ending)
    data = (
        "# Inventory data — January 2026 (one product)\n\n"
        "| Layer | Units | Unit cost (USD) |\n|---|---:|---:|\n"
        f"| Beginning inventory 2026-01-01 | {q0} | {money(c0)} |\n"
        f"| Purchase 2026-01-10 | {q1} | {money(c1)} |\n"
        f"| Purchase 2026-01-22 | {q2} | {money(c2)} |\n\n"
        f"Units sold in January: {sold}. Units on hand 2026-01-31 "
        f"(periodic system, count agrees): {ending}.\n"
    )
    policy = """# Inventory costing conventions (applies to this task)

- Periodic inventory system, LIFO (last-in, first-out): the most recent
  costs are charged to cost of goods sold first; ending inventory keeps
  the earliest layers.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "LIFO ending inventory",
        "Using `/app/documents/inventory_data.md` and `/app/policy.md`, compute "
        "the **ending inventory value** at 2026-01-31 in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="lifo-ending-inventory",
        family="inventory",
        title="Compute ending inventory under periodic LIFO",
        question=question,
        policy=policy,
        data_name="inventory_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "inventory", "lifo"],
        abs_tolerance="0.01",
        trap_value=money(fifo),
    )


def materials_price_variance(seed: int) -> TaskInstance:
    """Numeric: materials price variance on quantity purchased.

    Trap: using quantity used in production instead of quantity purchased.
    """
    rng = random.Random(seed)
    standard = Decimal(rng.randrange(400, 1501, 25)) / 100
    actual = standard + Decimal(rng.randrange(25, 201, 25)) / 100
    purchased = rng.randrange(2000, 12001, 250)
    used = purchased - rng.randrange(250, 1501, 250)
    gold = (actual - standard) * purchased
    trap = (actual - standard) * used
    data = (
        "# Direct materials — January 2026\n\n| Item | Value |\n|---|---:|\n"
        f"| Standard price | USD {money(standard)} per unit |\n"
        f"| Actual price paid | USD {money(actual)} per unit |\n"
        f"| Units purchased | {purchased} |\n"
        f"| Units used in production | {used} |\n"
    )
    policy = """# Standard costing conventions (applies to this task)

- Materials price variance = (actual price - standard price) x units
  purchased (isolated at purchase). A positive answer is unfavorable.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "materials price variance",
        "Using `/app/documents/materials_data.md` and `/app/policy.md`, compute "
        "the **materials price variance** in USD (positive = unfavorable).",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="materials-price-variance",
        family="standard-costing",
        title="Compute the materials price variance",
        question=question,
        policy=policy,
        data_name="materials_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "standard-costing", "price-variance"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


def npv_project_evaluation(seed: int) -> TaskInstance:
    """Numeric: NPV from a stated annuity factor. Trap: undiscounted sum."""
    rng = random.Random(seed)
    years = rng.choice([4, 5, 6])
    rate = rng.choice([Decimal("0.08"), Decimal("0.10"), Decimal("0.12")])
    factor = sum(Decimal(1) / (1 + rate) ** t for t in range(1, years + 1)).quantize(
        Decimal("0.0001")
    )
    inflow = Decimal(rng.randrange(15, 61)) * 1000
    initial = (inflow * factor * Decimal("0.8") // 1000) * 1000
    gold = (inflow * factor - initial).quantize(CENT)
    trap = inflow * years - initial
    data = (
        "# Project appraisal data\n\n| Item | Value |\n|---|---:|\n"
        f"| Initial investment (today) | USD {money(initial)} |\n"
        f"| Annual net cash inflow (end of each year) | USD {money(inflow)} |\n"
        f"| Project life | {years} years |\n"
        f"| Discount rate | {rate * 100:.0f}% |\n"
        f"| Present value annuity factor ({rate * 100:.0f}%, {years} years) | {factor} |\n"
        "\nNo salvage value. Ignore tax.\n"
    )
    policy = """# Capital budgeting conventions (applies to this task)

- NPV = annual net cash inflow x the annuity factor given in the data
  (use it as stated; do not recompute it) - initial investment.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "net present value",
        "Using `/app/documents/project_data.md` and `/app/policy.md`, compute "
        "the project's **net present value** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="npv-project-evaluation",
        family="capital-budgeting",
        title="Compute a project's net present value",
        question=question,
        policy=policy,
        data_name="project_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "npv", "capital-budgeting"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


def make_or_buy_advantage(seed: int) -> TaskInstance:
    """Numeric: total advantage of making. Trap: counting unavoidable fixed."""
    rng = random.Random(seed)
    units = rng.randrange(1000, 9001, 250)
    dm = Decimal(rng.randrange(200, 901, 25)) / 100
    dl = Decimal(rng.randrange(150, 701, 25)) / 100
    voh = Decimal(rng.randrange(100, 501, 25)) / 100
    avoidable = Decimal(rng.randrange(40, 201)) * 100
    unavoidable = Decimal(rng.randrange(60, 301)) * 100
    advantage = Decimal(rng.randrange(50, 201)) * 100
    relevant = (dm + dl + voh) * units + avoidable
    buy_price = ((relevant + advantage) / units).quantize(CENT)
    buy_total = buy_price * units
    gold = buy_total - relevant
    trap = buy_total - (relevant + unavoidable)
    data = (
        f"# Component decision — {units} units a year\n\n"
        "| Make (per unit) | USD |\n|---|---:|\n"
        f"| Direct materials | {money(dm)} |\n"
        f"| Direct labor | {money(dl)} |\n"
        f"| Variable overhead | {money(voh)} |\n\n"
        f"- Fixed overhead avoided if bought: USD {money(avoidable)} a year\n"
        f"- Fixed overhead that continues either way: USD {money(unavoidable)} a year\n"
        f"- Outside supplier's price: USD {money(buy_price)} per unit\n"
    )
    policy = """# Relevant costing conventions (applies to this task)

- Only costs that differ between the alternatives are relevant. Fixed
  overhead that continues either way is irrelevant and excluded.
- Advantage of making = total relevant buy cost - total relevant make
  cost. A positive answer means making is cheaper.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "make-or-buy advantage",
        "Using `/app/documents/component_data.md` and `/app/policy.md`, compute "
        "the **total annual advantage of making** the component in USD "
        "(positive = making is cheaper).",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="make-or-buy-advantage",
        family="relevant-costing",
        title="Compute the advantage of making a component",
        question=question,
        policy=policy,
        data_name="component_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "relevant-costing", "make-or-buy"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


def absorption_variable_income_difference(seed: int) -> TaskInstance:
    """Numeric: absorption minus variable income. Trap: rate x units sold."""
    rng = random.Random(seed)
    produced = rng.randrange(4000, 12001, 250)
    sold = produced - rng.randrange(250, 2001, 250)
    if produced == 2 * sold:  # keep the units-sold trap distinct from the gold
        sold -= 250
    rate = Decimal(rng.randrange(200, 1001, 25)) / 100
    fixed_total = rate * produced
    gold = rate * (produced - sold)
    trap = rate * sold
    data = (
        "# Production and sales — January 2026\n\n| Item | Value |\n|---|---:|\n"
        f"| Units produced | {produced} |\n"
        f"| Units sold | {sold} |\n"
        "| Beginning finished inventory | 0 units |\n"
        f"| Fixed manufacturing overhead | USD {money(fixed_total)} |\n"
        f"| Fixed overhead rate (per unit produced) | USD {money(rate)} |\n"
    )
    policy = """# Absorption vs variable costing (applies to this task)

- Difference = absorption-costing operating income - variable-costing
  operating income = fixed overhead rate x (units produced - units sold).
  Fixed overhead deferred in ending inventory under absorption costing
  is expensed at once under variable costing.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "absorption vs variable costing income difference",
        "Using `/app/documents/production_data.md` and `/app/policy.md`, compute "
        "**absorption-costing income minus variable-costing income** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="absorption-variable-income-difference",
        family="absorption-variable-costing",
        title="Compute the absorption/variable income difference",
        question=question,
        policy=policy,
        data_name="production_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "absorption-costing", "variable-costing"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


def current_ratio(seed: int) -> TaskInstance:
    """Numeric: current ratio. Trap: quick ratio (excl. inventory/prepaids)."""
    rng = random.Random(seed)
    cl = Decimal(rng.randrange(4, 16)) * 10000
    ratio = rng.choice(
        [Decimal("1.25"), Decimal("1.5"), Decimal("1.75"), Decimal("2"), Decimal("2.5")]
    )
    ca = cl * ratio
    inventory = (ca * Decimal("0.4") // 100) * 100
    prepaid = Decimal(rng.randrange(5, 31)) * 100
    receivables = (ca * Decimal("0.35") // 100) * 100
    cash = ca - inventory - prepaid - receivables
    payables = (cl * Decimal("0.6") // 100) * 100
    accrued = cl - payables
    quick = ((ca - inventory - prepaid) / cl).quantize(Decimal("0.0001"))
    data = (
        "# Balances — 2026-01-31\n\n| Item | USD |\n|---|---:|\n"
        f"| Cash | {money(cash)} |\n"
        f"| Accounts receivable | {money(receivables)} |\n"
        f"| Inventory | {money(inventory)} |\n"
        f"| Prepaid expenses | {money(prepaid)} |\n"
        f"| Accounts payable | {money(payables)} |\n"
        f"| Accrued liabilities | {money(accrued)} |\n"
        "\nNo non-current items are listed; every item above is current.\n"
    )
    policy = """# Ratio conventions (applies to this task)

- Current ratio = total current assets / total current liabilities.
  Inventory and prepaid expenses are current assets.
- Answer with the ratio (for example 1.50) in `/app/answer.json`.
"""
    question = _numeric_question(
        "current ratio",
        "Using `/app/documents/balances.md` and `/app/policy.md`, compute the **current ratio**.",
        "the ratio",
    )
    return _numeric_instance(
        task_id="current-ratio",
        family="financial-analysis",
        title="Compute the current ratio",
        question=question,
        policy=policy,
        data_name="balances.md",
        data=data,
        gold=ratio,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "liquidity-ratio", "current-ratio"],
        abs_tolerance="0.01",
        trap_value=format(quick, "f"),
    )


def bank_adjusted_balance(seed: int) -> TaskInstance:
    """Numeric: adjusted bank balance. Trap: unadjusted book balance."""
    rng = random.Random(seed)
    statement = Decimal(rng.randrange(400, 1601)) * 25
    in_transit = Decimal(rng.randrange(20, 121)) * 25
    outstanding = Decimal(rng.randrange(16, 101)) * 25
    fee = Decimal(rng.randrange(1, 9)) * 25
    nsf = Decimal(rng.randrange(4, 25)) * 25
    interest = Decimal(rng.randrange(1, 7)) * 25
    gold = statement + in_transit - outstanding
    book = gold + fee + nsf - interest
    data = (
        "# Bank reconciliation data — 2026-01-31\n\n| Item | USD |\n|---|---:|\n"
        f"| Balance per bank statement | {money(statement)} |\n"
        f"| Deposits in transit | {money(in_transit)} |\n"
        f"| Outstanding checks | {money(outstanding)} |\n"
        f"| Balance per books (unadjusted) | {money(book)} |\n"
        f"| Bank service charge (unrecorded) | {money(fee)} |\n"
        f"| NSF check returned (unrecorded) | {money(nsf)} |\n"
        f"| Interest credited by bank (unrecorded) | {money(interest)} |\n"
    )
    policy = """# Bank reconciliation conventions (applies to this task)

- Adjusted bank balance = balance per bank statement + deposits in
  transit - outstanding checks. Book-side items (service charges, NSF
  checks, interest) do not enter the bank side.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "adjusted bank balance",
        "Using `/app/documents/reconciliation_data.md` and `/app/policy.md`, "
        "compute the **adjusted bank balance** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="bank-adjusted-balance",
        family="bank-reconciliation",
        title="Compute the adjusted bank balance",
        question=question,
        policy=policy,
        data_name="reconciliation_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "bank-reconciliation", "adjusted-balance"],
        abs_tolerance="0.01",
        trap_value=money(book),
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
    "ppe-disposal": ppe_disposal,
    "inventory-costing-nrv": inventory_costing_nrv,
    "revenue-bundle-allocation": revenue_bundle_allocation,
    "suspense-clearance": suspense_clearance,
    "loan-effective-interest": loan_effective_interest,
    "perpetual-sale-with-cost": perpetual_sale_with_cost,
    "sales-return-restock": sales_return_restock,
    "supplies-adjustment": supplies_adjustment,
    "accrued-wages-adjustment": accrued_wages_adjustment,
    "straight-line-depreciation": straight_line_depreciation,
    "note-interest-accrual": note_interest_accrual,
    "payroll-withholdings": payroll_withholdings,
    "bond-discount-amortization": bond_discount_amortization,
    "cvp-target-profit-units": cvp_target_profit_units,
    "process-costing-equivalent-units": process_costing_equivalent_units,
    "operating-cash-flow-indirect": operating_cash_flow_indirect,
    "inventory-days-on-hand": inventory_days_on_hand,
    "equity-issue-above-par": equity_issue_above_par,
    "cash-dividend-declaration": cash_dividend_declaration,
    "treasury-stock-repurchase": treasury_stock_repurchase,
    "closing-entries-income-summary": closing_entries_income_summary,
    "job-overhead-applied": job_overhead_applied,
    "note-dishonored": note_dishonored,
    "lifo-ending-inventory": lifo_ending_inventory,
    "materials-price-variance": materials_price_variance,
    "npv-project-evaluation": npv_project_evaluation,
    "make-or-buy-advantage": make_or_buy_advantage,
    "absorption-variable-income-difference": absorption_variable_income_difference,
    "current-ratio": current_ratio,
    "bank-adjusted-balance": bank_adjusted_balance,
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
    "ppe-disposal": 111,
    "inventory-costing-nrv": 112,
    "revenue-bundle-allocation": 113,
    "suspense-clearance": 114,
    "loan-effective-interest": 115,
    "perpetual-sale-with-cost": 116,
    "sales-return-restock": 117,
    "supplies-adjustment": 118,
    "accrued-wages-adjustment": 119,
    "straight-line-depreciation": 120,
    "note-interest-accrual": 121,
    "payroll-withholdings": 122,
    "bond-discount-amortization": 123,
    "cvp-target-profit-units": 124,
    "process-costing-equivalent-units": 125,
    "operating-cash-flow-indirect": 126,
    "inventory-days-on-hand": 127,
    "equity-issue-above-par": 128,
    "cash-dividend-declaration": 129,
    "treasury-stock-repurchase": 130,
    "closing-entries-income-summary": 131,
    "job-overhead-applied": 132,
    "note-dishonored": 133,
    "lifo-ending-inventory": 134,
    "materials-price-variance": 135,
    "npv-project-evaluation": 136,
    "make-or-buy-advantage": 137,
    "absorption-variable-income-difference": 138,
    "current-ratio": 139,
    "bank-adjusted-balance": 140,
}
