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
    factor = _annuity_factor(rate, years)
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


TRAINING = "Expenses:Training"
CAP_COST_ACCOUNTS = [(TRAINING, "Staff training expense")]


def capitalized_cost_bundle(seed: int) -> TaskInstance:
    """Scenario: machine invoice bundles capitalizable and period costs.

    Oracle: equipment = invoice price + freight-in + installation/testing;
    staff training and the first-year service plan are expensed.
    Trap: capitalizing the whole invoice (training/service inflate cost).
    Level V/U/V/U/V/V/V -> vocational (borderline).
    """
    rng = random.Random(seed)
    price = Decimal(rng.randrange(200, 601)) * 50
    freight = Decimal(rng.randrange(8, 41)) * 25
    install = Decimal(rng.randrange(10, 51)) * 25
    training = Decimal(rng.randrange(6, 25)) * 25
    service = Decimal(rng.randrange(12, 41)) * 25
    equipment = price + freight + install
    period = training + service
    total = equipment + period
    day = rng.randint(4, 24)
    date = f"2026-01-{day:02d}"
    opening = Decimal("60000.00")
    initial = _ledger_header(opening, CAP_COST_ACCOUNTS)
    invoice = (
        f"# Supplier invoice — packaging machine, {date}\n\n"
        "| Item | USD |\n|---|---:|\n"
        f"| Machine (invoice price) | {money(price)} |\n"
        f"| Freight-in | {money(freight)} |\n"
        f"| Installation and testing | {money(install)} |\n"
        f"| Operator training course | {money(training)} |\n"
        f"| First-year service plan | {money(service)} |\n"
        f"| **Total paid from checking** | **{money(total)}** |\n"
        "\nThe machine was ready for use on the invoice date.\n"
    )
    policy = POLICY + (
        "- Capitalized cost of equipment includes the invoice price and all\n"
        "  costs needed to bring it to working condition (freight-in,\n"
        "  installation, testing). Staff training and post-commissioning\n"
        "  service plans are period expenses (`Expenses:Training` and\n"
        "  `Expenses:Repairs` respectively).\n"
    )
    solution = initial + _txn(
        date,
        "Supplier",
        "Packaging machine acquired and commissioned",
        [
            ("Assets:Equipment", equipment),
            (TRAINING, training),
            ("Expenses:Repairs", service),
            (BANK, -total),
        ],
    )
    return TaskInstance(
        task_id="capitalized-cost-bundle",
        family="fixed-assets",
        title="Capitalize a machine's cost from a bundled invoice",
        instruction=(
            "Record the acquisition in `/app/documents/machine_invoice.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md`. Append new "
            f"balanced transactions dated {date}; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(CAP_COST_ACCOUNTS),
            "documents/machine_invoice.md": invoice,
        },
        expected=_expected(
            "capitalized-cost-bundle",
            "fixed-assets",
            seed,
            expected_deltas={
                "Assets:Equipment": money(equipment),
                TRAINING: money(training),
                "Expenses:Repairs": money(service),
                BANK: money(-total),
            },
            expected_new_transactions=[1, 3],
            expected_period=[date, date],
            required_final_balances={"Assets:Equipment": money(equipment)},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["fixed-assets", "capitalized-cost", "freight-in"],
        level="vocational",
    )


PAYROLL_TAX = "Expenses:PayrollTaxes"
UNEMPLOYMENT_PAYABLE = "Liabilities:UnemploymentTaxPayable"
EMPLOYER_TAX_ACCOUNTS = [
    (WAGES, "Gross wages expense"),
    (PAYROLL_TAX, "Employer payroll taxes (company cost, above gross pay)"),
    (FICA_PAYABLE, "Social contributions payable to the authority"),
    (UNEMPLOYMENT_PAYABLE, "Unemployment insurance payable"),
]


def employer_payroll_taxes(seed: int) -> TaskInstance:
    """Scenario: employer-side payroll taxes on January gross wages.

    Oracle: payroll-tax expense = gross x (FICA match + unemployment %),
    credited to the two payables. Trap: treating employer taxes as a
    deduction from employees' pay (crediting wages payable / reducing wages).
    Level V/U/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    gross = Decimal(rng.randrange(8, 26)) * 2000
    fica_rate = Decimal("0.0765")
    futa_rate = rng.choice([Decimal("0.006"), Decimal("0.008")])
    fica = (gross * fica_rate).quantize(CENT)
    futa = (gross * futa_rate).quantize(CENT)
    opening = Decimal("80000.00")
    initial = _ledger_header(opening, EMPLOYER_TAX_ACCOUNTS) + _txn(
        "2026-01-31",
        "Payroll",
        "January gross wages (employee entry already recorded)",
        [(WAGES, gross), (BANK, -gross)],
    )
    doc = (
        "# Employer payroll taxes — January 2026\n\n"
        f"Gross wages for January (already recorded and paid): USD {money(gross)}.\n"
        "The employer's own taxes on those wages, not yet recorded:\n\n"
        "- Social contributions (employer match): 7.65% of gross wages\n"
        f"- Unemployment insurance: {futa_rate * 100:.1f}% of gross wages\n"
        "Both are payable to the authorities in February.\n"
    )
    policy = POLICY + (
        "- Taxes the employer bears on top of gross pay are a separate\n"
        "  payroll-tax expense of the company, credited to the respective\n"
        "  payable. They never reduce employees' wages or wages expense.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Payroll",
        "Employer payroll taxes on January wages",
        [(PAYROLL_TAX, fica + futa), (FICA_PAYABLE, -fica), (UNEMPLOYMENT_PAYABLE, -futa)],
    )
    return TaskInstance(
        task_id="employer-payroll-taxes",
        family="payroll",
        title="Record employer payroll taxes",
        instruction=(
            "Record the employer taxes described in "
            "`/app/documents/employer_taxes.md` in `/app/ledger.beancount`, "
            "following `/app/policy.md`. Append new balanced transactions "
            "dated 2026-01-31; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(EMPLOYER_TAX_ACCOUNTS),
            "documents/employer_taxes.md": doc,
        },
        expected=_expected(
            "employer-payroll-taxes",
            "payroll",
            seed,
            expected_deltas={
                PAYROLL_TAX: money(fica + futa),
                FICA_PAYABLE: money(-fica),
                UNEMPLOYMENT_PAYABLE: money(-futa),
            },
            expected_new_transactions=[1, 2],
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={WAGES: money(gross)},
        ),
        solution_ledger=solution,
        keywords=["payroll", "employer-taxes", "fica-match"],
        level="vocational",
    )


LT_NOTE = "Liabilities:LongTermNotePayable"
CURRENT_PORTION = "Liabilities:CurrentPortionOfLongTermDebt"
RECLASS_ACCOUNTS = [
    (LT_NOTE, "Long-term note payable (portion due after one year)"),
    (CURRENT_PORTION, "Current portion of long-term debt (due within one year)"),
]


def current_portion_reclass(seed: int) -> TaskInstance:
    """Scenario: reporting-date reclass of the note principal due next year.

    Oracle: move one year's principal installment from long-term to the
    current-portion account. Trap: reclassifying the whole balance.
    Level V/U/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    annual = Decimal(rng.randrange(4, 16)) * 1000
    years_left = rng.randint(3, 6)
    balance = annual * years_left
    opening = Decimal("10000.00")
    initial = _ledger_header(opening, RECLASS_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        "Opening long-term note balance",
        [("Equity:Opening-Balances", balance), (LT_NOTE, -balance)],
    )
    doc = (
        "# Note summary — reporting date 2026-01-31\n\n"
        f"Note balance: USD {money(balance)}. Principal is repayable in equal "
        f"annual installments of USD {money(annual)} each 31 December; "
        f"{years_left} installments remain (first due 2026-12-31).\n"
    )
    policy = POLICY + (
        "- At the reporting date, principal due within the next twelve\n"
        "  months is presented as a current liability: reclassify that\n"
        "  installment from `Liabilities:LongTermNotePayable` to\n"
        "  `Liabilities:CurrentPortionOfLongTermDebt`.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Reporting",
        "Reclassify principal due within twelve months",
        [(LT_NOTE, annual), (CURRENT_PORTION, -annual)],
    )
    return TaskInstance(
        task_id="current-portion-reclass",
        family="borrowings",
        title="Reclassify the current portion of a long-term note",
        instruction=(
            "Record the reporting-date reclassification for the note in "
            "`/app/documents/note_summary.md` in `/app/ledger.beancount`, "
            "following `/app/policy.md`. Append exactly one balanced "
            "transaction dated 2026-01-31; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(RECLASS_ACCOUNTS),
            "documents/note_summary.md": doc,
        },
        expected=_expected(
            "current-portion-reclass",
            "borrowings",
            seed,
            expected_deltas={LT_NOTE: money(annual), CURRENT_PORTION: money(-annual)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={LT_NOTE: money(-(balance - annual))},
        ),
        solution_ledger=solution,
        keywords=["current-portion", "long-term-debt", "reclassification"],
        level="vocational",
    )


PURCHASES = "Expenses:Purchases"
FREIGHT_IN = "Expenses:FreightIn"
PERIODIC_ACCOUNTS = [
    (AP, "Trade payables (supplier invoices on credit)"),
    (PURCHASES, "Purchases of merchandise (periodic system)"),
    (FREIGHT_IN, "Freight-in on merchandise purchases"),
]


def periodic_purchase_with_freight(seed: int) -> TaskInstance:
    """Scenario: merchandise bought on credit under the periodic system.

    Oracle: Purchases at invoice amount + FreightIn debited, AP credited
    for the total owed. Trap: debiting Inventory (perpetual habit) — the
    ledger intentionally has no inventory movement account for purchases.
    Level V/V/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    supplier = rng.choice(["Apex Components", "Crestline Materials", "Bolt & Nut Supply"])
    goods = Decimal(rng.randrange(80, 401)) * 25
    freight = Decimal(rng.randrange(2, 13)) * 25
    day = rng.randint(4, 24)
    date = f"2026-01-{day:02d}"
    opening = Decimal("20000.00")
    initial = _ledger_header(opening, PERIODIC_ACCOUNTS)
    invoice = (
        f"# Purchase invoice — {supplier}, {date}\n\n"
        f"Merchandise: USD {money(goods)}\n"
        f"Freight charged by supplier (FOB shipping point): USD {money(freight)}\n"
        f"Total on account: USD {money(goods + freight)} (due in 30 days)\n"
    )
    policy = POLICY + (
        "- The company uses the PERIODIC inventory system: merchandise buys\n"
        "  are debited to `Expenses:Purchases` (inventory is only counted at\n"
        "  period-end). Freight-in on purchases is debited to\n"
        "  `Expenses:FreightIn`, not to purchases.\n"
    )
    solution = initial + _txn(
        date,
        supplier,
        "Merchandise purchase on credit (periodic)",
        [(PURCHASES, goods), (FREIGHT_IN, freight), (AP, -(goods + freight))],
    )
    return TaskInstance(
        task_id="periodic-purchase-with-freight",
        family="inventory",
        title="Record a periodic-system purchase with freight-in",
        instruction=(
            f"Record the purchase in `/app/documents/purchase_invoice.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md` and "
            f"`/app/chart_of_accounts.md`. Append new balanced transactions "
            f"dated {date}; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(PERIODIC_ACCOUNTS),
            "documents/purchase_invoice.md": invoice,
        },
        expected=_expected(
            "periodic-purchase-with-freight",
            "inventory",
            seed,
            expected_deltas={
                PURCHASES: money(goods),
                FREIGHT_IN: money(freight),
                AP: money(-(goods + freight)),
            },
            expected_new_transactions=[1, 2],
            expected_period=[date, date],
            required_final_balances={AP: money(-(goods + freight))},
        ),
        solution_ledger=solution,
        keywords=["periodic-inventory", "purchases", "freight-in"],
        level="vocational",
    )


def bad_debt_percent_of_sales(seed: int) -> TaskInstance:
    """Scenario: month-end allowance under the percent-of-credit-sales method.

    Oracle: expense = credit sales x estimated % (the existing allowance
    balance is NOT considered under this method). Trap: aging-style
    true-up that credits only the shortfall over the existing balance.
    Level V/U/V/V/V/U/V -> vocational.
    """
    rng = random.Random(seed)
    credit_sales = Decimal(rng.randrange(80, 321)) * 500
    pct = rng.choice([Decimal("0.01"), Decimal("0.015"), Decimal("0.02")])
    expense = (credit_sales * pct).quantize(CENT)
    existing = Decimal(rng.randrange(8, 41)) * 50
    opening = Decimal("10000.00")
    initial = (
        _ledger_header(opening, RECEIVABLE_ACCOUNTS)
        + _txn(
            "2026-01-01",
            "Opening",
            "Opening allowance for doubtful accounts",
            [("Equity:Opening-Balances", existing), (ALLOWANCE, -existing)],
        )
        + _txn(
            "2026-01-15",
            "Customers",
            "January credit sales",
            [(AR, credit_sales), ("Income:Sales", -credit_sales)],
        )
    )
    doc = (
        "# Credit sales summary — January 2026\n\n"
        f"Net credit sales: USD {money(credit_sales)}.\n"
        f"Uncollectibles are estimated at {pct * 100:.1f}% of net credit sales.\n"
        f"Allowance balance at 2026-01-01 (credit): USD {money(existing)}.\n"
        "No write-offs occurred in January.\n"
    )
    policy = POLICY + (
        "- Uncollectibles are estimated by the percent-of-credit-sales\n"
        "  method: the month-end entry records bad-debt expense equal to the\n"
        "  estimated percent of the month's net credit sales. Under this\n"
        "  method the pre-existing allowance balance is not considered when\n"
        "  computing the entry.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Allowance",
        "Estimated uncollectibles on January credit sales",
        [(BAD_DEBTS, expense), (ALLOWANCE, -expense)],
    )
    return TaskInstance(
        task_id="bad-debt-percent-of-sales",
        family="receivables",
        title="Estimate uncollectibles by percent of credit sales",
        instruction=(
            "Record the month-end estimate in `/app/documents/credit_sales.md` "
            "in `/app/ledger.beancount`, following `/app/policy.md`. Append "
            "exactly one balanced transaction dated 2026-01-31; do not edit "
            "existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(RECEIVABLE_ACCOUNTS),
            "documents/credit_sales.md": doc,
        },
        expected=_expected(
            "bad-debt-percent-of-sales",
            "receivables",
            seed,
            expected_deltas={BAD_DEBTS: money(expense), ALLOWANCE: money(-expense)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={ALLOWANCE: money(-(existing + expense))},
        ),
        solution_ledger=solution,
        keywords=["bad-debt", "percent-of-sales", "allowance"],
        level="vocational",
    )


SALES_DISCOUNTS = "Income:SalesDiscounts"
DISCOUNT_ACCOUNTS = [
    (AR, "Trade receivables (customer invoices on credit)"),
    (SALES_DISCOUNTS, "Contra-revenue: cash discounts taken by customers"),
]


def cash_discount_receipt(seed: int) -> TaskInstance:
    """Scenario: customer pays within the discount period (gross method).

    Oracle: Bank at net, SalesDiscounts at the discount, AR credited gross.
    Trap: crediting AR only with the cash received (discount left in AR).
    Level V/U/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    customer = rng.choice(["Cobalt Retail", "Delta Foods", "Harbor Clinics"])
    gross = Decimal(rng.randrange(40, 201)) * 50
    pct = rng.choice([Decimal("0.01"), Decimal("0.02"), Decimal("0.03")])
    discount = (gross * pct).quantize(CENT)
    net = gross - discount
    opening = Decimal("10000.00")
    initial = _ledger_header(opening, DISCOUNT_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        f"Opening receivable, {customer}",
        [(AR, gross), ("Equity:Opening-Balances", -gross)],
    )
    doc = (
        f"# Remittance — {customer}, 2026-01-09\n\n"
        f"The customer paid the outstanding invoice of USD {money(gross)} within "
        f"the discount period and took the {pct * 100:.0f}% cash discount "
        "(terms stated on the original invoice). Cash received into checking: "
        f"USD {money(net)}.\n"
    )
    policy = POLICY + (
        "- Sales are recorded gross. Discounts taken by customers are a\n"
        "  reduction of revenue (`Income:SalesDiscounts`): on payment, debit\n"
        "  bank for the cash received, debit sales discounts for the discount\n"
        "  taken, and credit receivables for the full invoice amount.\n"
    )
    solution = initial + _txn(
        "2026-01-09",
        customer,
        "Payment received within discount period",
        [(BANK, net), (SALES_DISCOUNTS, discount), (AR, -gross)],
    )
    return TaskInstance(
        task_id="cash-discount-receipt",
        family="receivables",
        title="Record a customer payment taking a cash discount",
        instruction=(
            "Record the remittance in `/app/documents/remittance.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated 2026-01-09; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(DISCOUNT_ACCOUNTS),
            "documents/remittance.md": doc,
        },
        expected=_expected(
            "cash-discount-receipt",
            "receivables",
            seed,
            expected_deltas={
                BANK: money(net),
                SALES_DISCOUNTS: money(discount),
                AR: money(-gross),
            },
            expected_period=["2026-01-09", "2026-01-09"],
            required_final_balances={AR: "0.00"},
        ),
        solution_ledger=solution,
        keywords=["cash-discount", "gross-method", "contra-revenue"],
        level="vocational",
    )


def abc_overhead_assigned(seed: int) -> TaskInstance:
    """Numeric: ABC assignment for one pool. Trap: plantwide DLH rate."""
    rng = random.Random(seed)
    rate = Decimal(rng.randrange(20, 121)) * 5
    total_setups = rng.randrange(40, 161, 10)
    pool = rate * total_setups
    product_setups = rng.randrange(5, total_setups // 2, 5)
    gold = rate * product_setups
    dlh_total = rng.randrange(2000, 9001, 250)
    dlh_product = rng.randrange(250, dlh_total // 2, 250)
    trap = (pool / dlh_total * dlh_product).quantize(CENT)
    if trap == gold:
        dlh_product += 250
        trap = (pool / dlh_total * dlh_product).quantize(CENT)
    data = (
        "# Activity-based costing — setup cost pool, January 2026\n\n"
        "| Item | Value |\n|---|---:|\n"
        f"| Setup overhead pool | USD {money(pool)} |\n"
        f"| Total setups (all products) | {total_setups} |\n"
        f"| Setups for Product A | {product_setups} |\n"
        f"| Direct-labor hours, all products | {dlh_total} |\n"
        f"| Direct-labor hours, Product A | {dlh_product} |\n"
    )
    policy = """# ABC conventions (applies to this task)

- Activity rate = cost pool / total driver quantity (here, setups).
- Overhead assigned to a product = activity rate x the product's
  driver quantity. Direct-labor hours are not this pool's driver.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "ABC overhead assigned to Product A",
        "Using `/app/documents/abc_data.md` and `/app/policy.md`, compute the "
        "setup overhead **assigned to Product A** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="abc-overhead-assigned",
        family="activity-based-costing",
        title="Assign setup overhead to a product (ABC)",
        question=question,
        policy=policy,
        data_name="abc_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "abc", "overhead-allocation"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


def high_low_variable_cost(seed: int) -> TaskInstance:
    """Numeric: variable cost per unit by high-low. Trap: avg cost at high."""
    rng = random.Random(seed)
    vc = Decimal(rng.randrange(200, 1501, 25)) / 100
    fixed = Decimal(rng.randrange(100, 601)) * 50
    low_units = rng.randrange(1000, 4001, 250)
    high_units = low_units + rng.randrange(1000, 4001, 250)
    trap = ((fixed + vc * high_units) / high_units).quantize(Decimal("0.0001"))
    data = (
        "# Utility cost observations\n\n| Month | Units | Total cost (USD) |\n|---|---:|---:|\n"
        f"| Low-activity month | {low_units} | {money(fixed + vc * low_units)} |\n"
        f"| High-activity month | {high_units} | {money(fixed + vc * high_units)} |\n"
    )
    policy = """# High-low conventions (applies to this task)

- Variable cost per unit = (total cost at high activity - total cost at
  low activity) / (high units - low units).
- Answer in USD per unit in `/app/answer.json`.
"""
    question = _numeric_question(
        "variable cost per unit (high-low)",
        "Using `/app/documents/cost_observations.md` and `/app/policy.md`, "
        "compute the **variable cost per unit** in USD.",
        "the USD amount per unit",
    )
    return _numeric_instance(
        task_id="high-low-variable-cost",
        family="cost-behavior",
        title="Estimate variable cost per unit (high-low)",
        question=question,
        policy=policy,
        data_name="cost_observations.md",
        data=data,
        gold=vc,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "high-low", "cost-behavior"],
        abs_tolerance="0.01",
        trap_value=format(trap, "f"),
    )


def cash_collections_budget(seed: int) -> TaskInstance:
    """Numeric: February collections from a two-month pattern. Trap: Feb only."""
    rng = random.Random(seed)
    jan_sales = Decimal(rng.randrange(80, 321)) * 500
    feb_sales = Decimal(rng.randrange(80, 321)) * 500
    now_pct = rng.choice([50, 60, 70])
    later = 100 - now_pct
    gold = feb_sales * now_pct / 100 + jan_sales * later / 100
    trap = feb_sales * now_pct / 100
    data = (
        "# Sales budget\n\n| Month | Budgeted credit sales (USD) |\n|---|---:|\n"
        f"| January | {money(jan_sales)} |\n"
        f"| February | {money(feb_sales)} |\n\n"
        f"Collections: {now_pct}% in the month of sale, the remaining "
        f"{later}% in the following month. All January collections follow "
        "the same pattern.\n"
    )
    policy = """# Collections budget conventions (applies to this task)

- A month's expected collections = the current-month share of that
  month's sales plus the following-month share of the prior month's sales.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "budgeted February cash collections",
        "Using `/app/documents/sales_budget.md` and `/app/policy.md`, compute "
        "**expected cash collections in February** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="cash-collections-budget",
        family="budgeting",
        title="Compute budgeted cash collections",
        question=question,
        policy=policy,
        data_name="sales_budget.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "cash-budget", "collections"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


def gross_profit_from_trial_balance(seed: int) -> TaskInstance:
    """Numeric: gross profit from TB data. Trap: gross sales minus COGS."""
    rng = random.Random(seed)

    def amt(lo, hi):
        return Decimal(rng.randrange(lo, hi)) * 100

    sales = amt(400, 1201)
    returns = amt(10, 61)
    discounts = amt(5, 31)
    beginning = amt(60, 201)
    purchases = amt(200, 601)
    freight = amt(5, 41)
    ending = amt(50, 181)
    opex = amt(50, 201)
    cogs = beginning + purchases + freight - ending
    gold = sales - returns - discounts - cogs
    trap = sales - cogs
    data = (
        "# Trial-balance extracts — year ended 2025-12-31\n\n| Item | USD |\n|---|---:|\n"
        f"| Sales (gross) | {money(sales)} |\n"
        f"| Sales returns and allowances | {money(returns)} |\n"
        f"| Sales discounts | {money(discounts)} |\n"
        f"| Inventory, 2025-01-01 | {money(beginning)} |\n"
        f"| Purchases | {money(purchases)} |\n"
        f"| Freight-in | {money(freight)} |\n"
        f"| Inventory, 2025-12-31 | {money(ending)} |\n"
        f"| Operating expenses | {money(opex)} |\n"
    )
    policy = """# Gross profit conventions (applies to this task)

- Net sales = gross sales - sales returns and allowances - sales discounts.
- Cost of goods sold = beginning inventory + purchases + freight-in
  - ending inventory.
- Gross profit = net sales - cost of goods sold. Operating expenses are
  below gross profit and excluded.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "gross profit",
        "Using `/app/documents/trial_balance.md` and `/app/policy.md`, compute "
        "**gross profit** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="gross-profit-from-trial-balance",
        family="financial-reporting",
        title="Compute gross profit from trial-balance data",
        question=question,
        policy=policy,
        data_name="trial_balance.md",
        data=data,
        gold=gold,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "gross-profit", "income-statement"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


def ending_retained_earnings(seed: int) -> TaskInstance:
    """Numeric: ending retained earnings. Trap: adding share-issue proceeds."""
    rng = random.Random(seed)

    def amt(lo, hi):
        return Decimal(rng.randrange(lo, hi)) * 100

    beginning = amt(200, 901)
    net_income = amt(60, 301)
    dividends = amt(10, 81)
    issue = amt(100, 401)
    treasury = amt(20, 101)
    gold = beginning + net_income - dividends
    trap = gold + issue
    data = (
        "# Equity activity — year ended 2025-12-31\n\n| Item | USD |\n|---|---:|\n"
        f"| Retained earnings, 2025-01-01 | {money(beginning)} |\n"
        f"| Net income | {money(net_income)} |\n"
        f"| Cash dividends declared | {money(dividends)} |\n"
        f"| New shares issued for cash | {money(issue)} |\n"
        f"| Treasury shares repurchased | {money(treasury)} |\n"
    )
    policy = """# Retained earnings conventions (applies to this task)

- Ending retained earnings = beginning retained earnings + net income
  - dividends declared. Share issues increase share capital/APIC, and
  treasury purchases are contra-equity; neither enters retained earnings.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "ending retained earnings",
        "Using `/app/documents/equity_activity.md` and `/app/policy.md`, compute "
        "**retained earnings at 2025-12-31** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="ending-retained-earnings",
        family="equity",
        title="Compute ending retained earnings",
        question=question,
        policy=policy,
        data_name="equity_activity.md",
        data=data,
        gold=gold,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "retained-earnings", "equity-changes"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


def present_value_lump_sum(seed: int) -> TaskInstance:
    """Numeric: PV of a lump sum from a stated factor. Trap: face amount."""
    rng = random.Random(seed)
    years = rng.choice([3, 5, 8, 10])
    rate = rng.choice([Decimal("0.06"), Decimal("0.08"), Decimal("0.10")])
    factor = (Decimal(1) / (1 + rate) ** years).quantize(Decimal("0.0001"))
    future = Decimal(rng.randrange(20, 121)) * 1000
    gold = (future * factor).quantize(CENT)
    data = (
        "# Note receivable terms\n\n| Item | Value |\n|---|---:|\n"
        f"| Single amount receivable at maturity | USD {money(future)} |\n"
        f"| Term | {years} years |\n"
        f"| Discount rate | {rate * 100:.0f}% |\n"
        f"| Present value factor ({rate * 100:.0f}%, {years} years, single sum) | {factor} |\n"
    )
    policy = """# Present value conventions (applies to this task)

- Present value = future amount x the single-sum factor given in the
  data (use it as stated; do not recompute it).
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "present value of a lump sum",
        "Using `/app/documents/note_terms.md` and `/app/policy.md`, compute "
        "the **present value** of the amount receivable in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="present-value-lump-sum",
        family="time-value-of-money",
        title="Compute the present value of a lump sum",
        question=question,
        policy=policy,
        data_name="note_terms.md",
        data=data,
        gold=gold,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "present-value", "time-value"],
        abs_tolerance="0.01",
        trap_value=money(future),
    )


def flexible_budget_total_cost(seed: int) -> TaskInstance:
    """Numeric: flexible-budget cost at actual volume. Trap: static budget."""
    rng = random.Random(seed)
    planned = rng.randrange(4000, 10001, 250)
    actual = planned + rng.randrange(500, 2501, 250)
    vc = Decimal(rng.randrange(300, 1201, 25)) / 100
    fixed = Decimal(rng.randrange(100, 501)) * 100
    gold = fixed + vc * actual
    trap = fixed + vc * planned
    data = (
        "# Budget data — January 2026\n\n| Item | Value |\n|---|---:|\n"
        f"| Planned (static-budget) units | {planned} |\n"
        f"| Actual units | {actual} |\n"
        f"| Variable cost | USD {money(vc)} per unit |\n"
        f"| Fixed costs (total, in the relevant range) | USD {money(fixed)} |\n"
    )
    policy = """# Flexible budget conventions (applies to this task)

- Flexible-budget total cost at the actual volume = total fixed costs
  (unchanged in the relevant range) + variable cost per unit x actual units.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "flexible-budget total cost",
        "Using `/app/documents/budget_data.md` and `/app/policy.md`, compute "
        "the **flexible-budget total cost** for January in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="flexible-budget-total-cost",
        family="budgeting",
        title="Compute flexible-budget total cost at actual volume",
        question=question,
        policy=policy,
        data_name="budget_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "flexible-budget"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


OWNER_CAPITAL = "Equity:OwnerCapital"
NARRATIVE_ACCOUNTS = [
    (OWNER_CAPITAL, "Owner capital contributed"),
    (SERVICES, "Service revenue (recognized as delivered)"),
]


def narrative_multi_transactions(seed: int) -> TaskInstance:
    """Scenario: four independent January events narrated in one document.

    Oracle: owner investment, equipment bought for cash, services rendered
    for cash, rent paid — each its own balanced entry (combined/split
    equivalents accepted on state). Trap: expensing the equipment.
    Level V/U/V/V/V/U/V -> vocational.
    """
    rng = random.Random(seed)
    invest = Decimal(rng.randrange(100, 401)) * 50
    equipment = Decimal(rng.randrange(40, 161)) * 50
    services = Decimal(rng.randrange(50, 201)) * 25
    rent = Decimal(rng.randrange(20, 81)) * 25
    opening = Decimal("5000.00")
    initial = _ledger_header(opening, NARRATIVE_ACCOUNTS)
    doc = (
        "# January 2026 transactions (none recorded yet)\n\n"
        f"1. 2026-01-03 — The owner invested USD {money(invest)} cash in the business.\n"
        f"2. 2026-01-07 — Bought equipment for USD {money(equipment)}, paid from "
        "checking. The equipment will be used for several years.\n"
        f"3. 2026-01-15 — Performed services for a customer and received "
        f"USD {money(services)} cash.\n"
        f"4. 2026-01-20 — Paid January office rent of USD {money(rent)} from checking.\n"
    )
    solution = (
        initial
        + _txn(
            "2026-01-03",
            "Owner",
            "Cash invested by owner",
            [(BANK, invest), (OWNER_CAPITAL, -invest)],
        )
        + _txn(
            "2026-01-07",
            "Vendor",
            "Equipment purchased",
            [("Assets:Equipment", equipment), (BANK, -equipment)],
        )
        + _txn(
            "2026-01-15",
            "Customer",
            "Services rendered for cash",
            [(BANK, services), (SERVICES, -services)],
        )
        + _txn(
            "2026-01-20", "Landlord", "January rent paid", [("Expenses:Rent", rent), (BANK, -rent)]
        )
    )
    return TaskInstance(
        task_id="narrative-multi-transactions",
        family="transaction-classification",
        title="Journalize four January transactions",
        instruction=(
            "Record all four transactions in `/app/documents/transactions.md` "
            "in `/app/ledger.beancount`, following `/app/policy.md` and "
            "`/app/chart_of_accounts.md`. Append new balanced transactions on "
            "their stated January dates; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": POLICY,
            "chart_of_accounts.md": _chart_md(NARRATIVE_ACCOUNTS),
            "documents/transactions.md": doc,
        },
        expected=_expected(
            "narrative-multi-transactions",
            "transaction-classification",
            seed,
            expected_deltas={
                BANK: money(invest - equipment + services - rent),
                OWNER_CAPITAL: money(-invest),
                "Assets:Equipment": money(equipment),
                SERVICES: money(-services),
                "Expenses:Rent": money(rent),
            },
            expected_new_transactions=[3, 6],
            required_final_balances={BANK: money(opening + invest - equipment + services - rent)},
        ),
        solution_ledger=solution,
        keywords=["journal-entries", "narrative-transactions"],
        level="vocational",
    )


def units_of_production_depreciation(seed: int) -> TaskInstance:
    """Scenario: January depreciation under units-of-production.

    Oracle: (cost - residual) / total estimated units x January units.
    Trap: ignoring residual value in the per-unit rate.
    Level V/U/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    asset = rng.choice(["printing press", "bottling machine", "delivery truck"])
    unit_label = rng.choice(["units", "hours", "miles"])
    rate = (Decimal(rng.randrange(25, 201, 25)) / 100).quantize(CENT)
    total_units = rng.randrange(40000, 120001, 5000)
    residual = Decimal(rng.randrange(5, 41)) * 100
    cost = rate * total_units + residual
    month_units = rng.randrange(800, 4001, 100)
    expense = rate * month_units
    opening = cost + Decimal("20000.00")
    initial = _ledger_header(opening, DEPR_ACCOUNTS) + _txn(
        "2026-01-02",
        "Vendor",
        f"Purchase of {asset}",
        [("Assets:Equipment", cost), (BANK, -cost)],
    )
    doc = (
        f"# Asset register — {asset}\n\n"
        f"Placed in service 2026-01-02. Cost USD {money(cost)}; residual value "
        f"USD {money(residual)}. Expected total output: {total_units} {unit_label}. "
        f"January output: {month_units} {unit_label}. Method: units-of-production.\n"
    )
    policy = POLICY + (
        "- Units-of-production depreciation: rate per unit = (cost - residual\n"
        "  value) / total estimated output; the period charge is the rate\n"
        "  times the period's actual output.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Depreciation",
        f"January depreciation ({month_units} {unit_label}), {asset}",
        [(DEPRECIATION, expense), (ACC_DEP, -expense)],
    )
    return TaskInstance(
        task_id="units-of-production-depreciation",
        family="fixed-assets",
        title="Record units-of-production depreciation",
        instruction=(
            f"Record January depreciation for the {asset} in "
            "`/app/ledger.beancount`, using `/app/documents/asset_register.md` "
            "and `/app/policy.md`. Append exactly one balanced transaction "
            "dated 2026-01-31; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(DEPR_ACCOUNTS),
            "documents/asset_register.md": doc,
        },
        expected=_expected(
            "units-of-production-depreciation",
            "fixed-assets",
            seed,
            expected_deltas={DEPRECIATION: money(expense), ACC_DEP: money(-expense)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={ACC_DEP: money(-expense)},
        ),
        solution_ledger=solution,
        keywords=["depreciation", "units-of-production"],
        level="vocational",
    )


WARRANTY_EXPENSE = "Expenses:Warranty"
WARRANTY_LIABILITY = "Liabilities:WarrantyPayable"
WARRANTY_ACCOUNTS = [
    (WARRANTY_EXPENSE, "Estimated warranty cost of products sold"),
    (WARRANTY_LIABILITY, "Estimated warranty claims payable"),
]


def warranty_provision_and_claims(seed: int) -> TaskInstance:
    """Scenario: pay January warranty claims; accrue the estimate on new sales.

    Oracle: claims paid debit the opening warranty liability (credit bank);
    January sales x estimate % is warranty expense credited to the liability.
    Trap: expensing the claims paid (cash-basis warranty accounting).
    Level V/U/V/V/V/U/V -> vocational.
    """
    rng = random.Random(seed)
    sales = Decimal(rng.randrange(80, 321)) * 500
    pct = rng.choice([Decimal("0.02"), Decimal("0.03"), Decimal("0.04")])
    estimate = sales * pct
    claims = Decimal(rng.randrange(10, 51)) * 50
    opening_liability = claims * rng.randint(2, 4)
    opening = Decimal("50000.00")
    initial = (
        _ledger_header(opening, WARRANTY_ACCOUNTS)
        + _txn(
            "2026-01-01",
            "Opening",
            "Opening estimated warranty liability",
            [
                ("Equity:Opening-Balances", opening_liability),
                (WARRANTY_LIABILITY, -opening_liability),
            ],
        )
        + _txn(
            "2026-01-18",
            "Customers",
            "January product sales (cash)",
            [(BANK, sales), ("Income:Sales", -sales)],
        )
    )
    doc = (
        "# Warranty activity — January 2026\n\n"
        f"- Warranty repairs honored and paid in January (on earlier sales): "
        f"USD {money(claims)} from checking. Not yet recorded.\n"
        f"- January sales of USD {money(sales)} carry a warranty; expected future "
        f"claims are {pct * 100:.0f}% of sales.\n"
    )
    policy = POLICY + (
        "- Warranty cost is expensed in the period of sale at the estimated\n"
        "  rate (credit the warranty liability). Claims honored later are\n"
        "  charged against that liability, never expensed again.\n"
    )
    solution = (
        initial
        + _txn(
            "2026-01-25",
            "Customers",
            "Warranty claims honored in January",
            [(WARRANTY_LIABILITY, claims), (BANK, -claims)],
        )
        + _txn(
            "2026-01-31",
            "Warranty",
            "Estimated warranty cost on January sales",
            [(WARRANTY_EXPENSE, estimate), (WARRANTY_LIABILITY, -estimate)],
        )
    )
    return TaskInstance(
        task_id="warranty-provision-and-claims",
        family="provisions-contingencies",
        title="Pay warranty claims and accrue the new estimate",
        instruction=(
            "Record the January warranty activity in "
            "`/app/documents/warranty_activity.md` in `/app/ledger.beancount`, "
            "following `/app/policy.md`. Append new balanced transactions "
            "dated in January 2026; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(WARRANTY_ACCOUNTS),
            "documents/warranty_activity.md": doc,
        },
        expected=_expected(
            "warranty-provision-and-claims",
            "provisions-contingencies",
            seed,
            expected_deltas={
                WARRANTY_LIABILITY: money(claims - estimate),
                BANK: money(-claims),
                WARRANTY_EXPENSE: money(estimate),
            },
            expected_new_transactions=[1, 3],
            required_final_balances={
                WARRANTY_LIABILITY: money(-(opening_liability - claims + estimate))
            },
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["warranty", "provision", "matching"],
        level="vocational",
    )


SALES_TAX_PAYABLE = "Liabilities:SalesTaxPayable"
SALES_TAX_ACCOUNTS = [(SALES_TAX_PAYABLE, "Sales tax collected, due to the authority")]


def sales_tax_collection(seed: int) -> TaskInstance:
    """Scenario: cash sale with sales tax collected for the authority.

    Oracle: bank at the tax-inclusive receipt; sales net; tax payable.
    Trap: recording the whole receipt as sales revenue.
    Level V/U/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    net_sales = Decimal(rng.randrange(20, 121)) * 1000
    rate = rng.choice([Decimal("0.06"), Decimal("0.08"), Decimal("0.10")])
    tax = net_sales * rate
    day = rng.randint(4, 24)
    date = f"2026-01-{day:02d}"
    opening = Decimal("10000.00")
    initial = _ledger_header(opening, SALES_TAX_ACCOUNTS)
    doc = (
        f"# Register tape — {date}\n\n"
        f"Merchandise sold for cash: USD {money(net_sales)} before tax.\n"
        f"Sales tax collected from customers at {rate * 100:.0f}%: "
        f"USD {money(tax)}. Total cash received: USD {money(net_sales + tax)}.\n"
    )
    policy = POLICY + (
        "- Sales tax is collected as agent for the tax authority: it is a\n"
        "  liability (`Liabilities:SalesTaxPayable`), never revenue. Sales\n"
        "  are recorded at the pre-tax amount.\n"
    )
    solution = initial + _txn(
        date,
        "Register",
        "Cash sales with sales tax collected",
        [(BANK, net_sales + tax), ("Income:Sales", -net_sales), (SALES_TAX_PAYABLE, -tax)],
    )
    return TaskInstance(
        task_id="sales-tax-collection",
        family="transaction-classification",
        title="Record a cash sale with sales tax collected",
        instruction=(
            "Record the register tape in `/app/documents/register_tape.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md`. Append new "
            f"balanced transactions dated {date}; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(SALES_TAX_ACCOUNTS),
            "documents/register_tape.md": doc,
        },
        expected=_expected(
            "sales-tax-collection",
            "transaction-classification",
            seed,
            expected_deltas={
                BANK: money(net_sales + tax),
                "Income:Sales": money(-net_sales),
                SALES_TAX_PAYABLE: money(-tax),
            },
            expected_period=[date, date],
            required_final_balances={SALES_TAX_PAYABLE: money(-tax)},
        ),
        solution_ledger=solution,
        keywords=["sales-tax", "agency-liability", "cash-sale"],
        level="vocational",
        category="tax",
    )


PETTY_CASH = "Assets:PettyCash"
POSTAGE = "Expenses:Postage"
CASH_SHORT = "Expenses:CashShortAndOver"
PETTY_ACCOUNTS = [
    (PETTY_CASH, "Petty cash fund (imprest)"),
    (POSTAGE, "Postage expense"),
    (CASH_SHORT, "Cash short and over"),
]


def petty_cash_replenishment(seed: int) -> TaskInstance:
    """Scenario: replenish an imprest petty cash fund with a small shortage.

    Oracle: expense the receipts, debit the shortage to CashShortAndOver,
    credit bank for fund minus cash on hand. The PettyCash account itself
    is untouched (imprest). Trap: crediting PettyCash or replenishing
    only the receipts and losing the shortage.
    Level V/U/V/U/V/V/V -> vocational (borderline).
    """
    rng = random.Random(seed)
    fund = Decimal(rng.choice([200, 300, 400]))
    supplies = Decimal(rng.randrange(30, 91))
    postage = Decimal(rng.randrange(15, 61))
    short = Decimal(rng.randrange(1, 9))
    spent = supplies + postage + short
    on_hand = fund - spent
    replenish = spent
    opening = Decimal("10000.00")
    initial = _ledger_header(opening, PETTY_ACCOUNTS) + _txn(
        "2026-01-02",
        "Bank",
        "Establish petty cash fund",
        [(PETTY_CASH, fund), (BANK, -fund)],
    )
    doc = (
        "# Petty cash count — 2026-01-31\n\n"
        f"Fund established at USD {money(fund)}. Receipts in the box: office "
        f"supplies USD {money(supplies)}, postage USD {money(postage)}. "
        f"Cash remaining in the box: USD {money(on_hand)}. Replenish the fund "
        "to its imprest amount from checking.\n"
    )
    policy = POLICY + (
        "- Imprest petty cash: the `Assets:PettyCash` balance never changes\n"
        "  on replenishment. Debit each receipt's expense; any shortage "
        "(fund - cash on hand - receipts) is debited to\n"
        "  `Expenses:CashShortAndOver`; credit bank for the replenishment "
        "(fund - cash on hand).\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Petty cash",
        "Replenish petty cash fund",
        [
            ("Expenses:OfficeSupplies", supplies),
            (POSTAGE, postage),
            (CASH_SHORT, short),
            (BANK, -replenish),
        ],
    )
    return TaskInstance(
        task_id="petty-cash-replenishment",
        family="cash-controls",
        title="Replenish petty cash with a cash shortage",
        instruction=(
            "Record the replenishment in `/app/documents/petty_cash_count.md` "
            "in `/app/ledger.beancount`, following `/app/policy.md`. Append "
            "new balanced transactions dated 2026-01-31; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(PETTY_ACCOUNTS),
            "documents/petty_cash_count.md": doc,
        },
        expected=_expected(
            "petty-cash-replenishment",
            "cash-controls",
            seed,
            expected_deltas={
                "Expenses:OfficeSupplies": money(supplies),
                POSTAGE: money(postage),
                CASH_SHORT: money(short),
                BANK: money(-replenish),
            },
            expected_new_transactions=[1, 3],
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={PETTY_CASH: money(fund)},
        ),
        solution_ledger=solution,
        keywords=["petty-cash", "imprest", "cash-shortage"],
        level="vocational",
    )


def small_stock_dividend(seed: int) -> TaskInstance:
    """Scenario: small stock dividend capitalized at market value.

    Oracle: retained earnings debited at market value of the new shares;
    common stock at par; APIC for the excess. Trap: capitalizing at par
    only (the large-stock-dividend rule). Level V/U/V/V/V/V/U.
    """
    rng = random.Random(seed)
    outstanding = rng.randrange(4000, 16001, 500)
    pct = rng.choice([5, 10])
    new_shares = outstanding * pct // 100
    par = Decimal(rng.choice([1, 2]))
    market = par + Decimal(rng.randrange(6, 31))
    total_market = new_shares * market
    par_total = new_shares * par
    retained_open = total_market * rng.randint(3, 5)
    stock_open = Decimal(outstanding) * par
    opening = Decimal("50000.00")
    initial = _ledger_header(opening, EQUITY_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        "Opening equity balances",
        [
            ("Equity:Opening-Balances", retained_open + stock_open),
            (RETAINED, -retained_open),
            (COMMON_STOCK, -stock_open),
        ],
    )
    doc = (
        "# Board resolution — 2026-01-20\n\n"
        f"A {pct}% stock dividend was declared and issued on the {outstanding} "
        f"common shares outstanding ({new_shares} new shares). Par value is "
        f"USD {money(par)} per share; the market price on the declaration date "
        f"was USD {money(market)} per share.\n"
    )
    policy = EQUITY_POLICY + (
        "- A SMALL stock dividend (under 20-25% of shares outstanding) is\n"
        "  capitalized at the market value of the shares issued: debit\n"
        "  retained earnings at market, credit common stock at par and\n"
        "  additional paid-in capital for the excess.\n"
    )
    solution = initial + _txn(
        "2026-01-20",
        "Board",
        f"{pct}% stock dividend issued at market",
        [
            (RETAINED, total_market),
            (COMMON_STOCK, -par_total),
            (APIC, -(total_market - par_total)),
        ],
    )
    return TaskInstance(
        task_id="small-stock-dividend",
        family="equity",
        title="Record a small stock dividend at market value",
        instruction=(
            "Record the stock dividend in `/app/documents/board_resolution.md` "
            "in `/app/ledger.beancount`, following `/app/policy.md`. Append "
            "new balanced transactions dated 2026-01-20; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(EQUITY_ACCOUNTS),
            "documents/board_resolution.md": doc,
        },
        expected=_expected(
            "small-stock-dividend",
            "equity",
            seed,
            expected_deltas={
                RETAINED: money(total_market),
                COMMON_STOCK: money(-par_total),
                APIC: money(-(total_market - par_total)),
            },
            expected_new_transactions=[1, 2],
            expected_period=["2026-01-20", "2026-01-20"],
            required_final_balances={RETAINED: money(-(retained_open - total_market))},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["stock-dividend", "small-stock-dividend", "equity"],
        level="vocational",
    )


def accounting_equation_missing_equity(seed: int) -> TaskInstance:
    """Numeric: ending equity from A = L + E. Trap: beginning equity."""
    rng = random.Random(seed)
    assets = Decimal(rng.randrange(200, 901)) * 1000
    liabilities = Decimal(rng.randrange(80, 401)) * 1000
    d_assets = Decimal(rng.randrange(20, 151)) * 1000
    d_liabilities = -Decimal(rng.randrange(10, 81)) * 1000
    gold = (assets + d_assets) - (liabilities + d_liabilities)
    trap = assets - liabilities
    data = (
        "# Position and changes — year ended 2025-12-31\n\n| Item | USD |\n|---|---:|\n"
        f"| Assets, 2025-01-01 | {money(assets)} |\n"
        f"| Liabilities, 2025-01-01 | {money(liabilities)} |\n"
        f"| Change in assets during the year | +{money(d_assets)} |\n"
        f"| Change in liabilities during the year | {money(d_liabilities)} |\n"
    )
    policy = """# Accounting equation (applies to this task)

- Assets = liabilities + equity at every date. Apply the year's changes
  first, then solve for equity at 2025-12-31.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "equity at year-end (accounting equation)",
        "Using `/app/documents/position_data.md` and `/app/policy.md`, compute "
        "**equity at 2025-12-31** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="accounting-equation-missing-equity",
        family="financial-reporting",
        title="Solve for ending equity with the accounting equation",
        question=question,
        policy=policy,
        data_name="position_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "accounting-equation"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


def current_income_tax_expense(seed: int) -> TaskInstance:
    """Numeric: current tax with permanent differences. Trap: book x rate."""
    rng = random.Random(seed)
    book = Decimal(rng.randrange(200, 801)) * 1000
    exempt = Decimal(rng.randrange(10, 61)) * 1000
    nondeductible = Decimal(rng.randrange(5, 41)) * 1000
    if exempt == nondeductible:  # keep the book-income trap distinct from the gold
        nondeductible += 1000
    rate = rng.choice([Decimal("0.21"), Decimal("0.25")])
    taxable = book - exempt + nondeductible
    gold = taxable * rate
    trap = book * rate
    data = (
        "# Tax computation extracts — year ended 2025-12-31\n\n| Item | USD |\n|---|---:|\n"
        f"| Pretax book income | {money(book)} |\n"
        f"| Tax-exempt interest included in book income | {money(exempt)} |\n"
        f"| Nondeductible fines included in book expenses | {money(nondeductible)} |\n"
        f"| Enacted tax rate | {rate * 100:.0f}% |\n"
        "\nThere are no temporary differences.\n"
    )
    policy = """# Current tax conventions (applies to this task)

- Taxable income = pretax book income - tax-exempt income
  + nondeductible expenses (permanent differences only).
- Current income tax expense = taxable income x the enacted rate.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "current income tax expense",
        "Using `/app/documents/tax_extracts.md` and `/app/policy.md`, compute "
        "**current income tax expense** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="current-income-tax-expense",
        family="income-taxes",
        title="Compute current income tax from permanent differences",
        question=question,
        policy=policy,
        data_name="tax_extracts.md",
        data=data,
        gold=gold,
        seed=seed,
        category="tax",
        keywords=["numeric", "income-tax", "permanent-differences"],
        abs_tolerance="0.01",
        trap_value=money(trap),
        standards=["asc:740", "ias:12"],
    )


def lease_liability_present_value(seed: int) -> TaskInstance:
    """Numeric: initial lease liability from an annuity factor. Trap: sum."""
    rng = random.Random(seed)
    years = rng.choice([3, 4, 5, 6])
    rate = rng.choice([Decimal("0.05"), Decimal("0.06"), Decimal("0.08")])
    factor = _annuity_factor(rate, years)
    payment = Decimal(rng.randrange(10, 61)) * 1000
    gold = (payment * factor).quantize(CENT)
    data = (
        "# Lease terms (lessee)\n\n| Item | Value |\n|---|---:|\n"
        f"| Annual payment, end of each year | USD {money(payment)} |\n"
        f"| Lease term | {years} years |\n"
        f"| Discount rate (rate implicit in the lease) | {rate * 100:.0f}% |\n"
        f"| Annuity factor ({rate * 100:.0f}%, {years} years) | {factor} |\n"
        "\nNo initial direct costs, incentives, or guaranteed residual.\n"
    )
    policy = """# Lessee measurement conventions (applies to this task)

- The lease liability at commencement is the present value of the lease
  payments: annual payment x the annuity factor given in the data
  (use it as stated; do not recompute it).
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "initial lease liability",
        "Using `/app/documents/lease_terms.md` and `/app/policy.md`, compute the "
        "**lease liability at commencement** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="lease-liability-present-value",
        family="leases",
        title="Compute the initial lease liability",
        question=question,
        policy=policy,
        data_name="lease_terms.md",
        data=data,
        gold=gold,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "leases", "present-value"],
        abs_tolerance="0.01",
        trap_value=money(payment * years),
        standards=["asc:842", "ifrs:16"],
    )


def equity_method_carrying_amount(seed: int) -> TaskInstance:
    """Numeric: equity-method carrying amount. Trap: forget dividends."""
    rng = random.Random(seed)
    pct = rng.choice([20, 25, 30, 40])
    cost = Decimal(rng.randrange(100, 601)) * 1000
    investee_income = Decimal(rng.randrange(40, 201)) * 1000
    investee_dividends = Decimal(rng.randrange(10, 81)) * 1000
    share = Decimal(pct) / 100
    gold = cost + share * investee_income - share * investee_dividends
    trap = cost + share * investee_income
    data = (
        "# Associate investment\n\n| Item | Value |\n|---|---:|\n"
        f"| Cost of {pct}% interest, 2025-01-01 | USD {money(cost)} |\n"
        f"| Investee net income, 2025 | USD {money(investee_income)} |\n"
        f"| Investee dividends paid, 2025 | USD {money(investee_dividends)} |\n"
    )
    policy = """# Equity method conventions (applies to this task)

- Carrying amount = cost + share of investee net income - share of
  investee dividends (dividends reduce the investment; they are not
  income under the equity method).
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "equity-method carrying amount",
        "Using `/app/documents/associate_data.md` and `/app/policy.md`, compute "
        "the investment's **carrying amount at 2025-12-31** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="equity-method-carrying-amount",
        family="investments",
        title="Compute an equity-method carrying amount",
        question=question,
        policy=policy,
        data_name="associate_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "equity-method", "associate"],
        abs_tolerance="0.01",
        trap_value=money(trap),
        standards=["asc:323", "ias:28"],
    )


def bond_issue_price(seed: int) -> TaskInstance:
    """Numeric: bond price from stated factors (market above coupon). Trap: par."""
    rng = random.Random(seed)
    face = Decimal(rng.randrange(100, 501)) * 1000
    years = rng.choice([3, 5, 10])
    coupon_rate = rng.choice([Decimal("0.04"), Decimal("0.05"), Decimal("0.06")])
    market = coupon_rate + Decimal("0.02")
    coupon = face * coupon_rate
    annuity = _annuity_factor(market, years)
    pv_factor = (Decimal(1) / (1 + market) ** years).quantize(Decimal("0.0001"))
    gold = (coupon * annuity + face * pv_factor).quantize(CENT)
    data = (
        "# Bond issue terms\n\n| Item | Value |\n|---|---:|\n"
        f"| Face value | USD {money(face)} |\n"
        f"| Coupon rate (annual payments) | {coupon_rate * 100:.0f}% |\n"
        f"| Term | {years} years |\n"
        f"| Market (effective) rate at issue | {market * 100:.0f}% |\n"
        f"| Annuity factor ({market * 100:.0f}%, {years} years) | {annuity} |\n"
        f"| Single-sum factor ({market * 100:.0f}%, {years} years) | {pv_factor} |\n"
    )
    policy = """# Bond pricing conventions (applies to this task)

- Issue price = annual coupon x the annuity factor + face value x the
  single-sum factor, using the factors given in the data as stated
  (do not recompute them). When the market rate exceeds the coupon
  rate the bonds sell at a discount.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "bond issue price",
        "Using `/app/documents/bond_terms.md` and `/app/policy.md`, compute the "
        "**issue price** of the bonds in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="bond-issue-price",
        family="borrowings",
        title="Compute a bond's issue price",
        question=question,
        policy=policy,
        data_name="bond_terms.md",
        data=data,
        gold=gold,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "bonds", "issue-price", "discount"],
        abs_tolerance="0.01",
        trap_value=money(face),
        standards=["asc:835-30", "ifrs:9"],
    )


def partnership_income_allocation(seed: int) -> TaskInstance:
    """Numeric: partner A's share after salaries. Trap: ratio on whole income."""
    rng = random.Random(seed)
    salary_a = Decimal(rng.randrange(20, 81)) * 1000
    salary_b = Decimal(rng.randrange(15, 61)) * 1000
    remainder = Decimal(rng.randrange(40, 201)) * 1000
    pct_a = rng.choice([50, 60, 70])
    if salary_a * (100 - pct_a) == salary_b * pct_a:
        # whole-income-ratio trap would coincide with the gold; nudge B's salary
        salary_b += 1000
    net_income = salary_a + salary_b + remainder
    gold = salary_a + remainder * pct_a / 100
    trap = net_income * pct_a / 100
    data = (
        "# Partnership agreement and results\n\n| Item | Value |\n|---|---:|\n"
        f"| Net income for the year | USD {money(net_income)} |\n"
        f"| Salary allowance, Partner A | USD {money(salary_a)} |\n"
        f"| Salary allowance, Partner B | USD {money(salary_b)} |\n"
        f"| Remaining income split | A {pct_a}% / B {100 - pct_a}% |\n"
    )
    policy = """# Partnership allocation conventions (applies to this task)

- Allocate salary allowances first; split only the REMAINING income by
  the stated ratio. Partner A's total share = A's salary allowance
  + A's percentage of the remainder.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "Partner A's income share",
        "Using `/app/documents/partnership_data.md` and `/app/policy.md`, compute "
        "**Partner A's total share of net income** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="partnership-income-allocation",
        family="partnerships",
        title="Allocate partnership income after salary allowances",
        question=question,
        policy=policy,
        data_name="partnership_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "partnership", "income-allocation"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


def _choice_question(heading: str, body: str, options_md: str, select_note: str) -> str:
    return f"""# Question — {heading}

{body}

{options_md}

## Answer format

Write `/app/answer.json` as a JSON object, for example:

```json
{{"final_answer": {select_note}, "confidence": 80}}
```

`confidence` is your self-assessed probability (0-100) that the answer
is fully correct.
"""


NORMAL_BALANCE_POLICY = """# Normal balance conventions (applies to this task)

- Normal DEBIT balances: assets, expenses, dividends/distributions,
  and contra-revenue accounts.
- Normal CREDIT balances: liabilities, equity (share capital, retained
  earnings), revenue, and contra-asset accounts (accumulated
  depreciation, allowance for doubtful accounts).
"""


def mc_normal_balances(seed: int) -> TaskInstance:
    """Multiple-choice: select every normal-DEBIT-balance account.

    Trap: contra-assets (accumulated depreciation, allowance) look like
    assets but are credit-normal; dividends look like equity but are
    debit-normal. Level: rule stated in policy -> vocational.
    """
    rng = random.Random(seed)
    pool: list[tuple[str, bool]] = [
        ("Cash", True),
        ("Accounts receivable", True),
        ("Supplies", True),
        ("Rent expense", True),
        ("Dividends declared", True),
        ("Sales returns and allowances", True),
        ("Accounts payable", False),
        ("Service revenue", False),
        ("Common stock", False),
        ("Accumulated depreciation", False),
        ("Allowance for doubtful accounts", False),
        ("Unearned revenue", False),
    ]
    rng.shuffle(pool)
    chosen = pool[:8]
    option_ids = ["A", "B", "C", "D", "E", "F", "G", "H"]
    gold = sorted(oid for oid, (_, is_debit) in zip(option_ids, chosen, strict=True) if is_debit)
    options_md = "\n".join(
        f"- {oid}. {name} has a normal DEBIT balance."
        for oid, (name, _) in zip(option_ids, chosen, strict=True)
    )
    question = _choice_question(
        "normal debit balances",
        "Using `/app/policy.md`, select **all** statements that are true. "
        "Incorrect selections are penalized, so select only statements you "
        "believe are correct.",
        options_md,
        '["A", "C"]',
    )
    return TaskInstance(
        task_id="mc-normal-balances",
        family="transaction-classification",
        title="Select the normal-debit-balance accounts",
        instruction=(
            "Answer the multiple-choice question in `/app/question.md` "
            "following `/app/policy.md`. Write your selection to "
            "`/app/answer.json` in the exact format shown in the question."
        ),
        app_files={
            "question.md": question,
            "policy.md": NORMAL_BALANCE_POLICY,
            "chart_of_accounts.md": _chart_md(),
            "answer.example.json": '{\n  "final_answer": ["A"],\n  "confidence": 50\n}\n',
        },
        expected=_expected(
            "mc-normal-balances",
            "transaction-classification",
            seed,
            format="multiple-choice",
            gold=gold,
            options=option_ids,
            expected_deltas={},
            expected_new_transactions=0,
            expected_period=None,
        ),
        solution_ledger="",
        solution_answer={"final_answer": gold, "confidence": 100},
        keywords=["multiple-choice", "normal-balance", "debit-credit"],
        level="vocational",
        format="multiple-choice",
        skill="remembering-understanding",
    )


SPECIAL_JOURNALS = [
    "Sales journal",
    "Purchases journal",
    "Cash receipts journal",
    "Cash payments journal",
    "General journal",
]
SPECIAL_JOURNAL_CASES = [
    ("Sold merchandise on credit to a customer.", "Sales journal"),
    ("Purchased merchandise on credit from a supplier.", "Purchases journal"),
    ("Received cash from a customer paying its account.", "Cash receipts journal"),
    ("Paid a supplier by check for an account balance.", "Cash payments journal"),
    ("Recorded the month-end depreciation adjustment.", "General journal"),
    ("The owner withdrew cash for personal use (paid by check).", "Cash payments journal"),
    ("A customer returned merchandise sold on credit (credit memo issued).", "General journal"),
]


def sc_special_journal_routing(seed: int) -> TaskInstance:
    """Single-choice: route one transaction to its special journal.

    Trap: returns/adjustments look like sales/purchases activity but
    belong in the general journal. Level: policy lists each journal's
    scope -> vocational.
    """
    rng = random.Random(seed)
    narrative, correct = rng.choice(SPECIAL_JOURNAL_CASES)
    journals = SPECIAL_JOURNALS.copy()
    rng.shuffle(journals)
    option_ids = ["A", "B", "C", "D", "E"]
    gold = option_ids[journals.index(correct)]
    options_md = "\n".join(
        f"- {oid}. {name}" for oid, name in zip(option_ids, journals, strict=True)
    )
    policy = """# Special journal conventions (applies to this task)

- Sales journal: sales of merchandise ON CREDIT only.
- Purchases journal: purchases of merchandise ON CREDIT only.
- Cash receipts journal: every receipt of cash.
- Cash payments journal: every payment of cash (including owner draws
  paid in cash or by check).
- General journal: everything else, including returns and allowances
  on credit transactions and all adjusting/closing entries.
"""
    question = _choice_question(
        "special journal routing",
        f"Transaction: **{narrative}**\n\nUsing `/app/policy.md`, in which "
        "journal is this transaction recorded? Select exactly one option.",
        options_md,
        '"B"',
    )
    return TaskInstance(
        task_id="sc-special-journal-routing",
        family="ledger-integrity-reporting",
        title="Route a transaction to its journal",
        instruction=(
            "Answer the single-choice question in `/app/question.md` "
            "following `/app/policy.md`. Write your selection to "
            "`/app/answer.json` in the exact format shown in the question."
        ),
        app_files={
            "question.md": question,
            "policy.md": policy,
            "answer.example.json": '{\n  "final_answer": "A",\n  "confidence": 50\n}\n',
        },
        expected=_expected(
            "sc-special-journal-routing",
            "ledger-integrity-reporting",
            seed,
            format="single-choice",
            gold=gold,
            options=option_ids,
            expected_deltas={},
            expected_new_transactions=0,
            expected_period=None,
        ),
        solution_ledger="",
        solution_answer={"final_answer": gold, "confidence": 100},
        keywords=["single-choice", "special-journals"],
        level="vocational",
        format="single-choice",
        skill="remembering-understanding",
    )


NOTE_PAYABLE = "Liabilities:NotesPayable"
ST_NOTE_ACCOUNTS = [(NOTE_PAYABLE, "Short-term notes payable")]


def short_term_note_payment(seed: int) -> TaskInstance:
    """Scenario: a 30-day note matures and is paid with interest (30/360).

    Oracle: debit note principal + interest expense for one month,
    credit bank maturity value. Trap: expensing the whole payment or
    paying principal only. Level V/U/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    principal = Decimal(rng.randrange(2, 11)) * 12000
    annual = rng.choice([Decimal("0.06"), Decimal("0.09"), Decimal("0.12")])
    interest = principal * annual / 12
    opening = Decimal("5000.00")
    initial = _ledger_header(opening, ST_NOTE_ACCOUNTS) + _txn(
        "2026-01-01",
        "Bank",
        "30-day note signed, cash received",
        [(BANK, principal), (NOTE_PAYABLE, -principal)],
    )
    doc = (
        "# Note payable — due 2026-01-31\n\n"
        f"Principal USD {money(principal)}, signed 2026-01-01, due in 30 days, "
        f"interest {annual * 100:.0f}% a year payable at maturity. The company "
        "paid the note in full from checking on 2026-01-31.\n"
    )
    policy = POLICY + (
        "- Interest on short-term notes uses a 360-day year (30/360): one\n"
        "  month = principal x annual rate x 30/360. At payment, debit the\n"
        "  note for principal and interest expense for the month's interest.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Bank",
        "Note and interest paid at maturity",
        [
            (NOTE_PAYABLE, principal),
            ("Expenses:Interest", interest),
            (BANK, -(principal + interest)),
        ],
    )
    return TaskInstance(
        task_id="short-term-note-payment",
        family="borrowings",
        title="Pay a short-term note and its interest at maturity",
        instruction=(
            "Record the payment in `/app/documents/note_payable.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated 2026-01-31; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(ST_NOTE_ACCOUNTS),
            "documents/note_payable.md": doc,
        },
        expected=_expected(
            "short-term-note-payment",
            "borrowings",
            seed,
            expected_deltas={
                NOTE_PAYABLE: money(principal),
                "Expenses:Interest": money(interest),
                BANK: money(-(principal + interest)),
            },
            expected_new_transactions=[1, 2],
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={NOTE_PAYABLE: "0.00"},
        ),
        solution_ledger=solution,
        keywords=["notes-payable", "interest", "maturity"],
        level="vocational",
    )


CARD_FEE = "Expenses:CreditCardFees"
CARD_ACCOUNTS = [(CARD_FEE, "Credit card processing fees")]


def credit_card_sale_fee(seed: int) -> TaskInstance:
    """Scenario: card sale settled net of the processor's fee.

    Oracle: sales at gross; bank at the net deposit; fee as expense.
    Trap: recording the net deposit as the sales amount.
    Level V/U/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    gross = Decimal(rng.randrange(30, 161)) * 100
    pct = rng.choice([Decimal("0.02"), Decimal("0.03"), Decimal("0.04")])
    fee = (gross * pct).quantize(CENT)
    day = rng.randint(4, 24)
    date = f"2026-01-{day:02d}"
    opening = Decimal("10000.00")
    initial = _ledger_header(opening, CARD_ACCOUNTS)
    doc = (
        f"# Card settlement — {date}\n\n"
        f"Customers bought merchandise for USD {money(gross)} by credit card. "
        f"The processor withheld a {pct * 100:.0f}% fee (USD {money(fee)}) and "
        f"deposited USD {money(gross - fee)} into checking the same day.\n"
    )
    policy = POLICY + (
        "- Credit-card sales are recorded at the gross selling price; the\n"
        "  processor's fee is a selling expense (`Expenses:CreditCardFees`),\n"
        "  never a reduction of sales.\n"
    )
    solution = initial + _txn(
        date,
        "Card processor",
        "Credit-card sale net of processing fee",
        [(BANK, gross - fee), (CARD_FEE, fee), ("Income:Sales", -gross)],
    )
    return TaskInstance(
        task_id="credit-card-sale-fee",
        family="transaction-classification",
        title="Record a credit-card sale net of its fee",
        instruction=(
            "Record the settlement in `/app/documents/card_settlement.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md`. Append new "
            f"balanced transactions dated {date}; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(CARD_ACCOUNTS),
            "documents/card_settlement.md": doc,
        },
        expected=_expected(
            "credit-card-sale-fee",
            "transaction-classification",
            seed,
            expected_deltas={
                BANK: money(gross - fee),
                CARD_FEE: money(fee),
                "Income:Sales": money(-gross),
            },
            expected_period=[date, date],
            required_final_balances={BANK: money(opening + gross - fee)},
        ),
        solution_ledger=solution,
        keywords=["credit-card-sale", "processing-fee", "gross-sales"],
        level="vocational",
    )


PATENT = "Assets:Patent"
ACC_AMORT = "Assets:AccumulatedAmortization"
AMORTIZATION = "Expenses:Amortization"
INTANGIBLE_ACCOUNTS = [
    (PATENT, "Patent at cost"),
    (ACC_AMORT, "Accumulated amortization (contra-asset; credit balance)"),
    (AMORTIZATION, "Amortization expense on intangible assets"),
]


def patent_amortization(seed: int) -> TaskInstance:
    """Scenario: first month's patent amortization over its useful life.

    Oracle: cost / (useful-life years x 12); the longer legal life is not
    used. Trap: amortizing over the legal life. Level V/U/V/U/V/V/U.
    """
    rng = random.Random(seed)
    useful = rng.choice([5, 8, 10])
    legal = useful + rng.choice([5, 10])
    monthly = Decimal(rng.randrange(50, 301))
    cost = monthly * 12 * useful
    opening = cost + Decimal("10000.00")
    initial = _ledger_header(opening, INTANGIBLE_ACCOUNTS) + _txn(
        "2026-01-02",
        "Seller",
        "Patent acquired",
        [(PATENT, cost), (BANK, -cost)],
    )
    doc = (
        "# Patent acquisition — 2026-01-02\n\n"
        f"Cost: USD {money(cost)}. Legal life remaining: {legal} years. "
        f"Expected useful (economic) life: {useful} years. No residual value.\n"
    )
    policy = POLICY + (
        "- Finite-lived intangibles are amortized straight-line over the\n"
        "  SHORTER of legal and useful life, monthly from the acquisition\n"
        "  month (full month in that month), to accumulated amortization.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Amortization",
        "January patent amortization",
        [(AMORTIZATION, monthly), (ACC_AMORT, -monthly)],
    )
    return TaskInstance(
        task_id="patent-amortization",
        family="intangible-assets",
        title="Record the first month of patent amortization",
        instruction=(
            "Record January amortization in `/app/ledger.beancount`, using "
            "`/app/documents/patent.md` and `/app/policy.md`. Append exactly "
            "one balanced transaction dated 2026-01-31; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(INTANGIBLE_ACCOUNTS),
            "documents/patent.md": doc,
        },
        expected=_expected(
            "patent-amortization",
            "intangible-assets",
            seed,
            expected_deltas={AMORTIZATION: money(monthly), ACC_AMORT: money(-monthly)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={PATENT: money(cost)},
        ),
        solution_ledger=solution,
        keywords=["intangible-assets", "amortization", "patent"],
        level="vocational",
        standards=["asc:350", "ias:38"],
    )


LOSS_CONTINGENCY = "Expenses:LitigationLoss"
CONTINGENT_LIABILITY = "Liabilities:EstimatedLitigationLiability"
CONTINGENCY_ACCOUNTS = [
    (LOSS_CONTINGENCY, "Loss from litigation contingency"),
    (CONTINGENT_LIABILITY, "Estimated liability for litigation claims"),
]


def loss_contingency_accrual(seed: int) -> TaskInstance:
    """Scenario: two lawsuits at January close; only one meets the criteria.

    Oracle: accrue only the probable-and-estimable claim; the remote
    claim is not recorded. Trap: accruing both claims.
    Level V/U/V/U/U/V/U -> vocational (borderline).
    """
    rng = random.Random(seed)
    probable = Decimal(rng.randrange(40, 201)) * 100
    remote = Decimal(rng.randrange(100, 501)) * 100
    opening = Decimal("50000.00")
    initial = _ledger_header(opening, CONTINGENCY_ACCOUNTS)
    doc = (
        "# Litigation status — 2026-01-31 (counsel's assessment)\n\n"
        f"- Claim 1 (supplier dispute): an unfavorable outcome is PROBABLE and "
        f"the loss is reasonably estimable at USD {money(probable)}.\n"
        f"- Claim 2 (customer claim): an unfavorable outcome is REMOTE; the "
        f"amount claimed is USD {money(remote)}.\n"
    )
    policy = POLICY + (
        "- A loss contingency is accrued (expense and liability) only when a\n"
        "  loss is probable AND reasonably estimable. Remote contingencies\n"
        "  are not recorded; reasonably possible ones are disclosed, not accrued.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Counsel",
        "Accrue probable litigation loss (Claim 1)",
        [(LOSS_CONTINGENCY, probable), (CONTINGENT_LIABILITY, -probable)],
    )
    return TaskInstance(
        task_id="loss-contingency-accrual",
        family="provisions-contingencies",
        title="Accrue the loss contingency that meets the criteria",
        instruction=(
            "Record the January entries required by "
            "`/app/documents/litigation_status.md` in `/app/ledger.beancount`, "
            "following `/app/policy.md`. Append new balanced transactions "
            "dated 2026-01-31; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(CONTINGENCY_ACCOUNTS),
            "documents/litigation_status.md": doc,
        },
        expected=_expected(
            "loss-contingency-accrual",
            "provisions-contingencies",
            seed,
            expected_deltas={
                LOSS_CONTINGENCY: money(probable),
                CONTINGENT_LIABILITY: money(-probable),
            },
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={CONTINGENT_LIABILITY: money(-probable)},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["loss-contingency", "probable-estimable", "accrual"],
        level="vocational",
        standards=["asc:450", "ias:37"],
    )


BOND_PREMIUM = "Liabilities:PremiumOnBondsPayable"
BOND_ISSUE_ACCOUNTS = [
    (BONDS, "Bonds payable at face value"),
    (BOND_PREMIUM, "Unamortized premium on bonds payable (credit balance)"),
]


def bond_issued_at_premium(seed: int) -> TaskInstance:
    """Scenario: bonds issued above face (coupon above market) on Jan 1.

    Oracle: bank at proceeds; bonds payable at face; premium for excess.
    Trap: recording the liability at proceeds (no premium split).
    Level V/U/V/V/V/V/U -> vocational.
    """
    rng = random.Random(seed)
    face = Decimal(rng.randrange(5, 21)) * 12000
    premium = (face * Decimal(rng.randrange(15, 51)) / 1000).quantize(Decimal("1"))
    proceeds = face + premium
    opening = Decimal("5000.00")
    initial = _ledger_header(opening, BOND_ISSUE_ACCOUNTS)
    doc = (
        "# Bond issuance — 2026-01-01\n\n"
        f"Face value USD {money(face)}, 8% coupon (market rate 6%), 5-year term. "
        f"The bonds sold for USD {money(proceeds)}, received in full into "
        "checking on the issue date.\n"
    )
    policy = POLICY + (
        "- Bonds payable are recorded at face value. Proceeds above face are\n"
        "  a premium (`Liabilities:PremiumOnBondsPayable`), amortized over\n"
        "  the bond term.\n"
    )
    solution = initial + _txn(
        "2026-01-01",
        "Underwriter",
        "Bonds issued at a premium",
        [(BANK, proceeds), (BONDS, -face), (BOND_PREMIUM, -premium)],
    )
    return TaskInstance(
        task_id="bond-issued-at-premium",
        family="borrowings",
        title="Record bonds issued at a premium",
        instruction=(
            "Record the issuance in `/app/documents/bond_issuance.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated 2026-01-01; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(BOND_ISSUE_ACCOUNTS),
            "documents/bond_issuance.md": doc,
        },
        expected=_expected(
            "bond-issued-at-premium",
            "borrowings",
            seed,
            expected_deltas={
                BANK: money(proceeds),
                BONDS: money(-face),
                BOND_PREMIUM: money(-premium),
            },
            expected_period=["2026-01-01", "2026-01-01"],
            required_final_balances={BONDS: money(-face)},
        ),
        solution_ledger=solution,
        keywords=["bonds-payable", "premium", "issuance"],
        level="vocational",
        standards=["asc:835-30", "ifrs:9"],
    )


DRAWING = "Equity:OwnerDrawing"
DRAWING_ACCOUNTS = [
    (OWNER_CAPITAL, "Owner capital contributed"),
    (DRAWING, "Owner withdrawals for personal use (contra-equity)"),
]


def closing_drawing_account(seed: int) -> TaskInstance:
    """Scenario: close the owner's drawing account at January 31.

    Oracle: OwnerCapital debited, Drawing credited (drawings never pass
    through income summary). Trap: closing drawings to income summary
    (treating them as an expense). Level V/V/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    capital = Decimal(rng.randrange(200, 601)) * 100
    draw1 = Decimal(rng.randrange(10, 41)) * 50
    draw2 = Decimal(rng.randrange(10, 41)) * 50
    total_drawn = draw1 + draw2
    closing_accounts = DRAWING_ACCOUNTS + [
        (INCOME_SUMMARY, "Income summary (temporary closing account)")
    ]
    opening = Decimal("10000.00")
    initial = (
        _ledger_header(opening, closing_accounts)
        + _txn(
            "2026-01-01",
            "Opening",
            "Opening owner capital",
            [("Equity:Opening-Balances", capital), (OWNER_CAPITAL, -capital)],
        )
        + _txn("2026-01-10", "Owner", "Cash withdrawn by owner", [(DRAWING, draw1), (BANK, -draw1)])
        + _txn("2026-01-24", "Owner", "Cash withdrawn by owner", [(DRAWING, draw2), (BANK, -draw2)])
    )
    doc = (
        "# Month-end closing instruction\n\n"
        f"Owner withdrawals in January total USD {money(total_drawn)} (two cash "
        "draws, already recorded in `Equity:OwnerDrawing`). Close the drawing "
        "account as part of the January closing process.\n"
    )
    policy = POLICY + (
        "- The drawing account is closed directly to the owner's capital\n"
        "  account at period-end. Drawings are distributions, never an\n"
        "  expense, and never pass through income summary.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Closing",
        "Close drawing account to owner capital",
        [(OWNER_CAPITAL, total_drawn), (DRAWING, -total_drawn)],
    )
    return TaskInstance(
        task_id="closing-drawing-account",
        family="equity",
        title="Close the owner drawing account",
        instruction=(
            "Record the closing entry described in "
            "`/app/documents/closing_instruction.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md`. Append "
            "exactly one balanced transaction dated 2026-01-31; do not edit "
            "existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(closing_accounts),
            "documents/closing_instruction.md": doc,
        },
        expected=_expected(
            "closing-drawing-account",
            "equity",
            seed,
            expected_deltas={OWNER_CAPITAL: money(total_drawn), DRAWING: money(-total_drawn)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={
                DRAWING: "0.00",
                OWNER_CAPITAL: money(-(capital - total_drawn)),
            },
        ),
        solution_ledger=solution,
        keywords=["closing-entries", "drawing-account", "owner-capital"],
        level="vocational",
    )


TRADING = "Assets:TradingSecurities"
UNREALIZED = "Income:UnrealizedGainLoss"
TRADING_ACCOUNTS = [
    (TRADING, "Trading securities at fair value"),
    (UNREALIZED, "Unrealized gain (credit) or loss on trading securities"),
]


def trading_securities_fair_value(seed: int) -> TaskInstance:
    """Scenario: mark trading securities up to fair value at month-end.

    Oracle: debit the securities, credit unrealized gain in income for
    shares x (fair value - cost). Trap: leaving them at cost, or routing
    the gain outside income. Level V/U/V/V/V/V/U -> vocational.
    """
    rng = random.Random(seed)
    shares = rng.randrange(100, 901, 25)
    cost_each = Decimal(rng.randrange(1500, 5001, 25)) / 100
    uplift = Decimal(rng.randrange(100, 801, 25)) / 100
    fair_each = cost_each + uplift
    cost_total = shares * cost_each
    gain = shares * uplift
    opening = cost_total + Decimal("10000.00")
    initial = _ledger_header(opening, TRADING_ACCOUNTS) + _txn(
        "2026-01-05",
        "Broker",
        f"Bought {shares} shares as trading securities",
        [(TRADING, cost_total), (BANK, -cost_total)],
    )
    doc = (
        "# Month-end quotes — 2026-01-31\n\n"
        f"The {shares} shares bought on 2026-01-05 at USD {money(cost_each)} each "
        f"are quoted at USD {money(fair_each)} each at 2026-01-31. The shares are "
        "held for trading (bought to sell at a short-term profit).\n"
    )
    policy = POLICY + (
        "- Trading securities are carried at fair value; unrealized gains and\n"
        "  losses are recognized in current income "
        "(`Income:UnrealizedGainLoss`) at each month-end.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Broker",
        "Mark trading securities to fair value",
        [(TRADING, gain), (UNREALIZED, -gain)],
    )
    return TaskInstance(
        task_id="trading-securities-fair-value",
        family="investments",
        title="Mark trading securities to fair value",
        instruction=(
            "Record the month-end adjustment in "
            "`/app/documents/month_end_quotes.md` in `/app/ledger.beancount`, "
            "following `/app/policy.md`. Append exactly one balanced "
            "transaction dated 2026-01-31; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(TRADING_ACCOUNTS),
            "documents/month_end_quotes.md": doc,
        },
        expected=_expected(
            "trading-securities-fair-value",
            "investments",
            seed,
            expected_deltas={TRADING: money(gain), UNREALIZED: money(-gain)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={TRADING: money(cost_total + gain)},
        ),
        solution_ledger=solution,
        keywords=["trading-securities", "fair-value", "unrealized-gain"],
        level="vocational",
        standards=["asc:321", "ifrs:9"],
    )


def materials_quantity_variance(seed: int) -> TaskInstance:
    """Numeric: materials quantity variance. Trap: quantity purchased."""
    rng = random.Random(seed)
    standard_price = Decimal(rng.randrange(300, 1201, 25)) / 100
    sq_per_unit = rng.choice([2, 3, 4])
    output = rng.randrange(800, 3001, 100)
    allowed = sq_per_unit * output
    excess = rng.randrange(50, 601, 50)
    used = allowed + excess
    purchased = used + rng.randrange(100, 801, 100)
    gold = (used - allowed) * standard_price
    trap = (purchased - allowed) * standard_price
    data = (
        "# Materials usage — January 2026\n\n| Item | Value |\n|---|---:|\n"
        f"| Standard price | USD {money(standard_price)} per unit of material |\n"
        f"| Standard quantity | {sq_per_unit} units of material per finished unit |\n"
        f"| Finished units produced | {output} |\n"
        f"| Material actually used | {used} units |\n"
        f"| Material purchased | {purchased} units |\n"
    )
    policy = """# Standard costing conventions (applies to this task)

- Materials quantity (efficiency) variance = (actual quantity USED
  - standard quantity allowed for actual output) x standard price.
  Standard quantity allowed = standard per finished unit x units made.
  A positive answer is unfavorable.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "materials quantity variance",
        "Using `/app/documents/materials_usage.md` and `/app/policy.md`, compute "
        "the **materials quantity variance** in USD (positive = unfavorable).",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="materials-quantity-variance",
        family="standard-costing",
        title="Compute the materials quantity variance",
        question=question,
        policy=policy,
        data_name="materials_usage.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "standard-costing", "quantity-variance"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


def cost_of_goods_manufactured(seed: int) -> TaskInstance:
    """Numeric: COGM schedule total. Trap: total manufacturing cost (no WIP adj)."""
    rng = random.Random(seed)

    def amt(lo, hi):
        return Decimal(rng.randrange(lo, hi)) * 100

    dm, dl, oh = amt(150, 501), amt(100, 401), amt(80, 301)
    wip_begin, wip_end = amt(30, 121), amt(20, 101)
    gold = dm + dl + oh + wip_begin - wip_end
    trap = dm + dl + oh
    data = (
        "# Manufacturing data — January 2026\n\n| Item | USD |\n|---|---:|\n"
        f"| Direct materials used | {money(dm)} |\n"
        f"| Direct labor | {money(dl)} |\n"
        f"| Manufacturing overhead applied | {money(oh)} |\n"
        f"| Work in process, 2026-01-01 | {money(wip_begin)} |\n"
        f"| Work in process, 2026-01-31 | {money(wip_end)} |\n"
    )
    policy = """# Cost of goods manufactured (applies to this task)

- COGM = direct materials used + direct labor + manufacturing overhead
  applied + beginning work in process - ending work in process.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "cost of goods manufactured",
        "Using `/app/documents/manufacturing_data.md` and `/app/policy.md`, compute "
        "**cost of goods manufactured** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="cost-of-goods-manufactured",
        family="job-order-costing",
        title="Compute cost of goods manufactured",
        question=question,
        policy=policy,
        data_name="manufacturing_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "cogm", "work-in-process"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


def payback_period_years(seed: int) -> TaskInstance:
    """Numeric: payback in years on cash inflow. Trap: using net income."""
    rng = random.Random(seed)
    half_years = rng.randrange(5, 13)  # payback = half_years / 2 years
    inflow = Decimal(rng.randrange(10, 51)) * 2000
    initial = inflow * half_years / 2
    depreciation = (inflow / 4).quantize(CENT)
    net_income = inflow - depreciation
    gold = (Decimal(half_years) / 2).quantize(Decimal("0.01"))
    trap = (initial / net_income).quantize(Decimal("0.0001"))
    data = (
        "# Project screening data\n\n| Item | Value |\n|---|---:|\n"
        f"| Initial investment | USD {money(initial)} |\n"
        f"| Annual net cash inflow (even) | USD {money(inflow)} |\n"
        f"| Annual depreciation on the project asset | USD {money(depreciation)} |\n"
        f"| Annual net income | USD {money(net_income)} |\n"
    )
    policy = """# Payback conventions (applies to this task)

- Payback period (even cash inflows) = initial investment / annual NET
  CASH inflow. Payback is a cash measure: depreciation (a non-cash
  charge already inside net income) is not deducted.
- Answer in years (for example 3.50) in `/app/answer.json`.
"""
    question = _numeric_question(
        "payback period",
        "Using `/app/documents/project_screening.md` and `/app/policy.md`, compute "
        "the **payback period in years**.",
        "the number of years",
    )
    return _numeric_instance(
        task_id="payback-period-years",
        family="capital-budgeting",
        title="Compute the payback period",
        question=question,
        policy=policy,
        data_name="project_screening.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "payback", "capital-budgeting"],
        abs_tolerance="0.01",
        trap_value=format(trap, "f"),
    )


def multiproduct_breakeven_units(seed: int) -> TaskInstance:
    """Numeric: break-even with a sales mix. Trap: simple average margin."""
    rng = random.Random(seed)
    breakeven = rng.randrange(500, 2501, 50)
    cm_a = Decimal(rng.randrange(500, 2001, 50)) / 100
    cm_b = cm_a + Decimal(rng.randrange(250, 1501, 50)) / 100
    mix_a = rng.choice([40, 60, 80])
    wacm = (cm_a * mix_a + cm_b * (100 - mix_a)) / 100
    fixed = (wacm * breakeven).quantize(CENT)
    simple = (cm_a + cm_b) / 2
    trap = int((fixed / simple).to_integral_value(rounding="ROUND_HALF_UP"))
    if trap == breakeven:
        trap += 50
    data = (
        "# Two-product data (monthly)\n\n| Item | Product A | Product B |\n|---|---:|---:|\n"
        f"| Contribution margin per unit | USD {money(cm_a)} | USD {money(cm_b)} |\n"
        f"| Share of units sold (sales mix) | {mix_a}% | {100 - mix_a}% |\n\n"
        f"Total fixed costs: USD {money(fixed)} a month. The sales mix is constant.\n"
    )
    policy = """# Multi-product CVP conventions (applies to this task)

- Weighted-average contribution margin = sum over products of
  (contribution margin per unit x sales-mix share).
- Break-even in TOTAL units = fixed costs / weighted-average margin.
- Answer with the total unit count in `/app/answer.json`.
"""
    question = _numeric_question(
        "multi-product break-even units",
        "Using `/app/documents/two_product_data.md` and `/app/policy.md`, compute "
        "the monthly **break-even volume in total units**.",
        "the unit count",
    )
    return _numeric_instance(
        task_id="multiproduct-breakeven-units",
        family="cost-volume-profit",
        title="Compute break-even units for a two-product mix",
        question=question,
        policy=policy,
        data_name="two_product_data.md",
        data=data,
        gold=Decimal(breakeven),
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "cvp", "sales-mix", "weighted-average-margin"],
        abs_tolerance="1",
        trap_value=str(trap),
    )


def total_current_liabilities(seed: int) -> TaskInstance:
    """Numeric: total current liabilities slice. Trap: including long-term note."""
    rng = random.Random(seed)

    def amt(lo, hi):
        return Decimal(rng.randrange(lo, hi)) * 100

    ap = amt(80, 301)
    accrued = amt(20, 101)
    unearned = amt(15, 91)
    current_portion = amt(10, 61)
    tax_payable = amt(10, 71)
    lt_note = amt(200, 601)
    gold = ap + accrued + unearned + current_portion + tax_payable
    trap = gold + lt_note
    data = (
        "# Liability balances — 2026-01-31\n\n| Item | USD |\n|---|---:|\n"
        f"| Accounts payable (due within 30 days) | {money(ap)} |\n"
        f"| Accrued wages payable | {money(accrued)} |\n"
        f"| Unearned revenue (services due within 6 months) | {money(unearned)} |\n"
        f"| Current portion of long-term debt | {money(current_portion)} |\n"
        f"| Income taxes payable | {money(tax_payable)} |\n"
        f"| Long-term note payable (due 2029, excluding current portion) | {money(lt_note)} |\n"
    )
    policy = """# Current liability conventions (applies to this task)

- Current liabilities are obligations due within one year, including
  the current portion of long-term debt and unearned revenue for
  services due within the year. The non-current remainder of long-term
  debt is excluded.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "total current liabilities",
        "Using `/app/documents/liability_balances.md` and `/app/policy.md`, compute "
        "**total current liabilities** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="total-current-liabilities",
        family="financial-reporting",
        title="Compute total current liabilities",
        question=question,
        policy=policy,
        data_name="liability_balances.md",
        data=data,
        gold=gold,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "current-liabilities", "classified-balance-sheet"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


CASH_FLOW_SECTIONS = [
    "Operating activities",
    "Investing activities",
    "Financing activities",
    "Not reported in the statement of cash flows (non-cash disclosure only)",
]
CASH_FLOW_CASES = [
    ("Cash paid to suppliers for inventory.", "Operating activities"),
    ("Cash received from customers.", "Operating activities"),
    ("Cash paid to purchase manufacturing equipment.", "Investing activities"),
    ("Cash received from selling a parcel of land.", "Investing activities"),
    ("Cash dividends paid to shareholders.", "Financing activities"),
    ("Cash received from issuing new shares.", "Financing activities"),
    ("Repayment of the principal on a bank loan in cash.", "Financing activities"),
    (
        "Equipment acquired by signing a note payable (no cash moved).",
        "Not reported in the statement of cash flows (non-cash disclosure only)",
    ),
]


def sc_cash_flow_classification(seed: int) -> TaskInstance:
    """Single-choice: classify one cash flow by section.

    Trap: dividends paid look like an operating distribution of profit
    but are financing; non-cash exchanges are not investing outflows.
    Level: policy gives the section definitions -> vocational.
    """
    rng = random.Random(seed)
    narrative, correct = rng.choice(CASH_FLOW_CASES)
    sections = CASH_FLOW_SECTIONS.copy()
    rng.shuffle(sections)
    option_ids = ["A", "B", "C", "D"]
    gold = option_ids[sections.index(correct)]
    options_md = "\n".join(
        f"- {oid}. {name}" for oid, name in zip(option_ids, sections, strict=True)
    )
    policy = """# Cash flow classification (applies to this task)

- Operating: cash from the main revenue-producing activities (receipts
  from customers, payments to suppliers and employees).
- Investing: cash to buy or from selling long-term assets.
- Financing: cash from/to owners and lenders as capital providers
  (share issues, dividends PAID, borrowing and repaying principal).
- Transactions with no cash movement are not reported in the statement
  body (non-cash disclosure only).
"""
    question = _choice_question(
        "cash flow section classification",
        f"Transaction: **{narrative}**\n\nUsing `/app/policy.md`, in which "
        "section is it reported? Select exactly one option.",
        options_md,
        '"B"',
    )
    return TaskInstance(
        task_id="sc-cash-flow-classification",
        family="cash-flow-statement",
        title="Classify a transaction by cash flow section",
        instruction=(
            "Answer the single-choice question in `/app/question.md` "
            "following `/app/policy.md`. Write your selection to "
            "`/app/answer.json` in the exact format shown in the question."
        ),
        app_files={
            "question.md": question,
            "policy.md": policy,
            "answer.example.json": '{\n  "final_answer": "A",\n  "confidence": 50\n}\n',
        },
        expected=_expected(
            "sc-cash-flow-classification",
            "cash-flow-statement",
            seed,
            format="single-choice",
            gold=gold,
            options=option_ids,
            expected_deltas={},
            expected_new_transactions=0,
            expected_period=None,
        ),
        solution_ledger="",
        solution_answer={"final_answer": gold, "confidence": 100},
        keywords=["single-choice", "cash-flow", "classification"],
        level="vocational",
        format="single-choice",
        skill="remembering-understanding",
        standards=["asc:230", "ias:7"],
    )


def inventory_shrinkage_adjustment(seed: int) -> TaskInstance:
    """Scenario: physical count below perpetual records at month-end.

    Oracle: shortage units x unit cost debited to cost of goods sold,
    credited to inventory. Trap: valuing the shortage at selling price.
    Level V/U/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    item = rng.choice(["ceramic planters", "trail backpacks", "steel water bottles"])
    recorded = rng.randrange(120, 401, 10)
    short = rng.randrange(3, 21)
    counted = recorded - short
    unit_cost = Decimal(rng.randrange(800, 3001, 25)) / 100
    price = (unit_cost * Decimal("1.8")).quantize(CENT)
    amount = short * unit_cost
    opening = Decimal("20000.00")
    initial = _ledger_header(opening, INVENTORY_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        f"Opening inventory per records: {recorded} {item}",
        [(INVENTORY, recorded * unit_cost), ("Equity:Opening-Balances", -recorded * unit_cost)],
    )
    doc = (
        f"# Inventory count — {item}, 2026-01-31\n\n"
        f"Perpetual records: {recorded} units at USD {money(unit_cost)} cost "
        f"(selling price USD {money(price)}).\n"
        f"Physical count: {counted} units. The difference is shrinkage "
        "(spoilage/theft); no other explanation was found.\n"
    )
    policy = POLICY + (
        "- Inventory shrinkage found at a count is charged to cost of goods\n"
        "  sold at the units' recorded COST (never selling price), crediting\n"
        "  inventory so the account agrees to the count.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Count",
        "Record inventory shrinkage to count",
        [(COST_OF_SALES, amount), (INVENTORY, -amount)],
    )
    return TaskInstance(
        task_id="inventory-shrinkage-adjustment",
        family="inventory",
        title="Adjust inventory for shrinkage found at the count",
        instruction=(
            "Record the shrinkage in `/app/documents/inventory_count.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md`. Append "
            "exactly one balanced transaction dated 2026-01-31; do not edit "
            "existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(INVENTORY_ACCOUNTS),
            "documents/inventory_count.md": doc,
        },
        expected=_expected(
            "inventory-shrinkage-adjustment",
            "inventory",
            seed,
            expected_deltas={COST_OF_SALES: money(amount), INVENTORY: money(-amount)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={INVENTORY: money(counted * unit_cost)},
        ),
        solution_ledger=solution,
        keywords=["inventory", "shrinkage", "perpetual-count"],
        level="vocational",
    )


PURCHASE_RETURN_ACCOUNTS = [
    (AP, "Trade payables (supplier invoices on credit)"),
    (INVENTORY, "Inventory of goods held for sale (perpetual)"),
]


def purchase_return_perpetual(seed: int) -> TaskInstance:
    """Scenario: return defective merchandise bought on credit (perpetual).

    Oracle: debit AP, credit inventory at purchase cost of returned units.
    Trap: crediting inventory at the goods' selling price.
    Level V/U/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    supplier = rng.choice(["Apex Components", "Bolt & Nut Supply", "Crestline Materials"])
    bought = rng.randrange(40, 121, 5)
    returned = rng.randrange(3, 16)
    unit_cost = Decimal(rng.randrange(1000, 3501, 25)) / 100
    price = (unit_cost * Decimal("1.7")).quantize(CENT)
    amount = returned * unit_cost
    opening = Decimal("20000.00")
    initial = _ledger_header(opening, PURCHASE_RETURN_ACCOUNTS) + _txn(
        "2026-01-08",
        supplier,
        f"Merchandise purchased on credit ({bought} units)",
        [(INVENTORY, bought * unit_cost), (AP, -bought * unit_cost)],
    )
    doc = (
        f"# Return memo — {supplier}, 2026-01-14\n\n"
        f"{returned} of the {bought} units bought on 2026-01-08 were defective "
        f"and returned for full credit at their purchase cost of "
        f"USD {money(unit_cost)} each (they would have sold for "
        f"USD {money(price)} each). Nothing has been paid yet.\n"
    )
    solution = initial + _txn(
        "2026-01-14",
        supplier,
        "Defective merchandise returned for credit",
        [(AP, amount), (INVENTORY, -amount)],
    )
    return TaskInstance(
        task_id="purchase-return-perpetual",
        family="inventory",
        title="Record a purchase return under perpetual inventory",
        instruction=(
            "Record the return in `/app/documents/return_memo.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated 2026-01-14; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": MERCH_POLICY,
            "chart_of_accounts.md": _chart_md(PURCHASE_RETURN_ACCOUNTS),
            "documents/return_memo.md": doc,
        },
        expected=_expected(
            "purchase-return-perpetual",
            "inventory",
            seed,
            expected_deltas={AP: money(amount), INVENTORY: money(-amount)},
            expected_period=["2026-01-14", "2026-01-14"],
            required_final_balances={AP: money(-(bought - returned) * unit_cost)},
        ),
        solution_ledger=solution,
        keywords=["purchase-return", "perpetual-inventory", "payables"],
        level="vocational",
    )


OVERHEAD_DISPO_ACCOUNTS = [
    (WIP, "Work in process inventory (job costs)"),
    (MFG_OVERHEAD, "Manufacturing overhead control (actual debited, applied credited)"),
    (COST_OF_SALES, "Cost of goods sold"),
]


def overhead_variance_disposition(seed: int) -> TaskInstance:
    """Scenario: close a small underapplied overhead balance to COGS.

    Oracle: underapplied (actual - applied, debit balance) is debited to
    cost of goods sold. Trap: treating the balance as overapplied
    (reversed entry). Level V/U/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    applied = Decimal(rng.randrange(100, 401)) * 50
    under = Decimal(rng.randrange(8, 61)) * 25
    actual = applied + under
    opening = Decimal("60000.00")
    initial = (
        _ledger_header(opening, OVERHEAD_DISPO_ACCOUNTS)
        + _txn(
            "2026-01-20",
            "Factory",
            "Actual manufacturing overhead incurred",
            [(MFG_OVERHEAD, actual), (BANK, -actual)],
        )
        + _txn(
            "2026-01-25",
            "Jobs",
            "Overhead applied to jobs in January",
            [(WIP, applied), (MFG_OVERHEAD, -applied)],
        )
    )
    doc = (
        "# Overhead summary — January 2026\n\n"
        f"Actual overhead incurred: USD {money(actual)}. Overhead applied to "
        f"jobs at the predetermined rate: USD {money(applied)}. The balance "
        "is small relative to cost of goods sold.\n"
    )
    policy = POLICY + (
        "- A small under- or overapplied overhead balance at month-end is\n"
        "  closed entirely to cost of goods sold: UNDERapplied (debit\n"
        "  balance) increases cost of goods sold; OVERapplied decreases it.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Overhead",
        "Close underapplied overhead to cost of goods sold",
        [(COST_OF_SALES, under), (MFG_OVERHEAD, -under)],
    )
    return TaskInstance(
        task_id="overhead-variance-disposition",
        family="job-order-costing",
        title="Close underapplied overhead to cost of goods sold",
        instruction=(
            "Record the disposition in `/app/documents/overhead_summary.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md`. Append "
            "exactly one balanced transaction dated 2026-01-31; do not edit "
            "existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(OVERHEAD_DISPO_ACCOUNTS),
            "documents/overhead_summary.md": doc,
        },
        expected=_expected(
            "overhead-variance-disposition",
            "job-order-costing",
            seed,
            expected_deltas={COST_OF_SALES: money(under), MFG_OVERHEAD: money(-under)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={MFG_OVERHEAD: "0.00"},
        ),
        solution_ledger=solution,
        keywords=["overhead-variance", "underapplied", "disposition"],
        level="vocational",
        category="management-accounting",
    )


UNEARNED_ACCOUNTS = [
    (DEFERRED, "Cash received for services not yet delivered"),
    (SERVICES, "Service revenue (recognized as delivered)"),
]


def unearned_revenue_release(seed: int) -> TaskInstance:
    """Scenario: one month earned on a 4-month advance service contract.

    Oracle: release total/4 from deferred revenue to service revenue.
    Trap: releasing the whole advance in January. Level V/U/V/V/V/V/V.
    """
    rng = random.Random(seed)
    monthly = Decimal(rng.randrange(30, 121)) * 25
    total = monthly * 4
    client = rng.choice(["Orion Dental", "Pike Logistics", "Rowan Legal"])
    opening = Decimal("10000.00")
    initial = _ledger_header(opening, UNEARNED_ACCOUNTS) + _txn(
        "2026-01-01",
        client,
        "Advance received for 4-month service contract",
        [(BANK, total), (DEFERRED, -total)],
    )
    doc = (
        f"# Service contract — {client}\n\n"
        f"USD {money(total)} received 2026-01-01 covers services for January "
        "through April 2026, delivered evenly each month. January's service "
        "has been delivered.\n"
    )
    policy = POLICY + (
        "- Advances for services are deferred revenue, recognized evenly by\n"
        "  month as the service is delivered (one quarter of this 4-month\n"
        "  contract per month).\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        client,
        "January service revenue earned",
        [(DEFERRED, monthly), (SERVICES, -monthly)],
    )
    return TaskInstance(
        task_id="unearned-revenue-release",
        family="accruals-deferrals",
        title="Release one month of unearned service revenue",
        instruction=(
            "Record January's earnings on the contract in "
            "`/app/documents/service_contract.md` in `/app/ledger.beancount`, "
            "following `/app/policy.md`. Append exactly one balanced "
            "transaction dated 2026-01-31; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(UNEARNED_ACCOUNTS),
            "documents/service_contract.md": doc,
        },
        expected=_expected(
            "unearned-revenue-release",
            "accruals-deferrals",
            seed,
            expected_deltas={DEFERRED: money(monthly), SERVICES: money(-monthly)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={DEFERRED: money(-(total - monthly))},
        ),
        solution_ledger=solution,
        keywords=["unearned-revenue", "deferral", "adjusting-entry"],
        level="vocational",
    )


RETIRE_LOSS = "Expenses:LossOnBondRetirement"
RETIRE_ACCOUNTS = [
    (BONDS, "Bonds payable at face value"),
    (BOND_DISCOUNT, "Unamortized discount on bonds (contra-liability; debit balance)"),
    (RETIRE_LOSS, "Loss on early retirement of bonds"),
]


def bond_early_retirement(seed: int) -> TaskInstance:
    """Scenario: bonds called above their carrying amount in January.

    Oracle: remove face and the remaining discount; loss = call price -
    carrying amount (face - discount). Trap: measuring the loss against
    face value and orphaning the discount. Level V/U/V/V/V/V/U.
    """
    rng = random.Random(seed)
    face = Decimal(rng.randrange(5, 16)) * 12000
    discount = (face * Decimal(rng.randrange(10, 41)) / 1000).quantize(Decimal("1"))
    carrying = face - discount
    call_pct = rng.choice([102, 103])
    call_price = (face * call_pct / 100).quantize(CENT)
    loss = call_price - carrying
    opening = call_price + Decimal("20000.00")
    initial = _ledger_header(opening, RETIRE_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        "Opening bond balances",
        [
            (BOND_DISCOUNT, discount),
            ("Equity:Opening-Balances", carrying),
            (BONDS, -face),
        ],
    )
    doc = (
        "# Bond call — 2026-01-15\n\n"
        f"The company called and retired all its bonds (face USD {money(face)}, "
        f"unamortized discount USD {money(discount)}) at {call_pct} "
        f"(USD {money(call_price)}), paid from checking.\n"
    )
    policy = POLICY + (
        "- On early retirement, remove the face amount and any unamortized\n"
        "  discount; the difference between the call price and the carrying\n"
        "  amount (face - discount) is a gain or loss on retirement.\n"
    )
    solution = initial + _txn(
        "2026-01-15",
        "Bondholders",
        "Bonds retired at call price",
        [(BONDS, face), (RETIRE_LOSS, loss), (BOND_DISCOUNT, -discount), (BANK, -call_price)],
    )
    return TaskInstance(
        task_id="bond-early-retirement",
        family="borrowings",
        title="Record the early retirement of bonds at a call price",
        instruction=(
            "Record the retirement in `/app/documents/bond_call.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated 2026-01-15; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(RETIRE_ACCOUNTS),
            "documents/bond_call.md": doc,
        },
        expected=_expected(
            "bond-early-retirement",
            "borrowings",
            seed,
            expected_deltas={
                BONDS: money(face),
                RETIRE_LOSS: money(loss),
                BOND_DISCOUNT: money(-discount),
                BANK: money(-call_price),
            },
            expected_new_transactions=[1, 2],
            expected_period=["2026-01-15", "2026-01-15"],
            required_final_balances={BONDS: "0.00", BOND_DISCOUNT: "0.00"},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["bonds", "early-retirement", "extinguishment"],
        level="vocational",
        standards=["asc:405-20", "ifrs:9"],
    )


FVOCI = "Assets:FVOCIInvestments"
AOCI = "Equity:AccumulatedOtherComprehensiveIncome"
FVOCI_ACCOUNTS = [
    (FVOCI, "Equity investments at fair value through OCI (IFRS)"),
    (AOCI, "Accumulated other comprehensive income"),
    (UNREALIZED, "Unrealized gain (credit) or loss (in profit or loss)"),
]


def fvoci_fair_value_adjustment(seed: int) -> TaskInstance:
    """Scenario (IFRS): FVOCI-elected shares rise by month-end.

    Oracle: debit the investment, credit AOCI (equity), not profit or
    loss, and no recycling on this election. Trap: crediting the
    unrealized gain to income as for trading securities.
    Level V/U/V/V/U/V/U -> vocational (borderline).
    """
    rng = random.Random(seed)
    shares = rng.randrange(100, 801, 25)
    cost_each = Decimal(rng.randrange(2000, 6001, 25)) / 100
    uplift = Decimal(rng.randrange(100, 601, 25)) / 100
    fair_each = cost_each + uplift
    cost_total = shares * cost_each
    gain = shares * uplift
    opening = cost_total + Decimal("10000.00")
    initial = _ledger_header(opening, FVOCI_ACCOUNTS) + _txn(
        "2026-01-05",
        "Broker",
        f"Bought {shares} shares (FVOCI election made)",
        [(FVOCI, cost_total), (BANK, -cost_total)],
    )
    doc = (
        "# Month-end quotes — 2026-01-31\n\n"
        f"The {shares} shares bought at USD {money(cost_each)} each are quoted "
        f"at USD {money(fair_each)} each. On acquisition the company made the "
        "irrevocable IFRS election to present fair-value changes of this "
        "strategic (non-trading) holding in other comprehensive income.\n"
    )
    policy = POLICY + (
        "- For equity investments with the FVOCI election, unrealized gains\n"
        "  and losses go to `Equity:AccumulatedOtherComprehensiveIncome`,\n"
        "  never to profit or loss, and are not recycled on disposal.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Broker",
        "FVOCI fair-value increase to OCI",
        [(FVOCI, gain), (AOCI, -gain)],
    )
    return TaskInstance(
        task_id="fvoci-fair-value-adjustment",
        family="investments",
        title="Record an FVOCI fair-value increase in OCI (IFRS)",
        instruction=(
            "Record the month-end adjustment in "
            "`/app/documents/month_end_quotes.md` in `/app/ledger.beancount` "
            "under IFRS as stated in `/app/policy.md`. Append exactly one "
            "balanced transaction dated 2026-01-31; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(FVOCI_ACCOUNTS),
            "documents/month_end_quotes.md": doc,
        },
        expected=_expected(
            "fvoci-fair-value-adjustment",
            "investments",
            seed,
            expected_deltas={FVOCI: money(gain), AOCI: money(-gain)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={FVOCI: money(cost_total + gain)},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["fvoci", "ifrs", "oci", "fair-value"],
        level="vocational",
        framework="ifrs",
        standards=["ifrs:9"],
    )


LAND = "Assets:Land"
BUILDING = "Assets:Building"
BASKET_ACCOUNTS = [
    (LAND, "Land (not depreciated)"),
    (BUILDING, "Building at cost"),
]


def basket_purchase_allocation(seed: int) -> TaskInstance:
    """Scenario: land and building bought together for one lump sum.

    Oracle: allocate the price by relative appraised values.
    Trap: splitting the lump sum evenly, or recording appraised values.
    Level V/U/V/U/V/V/V -> vocational (borderline).
    """
    rng = random.Random(seed)
    land_appraised = Decimal(rng.randrange(4, 13)) * 10000
    building_appraised = Decimal(rng.randrange(6, 16)) * 10000
    factor = rng.choice([Decimal("0.8"), Decimal("0.9")])
    lump = (land_appraised + building_appraised) * factor
    land_alloc = land_appraised * factor
    building_alloc = building_appraised * factor
    day = rng.randint(3, 22)
    date = f"2026-01-{day:02d}"
    opening = lump + Decimal("20000.00")
    initial = _ledger_header(opening, BASKET_ACCOUNTS)
    doc = (
        f"# Property purchase — {date}\n\n"
        f"Land and the building on it were bought together for a single price "
        f"of USD {money(lump)}, paid from checking. Independent appraisals: "
        f"land USD {money(land_appraised)}, building USD {money(building_appraised)}.\n"
    )
    policy = POLICY + (
        "- A lump-sum (basket) purchase price is allocated to the assets in\n"
        "  proportion to their relative appraised (fair) values. Land is\n"
        "  not depreciated; the building is recorded separately.\n"
    )
    solution = initial + _txn(
        date,
        "Seller",
        "Land and building acquired for a lump sum",
        [(LAND, land_alloc), (BUILDING, building_alloc), (BANK, -lump)],
    )
    return TaskInstance(
        task_id="basket-purchase-allocation",
        family="fixed-assets",
        title="Allocate a lump-sum property purchase",
        instruction=(
            "Record the purchase in `/app/documents/property_purchase.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md`. Append new "
            f"balanced transactions dated {date}; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(BASKET_ACCOUNTS),
            "documents/property_purchase.md": doc,
        },
        expected=_expected(
            "basket-purchase-allocation",
            "fixed-assets",
            seed,
            expected_deltas={
                LAND: money(land_alloc),
                BUILDING: money(building_alloc),
                BANK: money(-lump),
            },
            expected_new_transactions=[1, 2],
            expected_period=[date, date],
            required_final_balances={LAND: money(land_alloc)},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["basket-purchase", "lump-sum-allocation", "land-building"],
        level="vocational",
    )


def labor_efficiency_variance(seed: int) -> TaskInstance:
    """Numeric: labor efficiency variance. Trap: rate-variance formula."""
    rng = random.Random(seed)
    std_rate = Decimal(rng.randrange(1200, 3001, 25)) / 100
    actual_rate = std_rate + Decimal(rng.randrange(25, 201, 25)) / 100
    sh_per_unit = rng.choice([Decimal("0.5"), Decimal("1.5"), Decimal("2")])
    output = rng.randrange(1000, 4001, 100)
    allowed = (sh_per_unit * output).quantize(Decimal("1"))
    excess = Decimal(rng.randrange(50, 601, 25))
    actual_hours = allowed + excess
    gold = excess * std_rate
    trap = ((actual_rate - std_rate) * actual_hours).quantize(CENT)
    if trap == gold:
        trap += Decimal("100.00")
    data = (
        "# Direct labor — January 2026\n\n| Item | Value |\n|---|---:|\n"
        f"| Standard rate | USD {money(std_rate)} per hour |\n"
        f"| Actual rate paid | USD {money(actual_rate)} per hour |\n"
        f"| Standard hours | {format(sh_per_unit, 'f')} per finished unit |\n"
        f"| Finished units produced | {output} |\n"
        f"| Actual hours worked | {int(actual_hours)} |\n"
    )
    policy = """# Standard costing conventions (applies to this task)

- Labor EFFICIENCY variance = (actual hours - standard hours allowed
  for actual output) x STANDARD rate. (The rate variance instead uses
  the actual-minus-standard rate.) Positive = unfavorable.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "labor efficiency variance",
        "Using `/app/documents/labor_data.md` and `/app/policy.md`, compute the "
        "**labor efficiency variance** in USD (positive = unfavorable).",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="labor-efficiency-variance",
        family="standard-costing",
        title="Compute the labor efficiency variance",
        question=question,
        policy=policy,
        data_name="labor_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "standard-costing", "labor-variance"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


def diluted_eps(seed: int) -> TaskInstance:
    """Numeric: diluted EPS with options (treasury method). Trap: basic EPS."""
    rng = random.Random(seed)
    was = rng.randrange(20000, 80001, 2500)
    options = rng.randrange(5000, 20001, 500)
    market = Decimal(rng.choice([40, 48, 50, 60]))
    exercise = market * Decimal("0.8")
    repurchased = int(options * exercise / market)  # exact at 0.8 ratio
    incremental = options - repurchased
    eps = (Decimal(rng.randrange(120, 401, 5)) / 100).quantize(CENT)
    net_income = (eps * (was + incremental)).quantize(Decimal("1"))
    # keep the presented net income consistent with a clean 2-d.p. gold
    gold = (net_income / (was + incremental)).quantize(Decimal("0.0001"))
    trap = (net_income / was).quantize(Decimal("0.0001"))
    data = (
        "# Earnings per share data — year ended 2025-12-31\n\n| Item | Value |\n|---|---:|\n"
        f"| Net income | USD {money(net_income)} |\n"
        f"| Weighted-average common shares outstanding | {was} |\n"
        f"| Employee stock options outstanding | {options} shares |\n"
        f"| Exercise price | USD {money(exercise)} |\n"
        f"| Average market price | USD {money(market)} |\n"
        "\nNo preferred shares. The options are dilutive.\n"
    )
    policy = """# Diluted EPS conventions (applies to this task)

- Treasury-stock method: incremental shares = options - (options x
  exercise price / average market price).
- Diluted EPS = net income / (weighted-average shares + incremental
  shares). Answer in USD per share.
"""
    question = _numeric_question(
        "diluted earnings per share",
        "Using `/app/documents/eps_data.md` and `/app/policy.md`, compute "
        "**diluted earnings per share** in USD.",
        "the USD amount per share",
    )
    return _numeric_instance(
        task_id="diluted-eps",
        family="financial-analysis",
        title="Compute diluted EPS (treasury-stock method)",
        question=question,
        policy=policy,
        data_name="eps_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "eps", "dilution", "treasury-stock-method"],
        abs_tolerance="0.01",
        trap_value=format(trap, "f"),
        standards=["asc:260", "ias:33"],
    )


def asset_turnover_ratio(seed: int) -> TaskInstance:
    """Numeric: asset turnover on average assets. Trap: ending assets."""
    rng = random.Random(seed)
    turnover = rng.choice(
        [Decimal("0.80"), Decimal("1.20"), Decimal("1.50"), Decimal("1.80"), Decimal("2.40")]
    )
    average = Decimal(rng.randrange(200, 901)) * 1000
    step = rng.randint(1, 5)
    delta = Decimal(step) * 10000
    beginning, ending = average - delta, average + delta
    sales = average * turnover
    trap = (sales / ending).quantize(Decimal("0.0001"))
    data = (
        "# Turnover data — year ended 2025-12-31\n\n| Item | USD |\n|---|---:|\n"
        f"| Net sales | {money(sales)} |\n"
        f"| Total assets, 2025-01-01 | {money(beginning)} |\n"
        f"| Total assets, 2025-12-31 | {money(ending)} |\n"
    )
    policy = """# Ratio conventions (applies to this task)

- Asset turnover = net sales / AVERAGE total assets, where the average
  is (opening + closing) / 2.
- Answer with the ratio (for example 1.50) in `/app/answer.json`.
"""
    question = _numeric_question(
        "asset turnover",
        "Using `/app/documents/turnover_data.md` and `/app/policy.md`, compute **asset turnover**.",
        "the ratio",
    )
    return _numeric_instance(
        task_id="asset-turnover-ratio",
        family="financial-analysis",
        title="Compute asset turnover",
        question=question,
        policy=policy,
        data_name="turnover_data.md",
        data=data,
        gold=turnover,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "asset-turnover", "efficiency-ratio"],
        abs_tolerance="0.01",
        trap_value=format(trap, "f"),
    )


def breakeven_sales_dollars(seed: int) -> TaskInstance:
    """Numeric: break-even in sales dollars. Trap: answering break-even units."""
    rng = random.Random(seed)
    price = Decimal(rng.choice([40, 50, 80, 100]))
    cm_ratio = rng.choice([Decimal("0.30"), Decimal("0.40"), Decimal("0.50")])
    cm_unit = price * cm_ratio
    variable = price - cm_unit
    target_dollars = Decimal(rng.randrange(200, 1201)) * 1000
    fixed = target_dollars * cm_ratio
    trap_units = int(fixed / cm_unit)
    data = (
        "# Single-product data (monthly)\n\n| Item | Value |\n|---|---:|\n"
        f"| Selling price | USD {money(price)} per unit |\n"
        f"| Variable cost | USD {money(variable)} per unit |\n"
        f"| Total fixed costs | USD {money(fixed)} |\n"
    )
    policy = """# CVP conventions (applies to this task)

- Contribution margin ratio = (price - variable cost) / price.
- Break-even SALES DOLLARS = fixed costs / contribution margin ratio.
  (Fixed costs / margin per unit gives break-even UNITS, not dollars.)
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "break-even sales dollars",
        "Using `/app/documents/product_data.md` and `/app/policy.md`, compute "
        "the monthly **break-even point in sales dollars**.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="breakeven-sales-dollars",
        family="cost-volume-profit",
        title="Compute break-even sales dollars",
        question=question,
        policy=policy,
        data_name="product_data.md",
        data=data,
        gold=target_dollars,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "cvp", "break-even-dollars"],
        abs_tolerance="0.01",
        trap_value=str(trap_units),
    )


def direct_materials_used(seed: int) -> TaskInstance:
    """Numeric: direct materials used. Trap: purchases only."""
    rng = random.Random(seed)

    def amt(lo, hi):
        return Decimal(rng.randrange(lo, hi)) * 100

    beginning, purchases, freight = amt(40, 161), amt(200, 601), amt(4, 31)
    ending = amt(30, 141)
    if beginning + freight == ending:  # purchases-only trap would equal the gold
        ending += 100
    gold = beginning + purchases + freight - ending
    data = (
        "# Raw materials — January 2026\n\n| Item | USD |\n|---|---:|\n"
        f"| Raw materials, 2026-01-01 | {money(beginning)} |\n"
        f"| Raw materials purchased | {money(purchases)} |\n"
        f"| Freight-in on materials | {money(freight)} |\n"
        f"| Raw materials, 2026-01-31 | {money(ending)} |\n"
    )
    policy = """# Materials used conventions (applies to this task)

- Direct materials USED = beginning raw materials + purchases
  + freight-in - ending raw materials.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "direct materials used",
        "Using `/app/documents/raw_materials.md` and `/app/policy.md`, compute "
        "**direct materials used** in January in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="direct-materials-used",
        family="job-order-costing",
        title="Compute direct materials used",
        question=question,
        policy=policy,
        data_name="raw_materials.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "materials-used", "cogm-schedule"],
        abs_tolerance="0.01",
        trap_value=money(purchases),
    )


SUBSEQUENT_OPTIONS = [
    "Recognize (adjust the financial statements)",
    "Disclose only (do not adjust)",
    "Neither recognize nor disclose",
]
SUBSEQUENT_CASES = [
    (
        "A major customer, already in financial difficulty at the reporting "
        "date, declared bankruptcy in February, before the statements were "
        "issued. Its December balance is uncollectible.",
        "Recognize (adjust the financial statements)",
    ),
    (
        "A lawsuit over an event that occurred in November was settled in "
        "February, before issuance, for an amount different from the accrual.",
        "Recognize (adjust the financial statements)",
    ),
    (
        "A fire destroyed a warehouse in February, after the reporting "
        "date. The loss is material and uninsured.",
        "Disclose only (do not adjust)",
    ),
    (
        "The board approved a 2-for-1 stock split in February, after the reporting date.",
        "Disclose only (do not adjust)",
    ),
    (
        "A minor supplier changed its payment terms in February, with no "
        "material effect on the reported amounts.",
        "Neither recognize nor disclose",
    ),
]


def sc_subsequent_event_classification(seed: int) -> TaskInstance:
    """Single-choice: recognized vs nonrecognized subsequent event.

    Trap: treating a post-period disaster (fire) as an adjusting event
    because it is material. Level: policy states the condition-at-date
    test -> vocational.
    """
    rng = random.Random(seed)
    narrative, correct = rng.choice(SUBSEQUENT_CASES)
    labels = SUBSEQUENT_OPTIONS.copy()
    rng.shuffle(labels)
    option_ids = ["A", "B", "C"]
    gold = option_ids[labels.index(correct)]
    options_md = "\n".join(f"- {oid}. {name}" for oid, name in zip(option_ids, labels, strict=True))
    policy = """# Subsequent events (applies to this task)

- RECOGNIZE (adjust) events providing evidence about conditions that
  EXISTED at the reporting date (e.g., bankruptcy proving a receivable
  was already impaired, settling pre-existing litigation).
- DISCLOSE ONLY material events arising from conditions AFTER the
  reporting date (e.g., a later fire, a later stock split).
- Immaterial later events are neither recognized nor disclosed.
"""
    question = _choice_question(
        "subsequent event treatment",
        f"Event (reporting date 2025-12-31, evaluation before issuance):\n\n"
        f"**{narrative}**\n\nUsing `/app/policy.md`, how is it treated? "
        "Select exactly one option.",
        options_md,
        '"B"',
    )
    return TaskInstance(
        task_id="sc-subsequent-event-classification",
        family="financial-reporting",
        title="Classify a subsequent event",
        instruction=(
            "Answer the single-choice question in `/app/question.md` "
            "following `/app/policy.md`. Write your selection to "
            "`/app/answer.json` in the exact format shown in the question."
        ),
        app_files={
            "question.md": question,
            "policy.md": policy,
            "answer.example.json": '{\n  "final_answer": "A",\n  "confidence": 50\n}\n',
        },
        expected=_expected(
            "sc-subsequent-event-classification",
            "financial-reporting",
            seed,
            format="single-choice",
            gold=gold,
            options=option_ids,
            expected_deltas={},
            expected_new_transactions=0,
            expected_period=None,
        ),
        solution_ledger="",
        solution_answer={"final_answer": gold, "confidence": 100},
        keywords=["single-choice", "subsequent-events"],
        level="vocational",
        format="single-choice",
        skill="remembering-understanding",
        standards=["asc:855", "ias:10"],
    )


def treasury_stock_reissuance(seed: int) -> TaskInstance:
    """Scenario: treasury shares reissued above their repurchase cost.

    Oracle: bank at proceeds, treasury stock credited at cost, excess to
    APIC. Trap: recognizing the excess as a gain in income. Cost method.
    Level V/U/V/V/V/V/U -> vocational.
    """
    rng = random.Random(seed)
    shares = rng.randrange(200, 2001, 100)
    cost_each = Decimal(rng.randrange(8, 31))
    sale_each = cost_each + Decimal(rng.randrange(2, 11))
    cost_total = shares * cost_each
    proceeds = shares * sale_each
    stock_open = Decimal(rng.randrange(8000, 20001, 500))
    opening = cost_total + Decimal("20000.00")
    initial = (
        _ledger_header(opening, TREASURY_ACCOUNTS)
        + _txn(
            "2026-01-01",
            "Opening",
            "Opening common stock",
            [("Equity:Opening-Balances", stock_open), (COMMON_STOCK, -stock_open)],
        )
        + _txn(
            "2026-01-05",
            "Broker",
            f"Repurchased {shares} shares into treasury",
            [(TREASURY, cost_total), (BANK, -cost_total)],
        )
    )
    doc = (
        "# Treasury share reissuance — 2026-01-20\n\n"
        f"All {shares} treasury shares repurchased on 2026-01-05 at "
        f"USD {money(cost_each)} each were reissued to investors at "
        f"USD {money(sale_each)} each, received into checking.\n"
    )
    policy = POLICY + (
        "- Treasury stock uses the cost method. On reissuance above cost,\n"
        "  credit treasury stock at its repurchase cost and credit the\n"
        "  excess to additional paid-in capital. A company never recognizes\n"
        "  a gain or loss in income on transactions in its own shares.\n"
    )
    solution = initial + _txn(
        "2026-01-20",
        "Investors",
        "Treasury shares reissued above cost",
        [(BANK, proceeds), (TREASURY, -cost_total), (APIC, -(proceeds - cost_total))],
    )
    return TaskInstance(
        task_id="treasury-stock-reissuance",
        family="equity",
        title="Reissue treasury shares above cost",
        instruction=(
            "Record the reissuance in `/app/documents/reissuance.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated 2026-01-20; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(TREASURY_ACCOUNTS),
            "documents/reissuance.md": doc,
        },
        expected=_expected(
            "treasury-stock-reissuance",
            "equity",
            seed,
            expected_deltas={
                BANK: money(proceeds),
                TREASURY: money(-cost_total),
                APIC: money(-(proceeds - cost_total)),
            },
            expected_new_transactions=[1, 2],
            expected_period=["2026-01-20", "2026-01-20"],
            required_final_balances={TREASURY: "0.00", APIC: money(-(proceeds - cost_total))},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["treasury-stock", "reissuance", "paid-in-capital"],
        level="vocational",
    )


ROU_ASSET = "Assets:RightOfUseAsset"
LEASE_LIABILITY = "Liabilities:LeaseLiability"
LEASE_ENTRY_ACCOUNTS = [
    (ROU_ASSET, "Right-of-use asset"),
    (LEASE_LIABILITY, "Lease liability at present value of lease payments"),
]


def lease_initial_recognition(seed: int) -> TaskInstance:
    """Scenario: recognize a lease at commencement from a stated PV factor.

    Oracle: right-of-use asset and lease liability at annual payment x
    annuity factor. Trap: expensing payments as rent with no balance-sheet
    recognition. Level V/U/V/V/V/V/U -> vocational.
    """
    rng = random.Random(seed)
    asset = rng.choice(["warehouse space", "delivery fleet", "production equipment"])
    years = rng.choice([3, 4, 5, 6])
    rate = rng.choice([Decimal("0.05"), Decimal("0.06"), Decimal("0.08")])
    factor = _annuity_factor(rate, years)
    payment = Decimal(rng.randrange(10, 61)) * 1000
    present_value = (payment * factor).quantize(CENT)
    opening = Decimal("20000.00")
    initial = _ledger_header(opening, LEASE_ENTRY_ACCOUNTS)
    doc = (
        f"# Lease commencement — {asset}, 2026-01-01\n\n"
        f"Term {years} years. Payments of USD {money(payment)} are due at each "
        f"year-end. Discount rate {rate * 100:.0f}%; annuity factor "
        f"({rate * 100:.0f}%, {years} years) {factor}. No payment at "
        "commencement, initial direct costs, or lease incentives.\n"
    )
    policy = POLICY + (
        "- At lease commencement, recognize a right-of-use asset and a lease\n"
        "  liability at the present value of lease payments (annual payment\n"
        "  x the annuity factor stated in the lease document, used as given).\n"
        "  With no prepayments, incentives, or initial direct costs, the two\n"
        "  opening amounts are equal.\n"
    )
    solution = initial + _txn(
        "2026-01-01",
        "Lessor",
        f"Recognize lease of {asset}",
        [(ROU_ASSET, present_value), (LEASE_LIABILITY, -present_value)],
    )
    return TaskInstance(
        task_id="lease-initial-recognition",
        family="leases",
        title="Recognize a right-of-use asset and lease liability",
        instruction=(
            "Record the commencement entry in `/app/documents/lease_terms.md` "
            "in `/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated 2026-01-01; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(LEASE_ENTRY_ACCOUNTS),
            "documents/lease_terms.md": doc,
        },
        expected=_expected(
            "lease-initial-recognition",
            "leases",
            seed,
            expected_deltas={
                ROU_ASSET: money(present_value),
                LEASE_LIABILITY: money(-present_value),
            },
            expected_period=["2026-01-01", "2026-01-01"],
            required_final_balances={LEASE_LIABILITY: money(-present_value)},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["leases", "right-of-use", "initial-recognition"],
        level="vocational",
        standards=["asc:842", "ifrs:16"],
    )


FX_LOSS = "Expenses:ForeignExchangeLoss"
FX_PAYABLE_ACCOUNTS = [
    (AP, "Trade payables (supplier invoices on credit)"),
    (INVENTORY, "Inventory of goods held for sale (perpetual)"),
    (FX_LOSS, "Foreign-exchange loss on monetary items"),
]


def fx_payable_remeasurement(seed: int) -> TaskInstance:
    """Scenario: euro payable strengthens against USD by January 31.

    Oracle: remeasure only the monetary payable to the closing spot,
    recognizing the increase as an FX loss. Trap: adjusting inventory
    (a nonmonetary item at historical cost). Level V/U/V/V/V/V/U.
    """
    rng = random.Random(seed)
    supplier = rng.choice(["Alpen Werkzeuge", "Bergman Components", "Nordhaus GmbH"])
    euros = Decimal(rng.randrange(2, 11)) * 10000
    initial_spot = rng.choice([Decimal("1.05"), Decimal("1.08"), Decimal("1.10"), Decimal("1.12")])
    uplift = Decimal(rng.randrange(2, 13)) / 100
    closing_spot = initial_spot + uplift
    initial_amount = euros * initial_spot
    loss = euros * uplift
    opening = Decimal("30000.00")
    initial = _ledger_header(opening, FX_PAYABLE_ACCOUNTS) + _txn(
        "2026-01-08",
        supplier,
        "Merchandise purchased on credit (euro invoice)",
        [(INVENTORY, initial_amount), (AP, -initial_amount)],
    )
    doc = (
        f"# Foreign supplier balance — {supplier}\n\n"
        f"Invoice: EUR {money(euros)}, recorded 2026-01-08 at the spot rate "
        f"USD {initial_spot:.2f} per EUR. Spot rate at 2026-01-31: "
        f"USD {closing_spot:.2f} per EUR. The payable is still outstanding.\n"
    )
    policy = POLICY + (
        "- Foreign-currency MONETARY items (such as payables) are remeasured\n"
        "  at the closing spot rate; the exchange difference is recognized\n"
        "  in profit or loss. Inventory is nonmonetary and stays at the\n"
        "  historical transaction-date rate.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        supplier,
        "Remeasure euro payable to closing spot",
        [(FX_LOSS, loss), (AP, -loss)],
    )
    return TaskInstance(
        task_id="fx-payable-remeasurement",
        family="foreign-currency",
        title="Remeasure a foreign-currency payable",
        instruction=(
            "Record the January 31 adjustment in "
            "`/app/documents/fx_balance.md` in `/app/ledger.beancount`, "
            "following `/app/policy.md`. Append exactly one balanced "
            "transaction dated 2026-01-31; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(FX_PAYABLE_ACCOUNTS),
            "documents/fx_balance.md": doc,
        },
        expected=_expected(
            "fx-payable-remeasurement",
            "foreign-currency",
            seed,
            expected_deltas={FX_LOSS: money(loss), AP: money(-loss)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={
                AP: money(-euros * closing_spot),
                INVENTORY: money(initial_amount),
            },
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["foreign-currency", "remeasurement", "monetary-items"],
        level="vocational",
        standards=["asc:830", "ias:21"],
    )


DEVELOPMENT_ASSET = "Assets:DevelopmentCosts"
RD_EXPENSE = "Expenses:ResearchAndDevelopment"
RD_ACCOUNTS = [
    (DEVELOPMENT_ASSET, "Capitalized development costs (IAS 38 criteria met)"),
    (RD_EXPENSE, "Research and development expense"),
]


def development_cost_capitalization(seed: int) -> TaskInstance:
    """Scenario (IFRS): a January project crosses technical feasibility.

    Oracle: research and pre-feasibility work are expensed; only directly
    attributable post-feasibility materials and staff costs capitalize.
    Trap: capitalizing all project spend. Level V/U/V/U/U/V/U.
    """
    rng = random.Random(seed)
    research = Decimal(rng.randrange(40, 161)) * 50
    pre_feasibility = Decimal(rng.randrange(20, 81)) * 50
    materials = Decimal(rng.randrange(30, 121)) * 50
    staff = Decimal(rng.randrange(50, 201)) * 50
    training = Decimal(rng.randrange(10, 41)) * 25
    capitalized = materials + staff
    expensed = research + pre_feasibility + training
    total = capitalized + expensed
    opening = total + Decimal("20000.00")
    initial = _ledger_header(opening, RD_ACCOUNTS)
    doc = (
        "# New-product project costs — January 2026 (all paid from checking)\n\n"
        "| Cost | USD |\n|---|---:|\n"
        f"| Exploratory research | {money(research)} |\n"
        f"| Prototype work before feasibility | {money(pre_feasibility)} |\n"
        f"| Materials consumed after feasibility | {money(materials)} |\n"
        f"| Directly engaged development staff after feasibility | {money(staff)} |\n"
        f"| Training staff to operate the future process | {money(training)} |\n\n"
        "At 2026-01-10 all IAS 38 development capitalization criteria were "
        "met and are documented in the project file.\n"
    )
    policy = POLICY + (
        "- Under IAS 38, research and costs incurred before development\n"
        "  capitalization criteria are met are expensed. Only directly\n"
        "  attributable materials and directly engaged staff costs incurred\n"
        "  AFTER the criteria are met are capitalized. Training is expensed.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Project",
        "January research and development costs",
        [(DEVELOPMENT_ASSET, capitalized), (RD_EXPENSE, expensed), (BANK, -total)],
    )
    return TaskInstance(
        task_id="development-cost-capitalization",
        family="intangible-assets",
        title="Capitalize qualifying development costs (IFRS)",
        instruction=(
            "Record the January project costs in `/app/documents/project_costs.md` "
            "in `/app/ledger.beancount` under IFRS as stated in `/app/policy.md`. "
            "Append new balanced transactions dated 2026-01-31; do not edit "
            "existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(RD_ACCOUNTS),
            "documents/project_costs.md": doc,
        },
        expected=_expected(
            "development-cost-capitalization",
            "intangible-assets",
            seed,
            expected_deltas={
                DEVELOPMENT_ASSET: money(capitalized),
                RD_EXPENSE: money(expensed),
                BANK: money(-total),
            },
            expected_new_transactions=[1, 3],
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={DEVELOPMENT_ASSET: money(capitalized)},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["ifrs", "ias-38", "development-costs", "research"],
        level="vocational",
        framework="ifrs",
        standards=["ias:38"],
    )


ERROR_ACCOUNTS = INVENTORY_ACCOUNTS + [(RETAINED, "Retained earnings")]


def inventory_error_correction(seed: int) -> TaskInstance:
    """Scenario: last year's count omitted goods; opening inventory is low.

    Oracle: debit inventory, credit opening retained earnings (prior-period
    correction, tax ignored as stated). Trap: crediting current-period
    cost of goods sold. Level V/U/U/V/U/U/U -> vocational (borderline).
    """
    rng = random.Random(seed)
    item = rng.choice(["ceramic planters", "trail backpacks", "LED desk lamps"])
    recorded_units = rng.randrange(100, 301, 10)
    omitted_units = rng.randrange(10, 61, 5)
    unit_cost = Decimal(rng.randrange(800, 3001, 25)) / 100
    recorded = recorded_units * unit_cost
    error = omitted_units * unit_cost
    retained_open = Decimal(rng.randrange(200, 801)) * 100
    opening = Decimal("20000.00")
    initial = (
        _ledger_header(opening, ERROR_ACCOUNTS)
        + _txn(
            "2026-01-01",
            "Opening",
            "Opening retained earnings (as previously reported)",
            [("Equity:Opening-Balances", retained_open), (RETAINED, -retained_open)],
        )
        + _txn(
            "2026-01-01",
            "Opening",
            f"Opening inventory as previously reported: {recorded_units} {item}",
            [(INVENTORY, recorded), ("Equity:Opening-Balances", -recorded)],
        )
    )
    doc = (
        "# Audit finding — 2026-01-06\n\n"
        f"The 2025 year-end count omitted {omitted_units} {item} (cost "
        f"USD {money(unit_cost)} each) held in a side storeroom, so opening "
        "inventory and opening retained earnings are both understated. The "
        "2025 statements have been issued. Ignore income-tax effects for "
        "this correction (handled separately).\n"
    )
    policy = POLICY + (
        "- A material prior-period error is corrected retrospectively\n"
        "  against OPENING retained earnings, not through current-period\n"
        "  profit or loss. Append the correction dated 2026-01-01; never\n"
        "  rewrite the recorded opening entries.\n"
    )
    solution = initial + _txn(
        "2026-01-01",
        "Audit",
        "Correct understated opening inventory",
        [(INVENTORY, error), (RETAINED, -error)],
    )
    return TaskInstance(
        task_id="inventory-error-correction",
        family="accounting-changes-errors",
        title="Correct an understated opening inventory",
        instruction=(
            "Record the correction in `/app/documents/audit_finding.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated 2026-01-01; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(ERROR_ACCOUNTS),
            "documents/audit_finding.md": doc,
        },
        expected=_expected(
            "inventory-error-correction",
            "accounting-changes-errors",
            seed,
            expected_deltas={INVENTORY: money(error), RETAINED: money(-error)},
            expected_period=["2026-01-01", "2026-01-01"],
            required_final_balances={
                INVENTORY: money(recorded + error),
                RETAINED: money(-(retained_open + error)),
            },
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["prior-period-error", "inventory", "restatement"],
        level="vocational",
        standards=["asc:250", "ias:8"],
    )


IMPAIRMENT_LOSS = "Expenses:ImpairmentLoss"
ACC_IMPAIRMENT = "Assets:AccumulatedImpairment"
IMPAIRMENT_ACCOUNTS = DISPOSAL_ACCOUNTS + [
    (IMPAIRMENT_LOSS, "Impairment loss on long-lived assets"),
    (ACC_IMPAIRMENT, "Accumulated impairment losses (contra-asset)"),
]


def long_lived_asset_impairment(seed: int) -> TaskInstance:
    """Scenario (IFRS): a machine's carrying amount exceeds recoverable amount.

    Oracle: recoverable is the HIGHER of fair value less costs of disposal
    and value in use; impair carrying down to it. Trap: using the lower
    measure (larger write-down). Level V/U/V/U/U/V/U -> vocational.
    """
    rng = random.Random(seed)
    asset = rng.choice(["injection molder", "packaging line", "CNC router"])
    carrying = Decimal(rng.randrange(40, 121)) * 1000
    acc_dep = Decimal(rng.randrange(20, 61)) * 1000
    cost = carrying + acc_dep
    impairment = Decimal(rng.randrange(4, 25)) * 1000
    recoverable = carrying - impairment
    lower_gap = Decimal(rng.randrange(2, 11)) * 1000
    lower_measure = recoverable - lower_gap
    if rng.random() < 0.5:
        fvlcd, viu = recoverable, lower_measure
    else:
        fvlcd, viu = lower_measure, recoverable
    undiscounted = carrying + Decimal(rng.randrange(2, 11)) * 1000
    opening = Decimal("20000.00")
    initial = _ledger_header(opening, IMPAIRMENT_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        f"Opening carrying amount: {asset}",
        [
            ("Assets:Equipment", cost),
            (ACC_DEP, -acc_dep),
            ("Equity:Opening-Balances", acc_dep - cost),
        ],
    )
    doc = (
        f"# Impairment review — {asset}, 2026-01-31\n\n"
        f"Cost USD {money(cost)}; accumulated depreciation USD {money(acc_dep)} "
        f"(carrying amount USD {money(carrying)}). At the review date:\n\n"
        f"- Fair value less costs of disposal: USD {money(fvlcd)}\n"
        f"- Value in use (discounted): USD {money(viu)}\n"
        f"- Undiscounted expected future cash flows: USD {money(undiscounted)}\n"
    )
    policy = POLICY + (
        "- Under IAS 36, recoverable amount is the HIGHER of fair value less\n"
        "  costs of disposal and value in use. If carrying amount exceeds\n"
        "  recoverable amount, write it down (impairment loss in profit or\n"
        "  loss, credited to accumulated impairment). Undiscounted cash\n"
        "  flows are not a recoverability test under IFRS.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Impairment review",
        f"Write {asset} down to recoverable amount",
        [(IMPAIRMENT_LOSS, impairment), (ACC_IMPAIRMENT, -impairment)],
    )
    return TaskInstance(
        task_id="long-lived-asset-impairment",
        family="fixed-assets",
        title="Impair a long-lived asset to recoverable amount (IFRS)",
        instruction=(
            "Record the January adjustment in `/app/documents/impairment_review.md` "
            "in `/app/ledger.beancount` under IFRS as stated in `/app/policy.md`. "
            "Append exactly one balanced transaction dated 2026-01-31; do not "
            "edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(IMPAIRMENT_ACCOUNTS),
            "documents/impairment_review.md": doc,
        },
        expected=_expected(
            "long-lived-asset-impairment",
            "fixed-assets",
            seed,
            expected_deltas={
                IMPAIRMENT_LOSS: money(impairment),
                ACC_IMPAIRMENT: money(-impairment),
            },
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={ACC_IMPAIRMENT: money(-impairment)},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["impairment", "ias-36", "recoverable-amount"],
        level="vocational",
        framework="ifrs",
        standards=["ias:36"],
    )


def production_budget_units(seed: int) -> TaskInstance:
    """Numeric: budgeted production. Trap: budgeted sales units only."""
    rng = random.Random(seed)
    sales = rng.randrange(4000, 16001, 100)
    desired_ending = rng.randrange(300, 2001, 50)
    beginning = rng.randrange(200, 1601, 50)
    if desired_ending == beginning:
        desired_ending += 50
    gold = Decimal(sales + desired_ending - beginning)
    data = (
        "# Production budget data — February 2026\n\n| Item | Units |\n|---|---:|\n"
        f"| Budgeted unit sales | {sales} |\n"
        f"| Desired ending finished goods | {desired_ending} |\n"
        f"| Beginning finished goods | {beginning} |\n"
    )
    policy = """# Production budget conventions (applies to this task)

- Units to produce = budgeted unit sales + desired ending finished
  goods - beginning finished goods.
- Answer with the unit count in `/app/answer.json`.
"""
    question = _numeric_question(
        "budgeted production units",
        "Using `/app/documents/production_budget.md` and `/app/policy.md`, compute "
        "**units to produce in February**.",
        "the unit count",
    )
    return _numeric_instance(
        task_id="production-budget-units",
        family="budgeting",
        title="Compute budgeted production units",
        question=question,
        policy=policy,
        data_name="production_budget.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "production-budget", "operating-budget"],
        abs_tolerance="1",
        trap_value=str(sales),
    )


def predetermined_overhead_applied(seed: int) -> TaskInstance:
    """Numeric: rate from estimates applied to actual base. Trap: actual OH."""
    rng = random.Random(seed)
    rate = Decimal(rng.randrange(4, 21)) * Decimal("2.50")
    estimated_hours = rng.randrange(8000, 24001, 500)
    estimated_overhead = rate * estimated_hours
    actual_hours = rng.randrange(7000, 26001, 250)
    if actual_hours == estimated_hours:
        actual_hours += 250
    gold = rate * actual_hours
    actual_overhead = gold + Decimal(rng.choice([-1, 1]) * rng.randrange(20, 121)) * 100
    data = (
        "# Overhead budget and actuals — January 2026\n\n| Item | Value |\n|---|---:|\n"
        f"| Estimated manufacturing overhead | USD {money(estimated_overhead)} |\n"
        f"| Estimated direct-labor hours | {estimated_hours} |\n"
        f"| Actual direct-labor hours | {actual_hours} |\n"
        f"| Actual manufacturing overhead | USD {money(actual_overhead)} |\n"
    )
    policy = """# Predetermined overhead conventions (applies to this task)

- Predetermined rate = estimated overhead / estimated allocation base.
- Applied overhead = predetermined rate x ACTUAL allocation base.
  Actual overhead is compared with applied overhead later; it is never
  the amount applied.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "applied manufacturing overhead",
        "Using `/app/documents/overhead_budget.md` and `/app/policy.md`, compute "
        "**manufacturing overhead applied** in January in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="predetermined-overhead-applied",
        family="job-order-costing",
        title="Compute applied overhead from the predetermined rate",
        question=question,
        policy=policy,
        data_name="overhead_budget.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "predetermined-overhead", "applied-overhead"],
        abs_tolerance="0.01",
        trap_value=money(actual_overhead),
    )


def interim_income_tax_expense(seed: int) -> TaskInstance:
    """Numeric: Q2 tax is YTD tax at estimated annual rate less Q1 tax.

    Trap: applying the rate to Q2-only pretax income.
    """
    rng = random.Random(seed)
    q1_income = Decimal(rng.randrange(100, 401)) * 1000
    q2_income = Decimal(rng.randrange(80, 361)) * 1000
    annual_rate = rng.choice([Decimal("0.21"), Decimal("0.24"), Decimal("0.25")])
    q1_rate = annual_rate - Decimal("0.01")
    q1_tax = q1_income * q1_rate
    ytd = q1_income + q2_income
    gold = ytd * annual_rate - q1_tax
    trap = q2_income * annual_rate
    data = (
        "# Interim tax data — six months ended 2026-06-30\n\n| Item | USD |\n|---|---:|\n"
        f"| Pretax income, Q1 | {money(q1_income)} |\n"
        f"| Pretax income, Q2 | {money(q2_income)} |\n"
        f"| Pretax income, year to date | {money(ytd)} |\n"
        f"| Income tax expense already recognized in Q1 | {money(q1_tax)} |\n"
        f"| Estimated annual effective tax rate at Q2 | {annual_rate * 100:.0f}% |\n"
    )
    policy = """# Interim tax conventions (applies to this task)

- Year-to-date tax = year-to-date pretax income x the CURRENT estimated
  annual effective tax rate.
- The current quarter's expense is that year-to-date amount less tax
  already recognized in earlier quarters.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "Q2 interim income tax expense",
        "Using `/app/documents/interim_tax.md` and `/app/policy.md`, compute "
        "**income tax expense for Q2** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="interim-income-tax-expense",
        family="income-taxes",
        title="Compute Q2 interim income tax expense",
        question=question,
        policy=policy,
        data_name="interim_tax.md",
        data=data,
        gold=gold,
        seed=seed,
        category="tax",
        keywords=["numeric", "interim-reporting", "income-tax"],
        abs_tolerance="0.01",
        trap_value=money(trap),
        standards=["asc:740", "ias:34"],
    )


def segment_margin(seed: int) -> TaskInstance:
    """Numeric: segment margin excludes common fixed costs.

    Trap: subtracting allocated common fixed costs (segment net income).
    """
    rng = random.Random(seed)

    def amt(lo, hi):
        return Decimal(rng.randrange(lo, hi)) * 100

    sales, variable, traceable, common = amt(400, 1001), amt(150, 451), amt(50, 201), amt(40, 161)
    gold = sales - variable - traceable
    trap = gold - common
    data = (
        "# Segment data — January 2026\n\n| Item | USD |\n|---|---:|\n"
        f"| Segment sales | {money(sales)} |\n"
        f"| Segment variable costs | {money(variable)} |\n"
        f"| Traceable fixed costs | {money(traceable)} |\n"
        f"| Common fixed costs allocated to the segment | {money(common)} |\n"
    )
    policy = """# Segment margin conventions (applies to this task)

- Segment margin = segment sales - segment variable costs - TRACEABLE
  fixed costs. Common fixed costs are not controllable by / traceable
  to the segment and are excluded, allocated or not.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "segment margin",
        "Using `/app/documents/segment_data.md` and `/app/policy.md`, compute "
        "the **segment margin** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="segment-margin",
        family="responsibility-accounting",
        title="Compute a segment margin",
        question=question,
        policy=policy,
        data_name="segment_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "segment-margin", "traceable-fixed-costs"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


def residual_income(seed: int) -> TaskInstance:
    """Numeric: residual income. Trap: answering ROI (a percentage)."""
    rng = random.Random(seed)
    assets = Decimal(rng.randrange(200, 801)) * 1000
    required = rng.choice([Decimal("0.10"), Decimal("0.12"), Decimal("0.15")])
    excess = Decimal(rng.randrange(1, 9)) / 100
    operating_income = assets * (required + excess)
    gold = operating_income - assets * required
    trap = ((operating_income / assets) * 100).quantize(Decimal("0.01"))
    sales = assets * 2
    data = (
        "# Division data — year ended 2025-12-31\n\n| Item | Value |\n|---|---:|\n"
        f"| Sales | USD {money(sales)} |\n"
        f"| Operating income | USD {money(operating_income)} |\n"
        f"| Average operating assets | USD {money(assets)} |\n"
        f"| Minimum required return | {required * 100:.0f}% |\n"
    )
    policy = """# Residual income conventions (applies to this task)

- Residual income = operating income - (average operating assets x
  minimum required return). It is a DOLLAR amount, not a percentage
  (income / assets is ROI, a different measure).
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "residual income",
        "Using `/app/documents/division_data.md` and `/app/policy.md`, compute "
        "the division's **residual income** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="residual-income",
        family="responsibility-accounting",
        title="Compute residual income",
        question=question,
        policy=policy,
        data_name="division_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "residual-income", "required-return"],
        abs_tolerance="0.01",
        trap_value=format(trap, "f"),
    )


def cash_collected_from_customers(seed: int) -> TaskInstance:
    """Numeric: direct-method collections. Trap: accrual sales revenue."""
    rng = random.Random(seed)

    def amt(lo, hi):
        return Decimal(rng.randrange(lo, hi)) * 100

    sales = amt(400, 1201)
    ar_begin, ar_end = amt(40, 181), amt(30, 161)
    if ar_begin == ar_end:
        ar_end += 1000
    gold = sales + ar_begin - ar_end
    data = (
        "# Sales and receivables — year ended 2025-12-31\n\n| Item | USD |\n|---|---:|\n"
        f"| Sales revenue (all on credit) | {money(sales)} |\n"
        f"| Accounts receivable, 2025-01-01 | {money(ar_begin)} |\n"
        f"| Accounts receivable, 2025-12-31 | {money(ar_end)} |\n"
        "\nNo receivables were written off during the year.\n"
    )
    policy = """# Direct-method conventions (applies to this task)

- Cash collected from customers = sales revenue + beginning accounts
  receivable - ending accounts receivable (no write-offs, per the data).
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "cash collected from customers (direct method)",
        "Using `/app/documents/receivables_data.md` and `/app/policy.md`, compute "
        "**cash collected from customers** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="cash-collected-from-customers",
        family="cash-flow-statement",
        title="Compute cash collected from customers",
        question=question,
        policy=policy,
        data_name="receivables_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "cash-flow", "direct-method"],
        abs_tolerance="0.01",
        trap_value=money(sales),
        standards=["asc:230", "ias:7"],
    )


def free_cash_flow(seed: int) -> TaskInstance:
    """Numeric: free cash flow under the stated definition.

    Trap: stopping at operating cash flow minus capital expenditures and
    omitting the dividends the stated definition also deducts.
    """
    rng = random.Random(seed)

    def amt(lo, hi):
        return Decimal(rng.randrange(lo, hi)) * 100

    cfo, capex, dividends = amt(300, 901), amt(60, 251), amt(20, 121)
    gold = cfo - capex - dividends
    trap = cfo - capex
    data = (
        "# Cash flow extracts — year ended 2025-12-31\n\n| Item | USD |\n|---|---:|\n"
        f"| Net cash provided by operating activities | {money(cfo)} |\n"
        f"| Capital expenditures | {money(capex)} |\n"
        f"| Cash dividends paid | {money(dividends)} |\n"
    )
    policy = """# Free cash flow convention (applies to this task)

- For this task, free cash flow = net cash provided by operating
  activities - capital expenditures - cash dividends paid, exactly as
  defined here.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "free cash flow",
        "Using `/app/documents/cash_flow_extracts.md` and `/app/policy.md`, "
        "compute **free cash flow** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="free-cash-flow",
        family="cash-flow-statement",
        title="Compute free cash flow",
        question=question,
        policy=policy,
        data_name="cash_flow_extracts.md",
        data=data,
        gold=gold,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "free-cash-flow"],
        abs_tolerance="0.01",
        trap_value=money(trap),
        standards=["asc:230", "ias:7"],
    )


STATEMENT_IMPACT_OPTIONS = [
    "Assets increase, liabilities increase, equity unchanged",
    "Assets increase, liabilities unchanged, equity increases",
    "Assets decrease, liabilities decrease, equity unchanged",
    "Assets decrease, liabilities unchanged, equity decreases",
    "No change in total assets, liabilities, or equity",
]
STATEMENT_IMPACT_CASES = [
    ("Borrowed cash from the bank on a short-term note.", 0),
    ("Purchased office supplies on credit.", 0),
    ("Performed services for a customer on account.", 1),
    ("Received cash for services performed immediately.", 1),
    ("Paid an accounts payable balance in cash.", 2),
    ("The owner withdrew cash for personal use.", 3),
    ("Paid this month's rent in cash.", 3),
    ("Bought equipment for cash at its purchase price.", 4),
    ("Collected cash on an existing accounts receivable.", 4),
]


def sc_transaction_statement_impact(seed: int) -> TaskInstance:
    """Single-choice: total asset/liability/equity effects of one transaction.

    Traps: an asset exchange (equipment for cash, collection of a
    receivable) leaves totals unchanged; owner withdrawals and expenses
    decrease equity rather than creating a liability.
    """
    rng = random.Random(seed)
    narrative, correct_index = rng.choice(STATEMENT_IMPACT_CASES)
    labels = STATEMENT_IMPACT_OPTIONS.copy()
    rng.shuffle(labels)
    option_ids = ["A", "B", "C", "D", "E"]
    gold = option_ids[labels.index(STATEMENT_IMPACT_OPTIONS[correct_index])]
    options_md = "\n".join(f"- {oid}. {name}" for oid, name in zip(option_ids, labels, strict=True))
    policy = """# Transaction effects (applies to this task)

- Apply Assets = Liabilities + Equity. Revenues increase equity;
  expenses and owner withdrawals/dividends decrease it.
- Exchanging one asset for another of equal carrying amount (buying
  equipment for cash; collecting a receivable) leaves TOTAL assets
  unchanged.
- Borrowing or buying on credit increases both assets and liabilities;
  paying a payable decreases both.
"""
    question = _choice_question(
        "effect on the accounting equation",
        f"Transaction: **{narrative}**\n\nUsing `/app/policy.md`, what is its "
        "immediate effect on TOTAL assets, liabilities, and equity? Select "
        "exactly one option.",
        options_md,
        '"B"',
    )
    return TaskInstance(
        task_id="sc-transaction-statement-impact",
        family="transaction-classification",
        title="Identify a transaction's effect on the accounting equation",
        instruction=(
            "Answer the single-choice question in `/app/question.md` "
            "following `/app/policy.md`. Write your selection to "
            "`/app/answer.json` in the exact format shown in the question."
        ),
        app_files={
            "question.md": question,
            "policy.md": policy,
            "answer.example.json": '{\n  "final_answer": "A",\n  "confidence": 50\n}\n',
        },
        expected=_expected(
            "sc-transaction-statement-impact",
            "transaction-classification",
            seed,
            format="single-choice",
            gold=gold,
            options=option_ids,
            expected_deltas={},
            expected_new_transactions=0,
            expected_period=None,
        ),
        solution_ledger="",
        solution_answer={"final_answer": gold, "confidence": 100},
        keywords=["single-choice", "accounting-equation", "transaction-effects"],
        level="vocational",
        format="single-choice",
        skill="application",
    )


GOODWILL = "Assets:Goodwill"
ACQUISITION_ACCOUNTS = [
    (AR, "Trade receivables acquired"),
    (INVENTORY, "Inventory acquired"),
    (AP, "Trade payables assumed"),
    (GOODWILL, "Goodwill on acquisition"),
]


def business_combination_acquisition(seed: int) -> TaskInstance:
    """Scenario: acquire a business's net assets for cash on Jan 15.

    Oracle: identifiable assets/liabilities at fair value, goodwill for
    consideration in excess of net identifiable assets. Trap: using the
    seller's book values (or pushing the excess into equipment).
    Level V/U/V/U/U/U/U -> university.
    """
    rng = random.Random(seed)
    receivables = Decimal(rng.randrange(30, 121)) * 100
    inventory = Decimal(rng.randrange(80, 241)) * 100
    equipment = Decimal(rng.randrange(150, 451)) * 100
    payables = Decimal(rng.randrange(30, 121)) * 100
    goodwill = Decimal(rng.randrange(40, 161)) * 100
    net_identifiable = receivables + inventory + equipment - payables
    price = net_identifiable + goodwill

    def book(value: Decimal, pct: int) -> Decimal:
        return (value * pct / 100).quantize(CENT)

    opening = price + Decimal("20000.00")
    initial = _ledger_header(opening, ACQUISITION_ACCOUNTS)
    doc = (
        "# Acquisition summary — 2026-01-15\n\n"
        f"Cash consideration paid from checking: USD {money(price)}.\n\n"
        "| Item | Fair value (USD) | Seller book value (USD) |\n|---|---:|---:|\n"
        f"| Accounts receivable | {money(receivables)} | {money(book(receivables, 90))} |\n"
        f"| Inventory | {money(inventory)} | {money(book(inventory, 80))} |\n"
        f"| Equipment | {money(equipment)} | {money(book(equipment, 70))} |\n"
        f"| Accounts payable assumed | {money(payables)} | {money(payables)} |\n"
    )
    policy = POLICY + (
        "- Acquisition method: identifiable assets acquired and liabilities\n"
        "  assumed are recorded at FAIR value at the acquisition date (the\n"
        "  seller's book values are irrelevant). Consideration in excess of\n"
        "  net identifiable assets is goodwill.\n"
    )
    solution = initial + _txn(
        "2026-01-15",
        "Seller",
        "Business acquired for cash",
        [
            (AR, receivables),
            (INVENTORY, inventory),
            ("Assets:Equipment", equipment),
            (GOODWILL, goodwill),
            (AP, -payables),
            (BANK, -price),
        ],
    )
    return TaskInstance(
        task_id="business-combination-acquisition",
        family="business-combinations",
        title="Record a business acquisition and goodwill",
        instruction=(
            "Record the acquisition in `/app/documents/acquisition_summary.md` "
            "in `/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated 2026-01-15; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(ACQUISITION_ACCOUNTS),
            "documents/acquisition_summary.md": doc,
        },
        expected=_expected(
            "business-combination-acquisition",
            "business-combinations",
            seed,
            expected_deltas={
                AR: money(receivables),
                INVENTORY: money(inventory),
                "Assets:Equipment": money(equipment),
                GOODWILL: money(goodwill),
                AP: money(-payables),
                BANK: money(-price),
            },
            expected_new_transactions=[1, 3],
            expected_period=["2026-01-15", "2026-01-15"],
            required_final_balances={GOODWILL: money(goodwill)},
        ),
        solution_ledger=solution,
        difficulty="hard",
        keywords=["business-combination", "goodwill", "fair-value"],
        level="university",
        standards=["asc:805", "ifrs:3"],
    )


CONSOLIDATION_ACCOUNTS = [
    (INVENTORY, "Inventory (combined parent and subsidiary)"),
    (COST_OF_SALES, "Cost of goods sold (combined)"),
]


def consolidation_intercompany_elimination(seed: int) -> TaskInstance:
    """Scenario: eliminate an intercompany sale still wholly in inventory.

    Oracle: debit sales at transfer price, credit COGS at seller cost and
    inventory for unrealized profit. 100% is eliminated even with a
    noncontrolling interest. Trap: eliminating only the parent's 80%.
    Level V/U/U/U/U/U/U -> university.
    """
    rng = random.Random(seed)
    cost = Decimal(rng.randrange(50, 201)) * 100
    markup = Decimal(rng.randrange(10, 81)) * 100
    transfer = cost + markup
    opening = Decimal("20000.00")
    initial = (
        _ledger_header(opening, CONSOLIDATION_ACCOUNTS)
        + _txn(
            "2026-01-01",
            "Combined books",
            "Intercompany sale included in combined sales",
            [("Equity:Opening-Balances", transfer), ("Income:Sales", -transfer)],
        )
        + _txn(
            "2026-01-01",
            "Combined books",
            "Seller cost included in combined cost of goods sold",
            [(COST_OF_SALES, cost), ("Equity:Opening-Balances", -cost)],
        )
        + _txn(
            "2026-01-01",
            "Combined books",
            "Inventory included at transfer price",
            [(INVENTORY, transfer), ("Equity:Opening-Balances", -transfer)],
        )
    )
    doc = (
        "# Consolidation worksheet note — January 2026\n\n"
        f"The parent sold goods costing USD {money(cost)} to its 80%-owned "
        f"subsidiary for USD {money(transfer)}. All the goods remain in the "
        "subsidiary's ending inventory. The combined ledger contains the "
        "sale, the seller's cost, and inventory at transfer price.\n"
    )
    policy = POLICY + (
        "- Consolidation eliminations remove intercompany sales in FULL,\n"
        "  regardless of the ownership percentage: debit sales at the\n"
        "  transfer price, credit cost of goods sold at the seller's cost,\n"
        "  and credit inventory for the unrealized profit on goods unsold.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Consolidation",
        "Eliminate intercompany sale and unrealized profit",
        [("Income:Sales", transfer), (COST_OF_SALES, -cost), (INVENTORY, -markup)],
    )
    return TaskInstance(
        task_id="consolidation-intercompany-elimination",
        family="consolidations",
        title="Eliminate an intercompany inventory sale",
        instruction=(
            "Record the elimination described in `/app/documents/consolidation_note.md` "
            "in `/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated 2026-01-31; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(CONSOLIDATION_ACCOUNTS),
            "documents/consolidation_note.md": doc,
        },
        expected=_expected(
            "consolidation-intercompany-elimination",
            "consolidations",
            seed,
            expected_deltas={
                "Income:Sales": money(transfer),
                COST_OF_SALES: money(-cost),
                INVENTORY: money(-markup),
            },
            expected_new_transactions=[1, 3],
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={
                "Income:Sales": "0.00",
                COST_OF_SALES: "0.00",
                INVENTORY: money(cost),
            },
        ),
        solution_ledger=solution,
        difficulty="hard",
        keywords=["consolidation", "intercompany-elimination", "unrealized-profit"],
        level="university",
        skill="analysis",
        standards=["asc:810", "ifrs:10"],
    )


HELD_FOR_SALE = "Assets:AssetHeldForSale"
HELD_FOR_SALE_ACCOUNTS = DISPOSAL_ACCOUNTS + [
    (HELD_FOR_SALE, "Non-current asset classified as held for sale"),
    (IMPAIRMENT_LOSS, "Write-down to fair value less costs to sell"),
]


def held_for_sale_measurement(seed: int) -> TaskInstance:
    """Scenario (IFRS): equipment meets held-for-sale criteria in January.

    Oracle: remove cost/accumulated depreciation, recognize the held-for
    -sale asset at fair value less costs to sell, and book the shortfall
    as a loss. Trap: reclassifying at carrying amount with no write-down.
    Level V/U/U/U/U/V/U -> university.
    """
    rng = random.Random(seed)
    asset = rng.choice(["delivery vehicle", "packaging machine", "forklift"])
    carrying = Decimal(rng.randrange(40, 121)) * 1000
    acc_dep = Decimal(rng.randrange(20, 71)) * 1000
    cost = carrying + acc_dep
    writedown = Decimal(rng.randrange(3, 21)) * 1000
    fvlcs = carrying - writedown
    costs_to_sell = Decimal(rng.randrange(1, 9)) * 500
    fair_value = fvlcs + costs_to_sell
    opening = Decimal("20000.00")
    initial = _ledger_header(opening, HELD_FOR_SALE_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        f"Opening carrying amount: {asset}",
        [
            ("Assets:Equipment", cost),
            (ACC_DEP, -acc_dep),
            ("Equity:Opening-Balances", acc_dep - cost),
        ],
    )
    doc = (
        f"# Held-for-sale decision — {asset}, 2026-01-20\n\n"
        "Management committed to an active sale plan on 2026-01-20; the "
        "asset is available for immediate sale, is being actively marketed "
        "at a reasonable price, and sale within twelve months is highly "
        f"probable. Cost USD {money(cost)}; accumulated depreciation "
        f"USD {money(acc_dep)}. Fair value USD {money(fair_value)}; expected "
        f"costs to sell USD {money(costs_to_sell)}.\n"
    )
    policy = POLICY + (
        "- When the held-for-sale criteria in the document are met, transfer\n"
        "  the asset out of equipment/accumulated depreciation into\n"
        "  `Assets:AssetHeldForSale` and measure it at the LOWER of carrying\n"
        "  amount and fair value less costs to sell, recognizing any\n"
        "  write-down in profit or loss.\n"
    )
    solution = initial + _txn(
        "2026-01-20",
        "Management",
        f"Classify {asset} as held for sale and write down",
        [
            (ACC_DEP, acc_dep),
            (HELD_FOR_SALE, fvlcs),
            (IMPAIRMENT_LOSS, writedown),
            ("Assets:Equipment", -cost),
        ],
    )
    return TaskInstance(
        task_id="held-for-sale-measurement",
        family="fixed-assets",
        title="Reclassify and measure an asset held for sale (IFRS)",
        instruction=(
            "Record the January entries in `/app/documents/held_for_sale.md` "
            "in `/app/ledger.beancount` under IFRS as stated in "
            "`/app/policy.md`. Append new balanced transactions dated "
            "2026-01-20; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(HELD_FOR_SALE_ACCOUNTS),
            "documents/held_for_sale.md": doc,
        },
        expected=_expected(
            "held-for-sale-measurement",
            "fixed-assets",
            seed,
            expected_deltas={
                ACC_DEP: money(acc_dep),
                HELD_FOR_SALE: money(fvlcs),
                IMPAIRMENT_LOSS: money(writedown),
                "Assets:Equipment": money(-cost),
            },
            expected_new_transactions=[1, 3],
            expected_period=["2026-01-20", "2026-01-20"],
            required_final_balances={
                "Assets:Equipment": "0.00",
                ACC_DEP: "0.00",
                HELD_FOR_SALE: money(fvlcs),
            },
        ),
        solution_ledger=solution,
        difficulty="hard",
        keywords=["held-for-sale", "ifrs-5", "write-down"],
        level="university",
        framework="ifrs",
        standards=["ifrs:5"],
    )


SHARE_COMP = "Expenses:ShareBasedCompensation"
SHARE_COMP_ACCOUNTS = [
    (APIC, "Additional paid-in capital from equity awards"),
    (SHARE_COMP, "Share-based compensation expense"),
]


def share_based_compensation_monthly(seed: int) -> TaskInstance:
    """Scenario: employee options vest straight-line over several years.

    Oracle: January expense is grant-date fair value divided by vesting
    months, credited to APIC. Trap: expensing the entire grant in January.
    Level V/U/V/V/V/V/U -> vocational.
    """
    rng = random.Random(seed)
    years = rng.choice([2, 3, 4])
    months = years * 12
    monthly = Decimal(rng.randrange(50, 401)) * 5
    total = monthly * months
    opening = Decimal("30000.00")
    initial = _ledger_header(opening, SHARE_COMP_ACCOUNTS)
    doc = (
        "# Equity award grant — 2026-01-01\n\n"
        f"Employee stock options with total grant-date fair value "
        f"USD {money(total)} were granted on 2026-01-01. They vest "
        f"straight-line over {years} years of service ({months} months). "
        "No forfeitures are expected; no cash changed hands.\n"
    )
    policy = POLICY + (
        "- Equity-classified share-based compensation is expensed\n"
        "  straight-line over the vesting period at grant-date fair value,\n"
        "  credited to additional paid-in capital.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Compensation committee",
        "January share-based compensation",
        [(SHARE_COMP, monthly), (APIC, -monthly)],
    )
    return TaskInstance(
        task_id="share-based-compensation-monthly",
        family="share-based-payment",
        title="Recognize one month of share-based compensation",
        instruction=(
            "Record January's compensation in `/app/documents/award_grant.md` "
            "in `/app/ledger.beancount`, following `/app/policy.md`. Append "
            "exactly one balanced transaction dated 2026-01-31; do not edit "
            "existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(SHARE_COMP_ACCOUNTS),
            "documents/award_grant.md": doc,
        },
        expected=_expected(
            "share-based-compensation-monthly",
            "share-based-payment",
            seed,
            expected_deltas={SHARE_COMP: money(monthly), APIC: money(-monthly)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={APIC: money(-monthly)},
        ),
        solution_ledger=solution,
        keywords=["share-based-compensation", "vesting", "apic"],
        level="vocational",
        standards=["asc:718", "ifrs:2"],
    )


REVALUATION_SURPLUS = "Equity:RevaluationSurplus"
REVALUATION_ACCOUNTS = DISPOSAL_ACCOUNTS + [
    (REVALUATION_SURPLUS, "Revaluation surplus in other comprehensive income")
]


def asset_revaluation_surplus(seed: int) -> TaskInstance:
    """Scenario (IFRS): equipment is revalued upward on Jan 31.

    Oracle (elimination method stated in policy): accumulated depreciation
    is eliminated against the gross amount, equipment is restated to fair
    value, and the uplift goes to revaluation surplus (OCI), not income.
    Trap: crediting the uplift to profit or loss. Level V/U/U/U/V/U/U.
    """
    rng = random.Random(seed)
    asset = rng.choice(["warehouse building", "production hall", "office building"])
    carrying = Decimal(rng.randrange(100, 301)) * 1000
    acc_dep = Decimal(rng.randrange(30, 121)) * 1000
    cost = carrying + acc_dep
    uplift = Decimal(rng.randrange(20, 121)) * 1000
    fair_value = carrying + uplift
    opening = Decimal("20000.00")
    initial = _ledger_header(opening, REVALUATION_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        f"Opening carrying amount: {asset}",
        [
            ("Assets:Equipment", cost),
            (ACC_DEP, -acc_dep),
            ("Equity:Opening-Balances", acc_dep - cost),
        ],
    )
    doc = (
        f"# Revaluation report — {asset}, 2026-01-31\n\n"
        f"Cost USD {money(cost)}; accumulated depreciation USD {money(acc_dep)} "
        f"(carrying amount USD {money(carrying)}). Independent fair value at "
        f"2026-01-31: USD {money(fair_value)}. The asset class is carried "
        "under the revaluation model.\n"
    )
    policy = POLICY + (
        "- Revaluation increases are recognized in other comprehensive\n"
        "  income (`Equity:RevaluationSurplus`), not profit or loss. Use the\n"
        "  elimination method: eliminate accumulated depreciation against\n"
        "  the asset's gross carrying amount, then restate the asset to\n"
        "  fair value.\n"
    )
    solution = (
        initial
        + _txn(
            "2026-01-31",
            "Valuation",
            "Eliminate accumulated depreciation on revaluation",
            [(ACC_DEP, acc_dep), ("Assets:Equipment", -acc_dep)],
        )
        + _txn(
            "2026-01-31",
            "Valuation",
            "Restate asset to fair value",
            [("Assets:Equipment", uplift), (REVALUATION_SURPLUS, -uplift)],
        )
    )
    return TaskInstance(
        task_id="asset-revaluation-surplus",
        family="fixed-assets",
        title="Record an upward asset revaluation (IFRS)",
        instruction=(
            "Record the revaluation in `/app/documents/revaluation_report.md` "
            "in `/app/ledger.beancount` under IFRS as stated in "
            "`/app/policy.md`. Append new balanced transactions dated "
            "2026-01-31; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(REVALUATION_ACCOUNTS),
            "documents/revaluation_report.md": doc,
        },
        expected=_expected(
            "asset-revaluation-surplus",
            "fixed-assets",
            seed,
            expected_deltas={
                ACC_DEP: money(acc_dep),
                "Assets:Equipment": money(uplift - acc_dep),
                REVALUATION_SURPLUS: money(-uplift),
            },
            expected_new_transactions=[1, 3],
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={
                ACC_DEP: "0.00",
                "Assets:Equipment": money(fair_value),
            },
        ),
        solution_ledger=solution,
        difficulty="hard",
        keywords=["revaluation", "ias-16", "oci"],
        level="university",
        framework="ifrs",
        standards=["ias:16"],
    )


def written_off_receivable_recovery(seed: int) -> TaskInstance:
    """Scenario: a customer whose account was written off pays in full.

    Oracle: reinstate the receivable against the allowance, then record
    the collection. Trap: crediting the recovery directly to revenue.
    Level V/U/V/V/V/V/V -> vocational.
    """
    rng = random.Random(seed)
    customer = rng.choice(["Pine Mart", "Cobalt Retail", "Delta Foods"])
    recovery = Decimal(rng.randrange(10, 81)) * 50
    allowance_open = recovery * rng.randint(2, 4)
    opening = Decimal("20000.00")
    initial = _ledger_header(opening, RECEIVABLE_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        "Opening allowance for doubtful accounts",
        [("Equity:Opening-Balances", allowance_open), (ALLOWANCE, -allowance_open)],
    )
    doc = (
        f"# Recovery notice — {customer}, 2026-01-18\n\n"
        f"This customer's account of USD {money(recovery)} was written off "
        "last year as uncollectible. The customer has now paid the full "
        "amount into checking.\n"
    )
    policy = POLICY + (
        "- A recovery of a written-off account is recorded in two steps:\n"
        "  reinstate the receivable (debit receivables, credit allowance),\n"
        "  then record the cash collection. It is not revenue.\n"
    )
    solution = (
        initial
        + _txn(
            "2026-01-18",
            customer,
            "Reinstate written-off account",
            [(AR, recovery), (ALLOWANCE, -recovery)],
        )
        + _txn(
            "2026-01-18",
            customer,
            "Collect reinstated account",
            [(BANK, recovery), (AR, -recovery)],
        )
    )
    return TaskInstance(
        task_id="written-off-receivable-recovery",
        family="receivables",
        title="Record recovery of a written-off receivable",
        instruction=(
            "Record the recovery in `/app/documents/recovery_notice.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated 2026-01-18; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(RECEIVABLE_ACCOUNTS),
            "documents/recovery_notice.md": doc,
        },
        expected=_expected(
            "written-off-receivable-recovery",
            "receivables",
            seed,
            expected_deltas={
                AR: "0.00",
                ALLOWANCE: money(-recovery),
                BANK: money(recovery),
            },
            expected_new_transactions=[1, 3],
            expected_period=["2026-01-18", "2026-01-18"],
            required_final_balances={ALLOWANCE: money(-(allowance_open + recovery))},
        ),
        solution_ledger=solution,
        keywords=["bad-debt-recovery", "allowance-method", "reinstatement"],
        level="vocational",
    )


PLEDGES = "Assets:PledgesReceivable"
CONTRIBUTION = "Income:ContributionRevenueWithDonorRestrictions"
REFUNDABLE_ADVANCE = "Liabilities:RefundableAdvance"
NFP_ACCOUNTS = [
    (PLEDGES, "Unconditional promises to give receivable"),
    (CONTRIBUTION, "Contribution revenue with donor restrictions"),
    (REFUNDABLE_ADVANCE, "Conditional grant advance refundable until barriers met"),
]


def nfp_conditional_vs_unconditional(seed: int) -> TaskInstance:
    """Scenario: charity receives a restricted pledge and conditional cash.

    Oracle: unconditional pledge is contribution revenue when promised;
    conditional cash advance is a refundable advance liability until the
    barriers are met. Trap: recognizing the conditional grant as revenue.
    Level V/U/V/U/U/V/U -> university.
    """
    rng = random.Random(seed)
    pledge = Decimal(rng.randrange(40, 161)) * 100
    conditional = Decimal(rng.randrange(30, 121)) * 100
    opening = Decimal("20000.00")
    initial = _ledger_header(opening, NFP_ACCOUNTS)
    doc = (
        "# January 2026 donor activity (charity)\n\n"
        f"1. 2026-01-10 — A donor unconditionally pledged USD {money(pledge)}, "
        "payable in March and restricted to the youth program. No barriers "
        "or right of return were imposed.\n"
        f"2. 2026-01-12 — A foundation transferred USD {money(conditional)} in "
        "cash. The charity must serve 500 new clients by year-end and return "
        "any unspent funds if it does not; the barrier has not yet been met.\n"
    )
    policy = POLICY + (
        "- For this not-for-profit, UNCONDITIONAL promises are contribution\n"
        "  revenue (with donor restrictions if purpose-restricted) when\n"
        "  promised. A transfer with a measurable barrier AND a right of\n"
        "  return is conditional: cash received is a refundable advance\n"
        "  liability until the barrier is met.\n"
    )
    solution = (
        initial
        + _txn(
            "2026-01-10",
            "Donor",
            "Unconditional restricted pledge received",
            [(PLEDGES, pledge), (CONTRIBUTION, -pledge)],
        )
        + _txn(
            "2026-01-12",
            "Foundation",
            "Conditional grant advance received",
            [(BANK, conditional), (REFUNDABLE_ADVANCE, -conditional)],
        )
    )
    return TaskInstance(
        task_id="nfp-conditional-vs-unconditional",
        family="not-for-profit",
        title="Distinguish conditional and unconditional contributions",
        instruction=(
            "Record the January donor activity in "
            "`/app/documents/donor_activity.md` in `/app/ledger.beancount`, "
            "following `/app/policy.md`. Append new balanced transactions on "
            "their stated January dates; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(NFP_ACCOUNTS),
            "documents/donor_activity.md": doc,
        },
        expected=_expected(
            "nfp-conditional-vs-unconditional",
            "not-for-profit",
            seed,
            expected_deltas={
                PLEDGES: money(pledge),
                CONTRIBUTION: money(-pledge),
                BANK: money(conditional),
                REFUNDABLE_ADVANCE: money(-conditional),
            },
            expected_new_transactions=[2, 3],
            required_final_balances={REFUNDABLE_ADVANCE: money(-conditional)},
        ),
        solution_ledger=solution,
        difficulty="hard",
        keywords=["not-for-profit", "contributions", "conditional-grant"],
        level="university",
        framework="us-gaap",
        standards=["asc:958"],
    )


def adjusted_receivable_balance(seed: int) -> TaskInstance:
    """Numeric: post a month of receivable activity to an ending balance.

    Trap: forgetting write-offs (or discounts) still reduce receivables.
    """
    rng = random.Random(seed)

    def amt(lo, hi):
        return Decimal(rng.randrange(lo, hi)) * 100

    beginning, credit_sales, collections = amt(80, 301), amt(400, 1001), amt(300, 801)
    returns, writeoffs, discounts = amt(10, 61), amt(5, 36), amt(4, 31)
    gold = beginning + credit_sales - collections - returns - writeoffs - discounts
    while gold <= 0:
        credit_sales += 10000
        gold += 10000
    trap = gold + writeoffs
    data = (
        "# Accounts receivable activity — January 2026\n\n| Item | USD |\n|---|---:|\n"
        f"| Balance, 2026-01-01 (debit) | {money(beginning)} |\n"
        f"| Credit sales | {money(credit_sales)} |\n"
        f"| Cash collections | {money(collections)} |\n"
        f"| Sales returns on credit sales | {money(returns)} |\n"
        f"| Accounts written off | {money(writeoffs)} |\n"
        f"| Sales discounts taken | {money(discounts)} |\n"
    )
    policy = """# Receivable T-account conventions (applies to this task)

- Ending receivables = beginning balance + credit sales - collections
  - sales returns - write-offs - discounts taken. Every listed credit
  item reduces the receivable, including write-offs.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "adjusted accounts receivable balance",
        "Using `/app/documents/receivable_activity.md` and `/app/policy.md`, compute "
        "**accounts receivable at 2026-01-31** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="adjusted-receivable-balance",
        family="receivables",
        title="Post receivable activity to an ending balance",
        question=question,
        policy=policy,
        data_name="receivable_activity.md",
        data=data,
        gold=gold,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "t-account", "receivables-rollforward"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


def ppe_additions_inferred(seed: int) -> TaskInstance:
    """Numeric: infer PPE purchases from the gross rollforward.

    Trap: answering the net increase in gross PPE.
    """
    rng = random.Random(seed)

    def amt(lo, hi):
        return Decimal(rng.randrange(lo, hi)) * 1000

    beginning, disposals, additions = amt(200, 601), amt(20, 121), amt(40, 201)
    ending = beginning + additions - disposals
    trap = ending - beginning
    data = (
        "# Equipment at cost — year ended 2025-12-31\n\n| Item | USD |\n|---|---:|\n"
        f"| Gross equipment, 2025-01-01 | {money(beginning)} |\n"
        f"| Gross equipment, 2025-12-31 | {money(ending)} |\n"
        f"| Cost of equipment disposed of during the year | {money(disposals)} |\n"
    )
    policy = """# PPE rollforward conventions (applies to this task)

- Ending gross PPE = beginning gross PPE + additions at cost - cost of
  assets disposed of. Solve for additions; the net change alone understates
  purchases whenever disposals occurred.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "PPE additions inferred from a rollforward",
        "Using `/app/documents/ppe_rollforward.md` and `/app/policy.md`, compute "
        "**equipment purchases (additions at cost)** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="ppe-additions-inferred",
        family="fixed-assets",
        title="Infer PPE purchases from a rollforward",
        question=question,
        policy=policy,
        data_name="ppe_rollforward.md",
        data=data,
        gold=additions,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "ppe-rollforward", "additions"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


def fixed_overhead_volume_variance(seed: int) -> TaskInstance:
    """Numeric: fixed OH volume variance. Trap: fixed OH spending variance."""
    rng = random.Random(seed)
    rate = Decimal(rng.randrange(4, 16)) * Decimal("2.50")
    denominator_hours = rng.randrange(8000, 20001, 500)
    shortfall = rng.randrange(250, 2001, 250)
    standard_hours = denominator_hours - shortfall
    budgeted = rate * denominator_hours
    actual = budgeted + Decimal(rng.randrange(10, 81)) * 100
    gold = Decimal(shortfall) * rate
    trap = actual - budgeted
    if trap == gold:
        actual += 1000
        trap = actual - budgeted
    data = (
        "# Fixed overhead — January 2026\n\n| Item | Value |\n|---|---:|\n"
        f"| Budgeted fixed overhead | USD {money(budgeted)} |\n"
        f"| Actual fixed overhead | USD {money(actual)} |\n"
        f"| Denominator (budgeted) hours | {denominator_hours} |\n"
        f"| Standard hours allowed for actual output | {standard_hours} |\n"
    )
    policy = """# Fixed overhead variance conventions (applies to this task)

- Fixed overhead rate = budgeted fixed overhead / denominator hours.
- VOLUME variance = budgeted fixed overhead - (fixed rate x standard
  hours allowed). Positive here (allowed below denominator) is
  unfavorable. Actual minus budgeted fixed overhead is the SPENDING
  variance, a different variance.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "fixed overhead volume variance",
        "Using `/app/documents/fixed_overhead.md` and `/app/policy.md`, compute "
        "the **fixed overhead volume variance** in USD (positive = unfavorable).",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="fixed-overhead-volume-variance",
        family="standard-costing",
        title="Compute the fixed overhead volume variance",
        question=question,
        policy=policy,
        data_name="fixed_overhead.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "fixed-overhead", "volume-variance"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


def cumulative_preferred_dividend(seed: int) -> TaskInstance:
    """Numeric: common dividends after cumulative preferred arrears.

    Trap: paying only the current preferred dividend before common.
    """
    rng = random.Random(seed)
    shares = rng.randrange(1000, 8001, 250)
    par = Decimal(rng.choice([50, 100]))
    rate = rng.choice([Decimal("0.06"), Decimal("0.08")])
    annual = shares * par * rate
    arrears_years = rng.choice([1, 2])
    common = Decimal(rng.randrange(50, 401)) * 100
    preferred_due = annual * (arrears_years + 1)
    declared = preferred_due + common
    trap = declared - annual
    data = (
        "# Dividend declaration — 2026\n\n| Item | Value |\n|---|---:|\n"
        f"| Cumulative preferred shares | {shares} |\n"
        f"| Preferred par value | USD {money(par)} per share |\n"
        f"| Preferred dividend rate | {rate * 100:.0f}% of par a year |\n"
        f"| Years of preferred dividends in arrears | {arrears_years} |\n"
        f"| Total dividends declared in 2026 | USD {money(declared)} |\n"
    )
    policy = """# Cumulative preferred conventions (applies to this task)

- Cumulative preferred shareholders must receive all arrears plus the
  current year dividend before common shareholders receive anything.
- Common dividends = total declared - (annual preferred dividend x
  (arrears years + 1)).
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "dividends to common shareholders",
        "Using `/app/documents/dividend_declaration.md` and `/app/policy.md`, "
        "compute **dividends allocated to common shareholders** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="cumulative-preferred-dividend",
        family="equity",
        title="Allocate dividends with cumulative preferred arrears",
        question=question,
        policy=policy,
        data_name="dividend_declaration.md",
        data=data,
        gold=common,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "cumulative-preferred", "dividends-in-arrears"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


def weighted_average_cost_of_capital(seed: int) -> TaskInstance:
    """Numeric: WACC with after-tax debt cost. Trap: pre-tax cost of debt."""
    rng = random.Random(seed)
    debt_weight = rng.choice([30, 40, 50, 60])
    equity_weight = 100 - debt_weight
    pretax = rng.choice([Decimal("0.05"), Decimal("0.06"), Decimal("0.08")])
    tax = rng.choice([Decimal("0.20"), Decimal("0.25"), Decimal("0.30")])
    cost_equity = rng.choice([Decimal("0.10"), Decimal("0.12"), Decimal("0.14")])
    gold = (
        Decimal(debt_weight) * pretax * (1 - tax) + Decimal(equity_weight) * cost_equity
    ).quantize(Decimal("0.0001"))
    trap = (Decimal(debt_weight) * pretax + Decimal(equity_weight) * cost_equity).quantize(
        Decimal("0.0001")
    )
    data = (
        "# Target capital structure and component costs\n\n| Item | Value |\n|---|---:|\n"
        f"| Debt weight (market value) | {debt_weight}% |\n"
        f"| Equity weight (market value) | {equity_weight}% |\n"
        f"| Pre-tax cost of debt | {pretax * 100:.0f}% |\n"
        f"| Cost of equity | {cost_equity * 100:.0f}% |\n"
        f"| Marginal tax rate | {tax * 100:.0f}% |\n"
    )
    policy = """# WACC conventions (applies to this task)

- WACC = debt weight x pre-tax cost of debt x (1 - tax rate)
  + equity weight x cost of equity. Interest is tax-deductible, so the
  debt cost enters after tax.
- Answer as a percentage number (for example 9.60 for 9.60%).
"""
    question = _numeric_question(
        "weighted average cost of capital",
        "Using `/app/documents/capital_structure.md` and `/app/policy.md`, compute "
        "**WACC** as a percentage number.",
        "the percentage number",
    )
    return _numeric_instance(
        task_id="weighted-average-cost-of-capital",
        family="cost-of-capital",
        title="Compute WACC with after-tax debt cost",
        question=question,
        policy=policy,
        data_name="capital_structure.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "wacc", "after-tax-cost-of-debt"],
        abs_tolerance="0.01",
        trap_value=format(trap, "f"),
    )


def standard_cost_per_unit(seed: int) -> TaskInstance:
    """Numeric: build a standard cost card. Trap: using actual input prices."""
    rng = random.Random(seed)
    dm_qty = (Decimal(rng.randrange(2, 9)) / 2).quantize(Decimal("0.5"))
    dm_price = Decimal(rng.randrange(200, 901, 25)) / 100
    dl_hours = (Decimal(rng.randrange(1, 7)) / 2).quantize(Decimal("0.5"))
    dl_rate = Decimal(rng.randrange(1200, 3001, 25)) / 100
    var_rate = Decimal(rng.randrange(200, 801, 25)) / 100
    fixed_rate = Decimal(rng.randrange(300, 1001, 25)) / 100
    gold = dm_qty * dm_price + dl_hours * (dl_rate + var_rate + fixed_rate)
    actual_dm_price = dm_price + Decimal("0.75")
    trap = dm_qty * actual_dm_price + dl_hours * (dl_rate + var_rate + fixed_rate)
    data = (
        "# Standard cost card inputs (per finished unit)\n\n"
        "| Item | Standard | Actual (January) |\n"
        "|---|---:|---:|\n"
        f"| Direct materials | {format(dm_qty, 'f')} units @ USD {money(dm_price)} | "
        f"USD {money(actual_dm_price)} per unit |\n"
        f"| Direct labor | {format(dl_hours, 'f')} hours @ USD {money(dl_rate)} | — |\n"
        f"| Variable overhead | USD {money(var_rate)} per labor hour | — |\n"
        f"| Fixed overhead | USD {money(fixed_rate)} per labor hour | — |\n"
    )
    policy = """# Standard cost conventions (applies to this task)

- A standard cost card uses STANDARD quantities and STANDARD prices for
  every input; actual prices explain variances and never enter the card.
  Overhead applies per standard labor hour.
- Answer in USD per unit in `/app/answer.json`.
"""
    question = _numeric_question(
        "standard cost per unit",
        "Using `/app/documents/cost_card_inputs.md` and `/app/policy.md`, compute "
        "the **standard cost per finished unit** in USD.",
        "the USD amount per unit",
    )
    return _numeric_instance(
        task_id="standard-cost-per-unit",
        family="standard-costing",
        title="Build a standard cost per unit",
        question=question,
        policy=policy,
        data_name="cost_card_inputs.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "standard-cost-card"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


JOB_PROCESS_OPTIONS = ["Job-order costing", "Process costing"]
JOB_PROCESS_CASES = [
    ("A builder constructing custom homes, each to a buyer's design.", "Job-order costing"),
    ("A law firm tracking time and costs by individual client matter.", "Job-order costing"),
    ("A print shop producing distinct customer orders in small batches.", "Job-order costing"),
    ("An oil refinery producing identical fuel in a continuous flow.", "Process costing"),
    ("A soft-drink bottler producing identical cans on a continuous line.", "Process costing"),
    ("A cement plant producing a homogeneous product in bulk.", "Process costing"),
]


def sc_job_vs_process_costing(seed: int) -> TaskInstance:
    """Single-choice: select job-order vs process costing from production type."""
    rng = random.Random(seed)
    narrative, correct = rng.choice(JOB_PROCESS_CASES)
    labels = JOB_PROCESS_OPTIONS.copy()
    rng.shuffle(labels)
    option_ids = ["A", "B"]
    gold = option_ids[labels.index(correct)]
    options_md = "\n".join(f"- {oid}. {name}" for oid, name in zip(option_ids, labels, strict=True))
    policy = """# Product costing system conventions (applies to this task)

- Job-order costing fits distinct, identifiable jobs or batches made to
  order (custom work, client matters, separate customer orders).
- Process costing fits homogeneous products made in a continuous flow,
  where costs are averaged over equivalent units.
"""
    question = _choice_question(
        "job-order or process costing",
        f"Producer: **{narrative}**\n\nUsing `/app/policy.md`, which costing "
        "system fits? Select exactly one option.",
        options_md,
        '"B"',
    )
    return TaskInstance(
        task_id="sc-job-vs-process-costing",
        family="product-costing",
        title="Choose job-order or process costing",
        instruction=(
            "Answer the single-choice question in `/app/question.md` "
            "following `/app/policy.md`. Write your selection to "
            "`/app/answer.json` in the exact format shown in the question."
        ),
        app_files={
            "question.md": question,
            "policy.md": policy,
            "answer.example.json": '{\n  "final_answer": "A",\n  "confidence": 50\n}\n',
        },
        expected=_expected(
            "sc-job-vs-process-costing",
            "product-costing",
            seed,
            format="single-choice",
            gold=gold,
            options=option_ids,
            expected_deltas={},
            expected_new_transactions=0,
            expected_period=None,
        ),
        solution_ledger="",
        solution_answer={"final_answer": gold, "confidence": 100},
        keywords=["single-choice", "job-order", "process-costing"],
        level="vocational",
        category="management-accounting",
        format="single-choice",
        skill="remembering-understanding",
    )


DEFERRED_GRANT = "Liabilities:DeferredGovernmentGrant"
GRANT_INCOME = "Income:GovernmentGrant"
GOV_GRANT_ACCOUNTS = [
    (DEFERRED_GRANT, "Government grant deferred income"),
    (GRANT_INCOME, "Government grant income recognized"),
]


def government_grant_release(seed: int) -> TaskInstance:
    """Scenario (IFRS): asset grant released over the asset's useful life.

    Oracle: one month of the deferred grant (total / life months) to
    income. Trap: recognizing the whole grant in January. Level
    V/U/V/V/V/V/U -> vocational.
    """
    rng = random.Random(seed)
    years = rng.choice([4, 5, 8, 10])
    monthly = Decimal(rng.randrange(50, 301)) * 5
    total = monthly * years * 12
    asset_cost = total * rng.choice([Decimal("1.5"), Decimal("2")])
    opening = asset_cost + Decimal("20000.00")
    initial = (
        _ledger_header(opening, GOV_GRANT_ACCOUNTS)
        + _txn(
            "2026-01-02",
            "Government",
            "Grant received toward equipment purchase",
            [(BANK, total), (DEFERRED_GRANT, -total)],
        )
        + _txn(
            "2026-01-02",
            "Vendor",
            "Equipment purchased and placed in service",
            [("Assets:Equipment", asset_cost), (BANK, -asset_cost)],
        )
    )
    doc = (
        "# Government grant — January 2026\n\n"
        f"A USD {money(total)} grant toward equipment costing "
        f"USD {money(asset_cost)} was received on 2026-01-02. All grant "
        f"conditions have been met. The equipment's useful life is {years} "
        "years from January 2026.\n"
    )
    policy = POLICY + (
        "- Asset-related government grants are deferred income recognized\n"
        "  in profit or loss evenly over the related asset's useful life\n"
        "  (monthly from the month the asset enters service).\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Government grant",
        "January grant income (one month)",
        [(DEFERRED_GRANT, monthly), (GRANT_INCOME, -monthly)],
    )
    return TaskInstance(
        task_id="government-grant-release",
        family="government-grants",
        title="Release one month of an asset government grant",
        instruction=(
            "Record January's grant income in `/app/documents/government_grant.md` "
            "in `/app/ledger.beancount` under IFRS as stated in "
            "`/app/policy.md`. Append exactly one balanced transaction dated "
            "2026-01-31; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(GOV_GRANT_ACCOUNTS),
            "documents/government_grant.md": doc,
        },
        expected=_expected(
            "government-grant-release",
            "government-grants",
            seed,
            expected_deltas={DEFERRED_GRANT: money(monthly), GRANT_INCOME: money(-monthly)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={DEFERRED_GRANT: money(-(total - monthly))},
        ),
        solution_ledger=solution,
        keywords=["government-grant", "deferred-income", "ias-20"],
        level="vocational",
        framework="ifrs",
        standards=["ias:20"],
    )


INVESTMENT_PROPERTY = "Assets:InvestmentProperty"
IP_ACCOUNTS = [
    (INVESTMENT_PROPERTY, "Investment property at fair value (IAS 40)"),
    (UNREALIZED, "Fair-value gain or loss in profit or loss"),
    (AOCI, "Accumulated other comprehensive income"),
]


def investment_property_fair_value(seed: int) -> TaskInstance:
    """Scenario (IFRS): rental property rises in fair value by Jan 31.

    Oracle: gain recognized in profit or loss under the IAS 40 fair-value
    model. Trap: routing it to OCI as if it were a PPE revaluation.
    Level V/U/V/V/U/V/U -> vocational.
    """
    rng = random.Random(seed)
    cost = Decimal(rng.randrange(150, 401)) * 1000
    gain = Decimal(rng.randrange(10, 61)) * 1000
    fair_value = cost + gain
    opening = cost + Decimal("20000.00")
    initial = _ledger_header(opening, IP_ACCOUNTS) + _txn(
        "2026-01-03",
        "Seller",
        "Rental building acquired as investment property",
        [(INVESTMENT_PROPERTY, cost), (BANK, -cost)],
    )
    doc = (
        "# Valuation — rental building, 2026-01-31\n\n"
        f"Acquired 2026-01-03 for USD {money(cost)} to earn rentals. An "
        f"independent valuation at 2026-01-31 puts fair value at "
        f"USD {money(fair_value)}. The company applies the IAS 40 fair-value "
        "model to investment property.\n"
    )
    policy = POLICY + (
        "- Investment property under the fair-value model is remeasured to\n"
        "  fair value at each reporting date with gains and losses in\n"
        "  PROFIT OR LOSS (not OCI). It is not depreciated.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Valuation",
        "Investment property fair-value gain",
        [(INVESTMENT_PROPERTY, gain), (UNREALIZED, -gain)],
    )
    return TaskInstance(
        task_id="investment-property-fair-value",
        family="investment-property",
        title="Remeasure investment property to fair value (IFRS)",
        instruction=(
            "Record the month-end adjustment in `/app/documents/valuation.md` "
            "in `/app/ledger.beancount` under IFRS as stated in "
            "`/app/policy.md`. Append exactly one balanced transaction dated "
            "2026-01-31; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(IP_ACCOUNTS),
            "documents/valuation.md": doc,
        },
        expected=_expected(
            "investment-property-fair-value",
            "investment-property",
            seed,
            expected_deltas={INVESTMENT_PROPERTY: money(gain), UNREALIZED: money(-gain)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={INVESTMENT_PROPERTY: money(fair_value)},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["investment-property", "ias-40", "fair-value-gain"],
        level="vocational",
        framework="ifrs",
        standards=["ias:40"],
    )


GOODWILL_ACCOUNTS = DISPOSAL_ACCOUNTS + [
    (GOODWILL, "Goodwill allocated to the cash-generating unit"),
    (IMPAIRMENT_LOSS, "Impairment loss"),
]


def goodwill_impairment(seed: int) -> TaskInstance:
    """Scenario (IFRS): a CGU's recoverable amount falls below carrying amount.

    Oracle: the shortfall is allocated first to goodwill (shortfall here
    is smaller than goodwill). Trap: writing equipment down first.
    Level V/U/U/U/U/V/U -> university.
    """
    rng = random.Random(seed)
    equipment_cost = Decimal(rng.randrange(100, 251)) * 1000
    acc_dep = Decimal(rng.randrange(20, 81)) * 1000
    equipment_net = equipment_cost - acc_dep
    goodwill = Decimal(rng.randrange(40, 121)) * 1000
    shortfall = Decimal(rng.randrange(5, 36)) * 1000
    if shortfall >= goodwill:
        shortfall = goodwill / 2
    carrying = equipment_net + goodwill
    recoverable = carrying - shortfall
    opening = Decimal("20000.00")
    initial = _ledger_header(opening, GOODWILL_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        "Opening CGU carrying amounts",
        [
            ("Assets:Equipment", equipment_cost),
            (GOODWILL, goodwill),
            (ACC_DEP, -acc_dep),
            ("Equity:Opening-Balances", acc_dep - equipment_cost - goodwill),
        ],
    )
    doc = (
        "# Annual goodwill impairment test — 2026-01-31\n\n"
        f"Cash-generating unit carrying amounts: equipment net "
        f"USD {money(equipment_net)} (cost USD {money(equipment_cost)}, "
        f"accumulated depreciation USD {money(acc_dep)}), goodwill "
        f"USD {money(goodwill)}; total USD {money(carrying)}. Recoverable "
        f"amount of the unit: USD {money(recoverable)}.\n"
    )
    policy = POLICY + (
        "- A CGU impairment loss (carrying amount above recoverable amount)\n"
        "  is allocated FIRST to goodwill; only any excess above the\n"
        "  goodwill balance reduces other assets.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Impairment test",
        "Impair goodwill to recoverable amount",
        [(IMPAIRMENT_LOSS, shortfall), (GOODWILL, -shortfall)],
    )
    return TaskInstance(
        task_id="goodwill-impairment",
        family="business-combinations",
        title="Impair goodwill allocated to a CGU (IFRS)",
        instruction=(
            "Record the impairment in `/app/documents/impairment_test.md` in "
            "`/app/ledger.beancount` under IFRS as stated in "
            "`/app/policy.md`. Append exactly one balanced transaction dated "
            "2026-01-31; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(GOODWILL_ACCOUNTS),
            "documents/impairment_test.md": doc,
        },
        expected=_expected(
            "goodwill-impairment",
            "business-combinations",
            seed,
            expected_deltas={IMPAIRMENT_LOSS: money(shortfall), GOODWILL: money(-shortfall)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={GOODWILL: money(goodwill - shortfall)},
        ),
        solution_ledger=solution,
        difficulty="hard",
        keywords=["goodwill-impairment", "cgu", "ias-36"],
        level="university",
        framework="ifrs",
        standards=["ias:36"],
    )


SUB_INVESTMENT = "Assets:InvestmentInForeignSubsidiary"
FX_TRANSLATION_ACCOUNTS = [
    (SUB_INVESTMENT, "Investment in foreign subsidiary (translated net assets)"),
    (AOCI, "Accumulated OCI — cumulative translation adjustment"),
]


def fx_translation_adjustment(seed: int) -> TaskInstance:
    """Scenario: foreign sub's currency strengthens; translate net assets.

    Oracle: retranslation increase on unchanged FC net assets goes to
    OCI (cumulative translation adjustment), not profit or loss. Trap:
    crediting an FX gain in income. Level V/U/V/U/U/V/U -> university.
    """
    rng = random.Random(seed)
    euros = Decimal(rng.randrange(10, 31)) * 10000
    initial_spot = rng.choice([Decimal("1.05"), Decimal("1.08"), Decimal("1.10"), Decimal("1.12")])
    uplift = Decimal(rng.randrange(2, 11)) / 100
    closing_spot = initial_spot + uplift
    initial_amount = euros * initial_spot
    gain = euros * uplift
    opening = Decimal("20000.00")
    initial = _ledger_header(opening, FX_TRANSLATION_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        "Investment in foreign subsidiary at opening spot",
        [(SUB_INVESTMENT, initial_amount), ("Equity:Opening-Balances", -initial_amount)],
    )
    doc = (
        "# Foreign subsidiary translation — 2026-01-31\n\n"
        f"The subsidiary's functional currency is the euro; its net assets "
        f"were EUR {money(euros)} throughout January (no transactions). "
        f"Spot: USD {initial_spot:.2f} per EUR at 2026-01-01; "
        f"USD {closing_spot:.2f} per EUR at 2026-01-31. Presentation "
        "currency is USD.\n"
    )
    policy = POLICY + (
        "- Translation differences on a foreign operation's net assets are\n"
        "  recognized in other comprehensive income (cumulative translation\n"
        "  adjustment), not in profit or loss.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Translation",
        "Retranslate foreign net assets at closing spot",
        [(SUB_INVESTMENT, gain), (AOCI, -gain)],
    )
    return TaskInstance(
        task_id="fx-translation-adjustment",
        family="foreign-currency",
        title="Record a foreign-operation translation adjustment",
        instruction=(
            "Record the January 31 adjustment in "
            "`/app/documents/fx_translation.md` in `/app/ledger.beancount`, "
            "following `/app/policy.md`. Append exactly one balanced "
            "transaction dated 2026-01-31; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(FX_TRANSLATION_ACCOUNTS),
            "documents/fx_translation.md": doc,
        },
        expected=_expected(
            "fx-translation-adjustment",
            "foreign-currency",
            seed,
            expected_deltas={SUB_INVESTMENT: money(gain), AOCI: money(-gain)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={SUB_INVESTMENT: money(euros * closing_spot)},
        ),
        solution_ledger=solution,
        difficulty="hard",
        keywords=["foreign-currency", "translation", "oci", "cta"],
        level="university",
        standards=["asc:830", "ias:21"],
    )


SALE_LEASEBACK_ACCOUNTS = DISPOSAL_ACCOUNTS + [
    (ROU_ASSET, "Right-of-use asset (leaseback)"),
    (LEASE_LIABILITY, "Lease liability (leaseback)"),
    (DEFERRED, "Deferred revenue (not used for a qualifying sale)"),
]


def sale_and_leaseback_entry(seed: int) -> TaskInstance:
    """Scenario (US GAAP): qualifying sale at fair value with a leaseback.

    Oracle: derecognize the asset, recognize the full sale gain, and book
    the leaseback ROU asset/liability at the stated present value. Trap:
    deferring the gain as if the sale had failed. Level V/U/U/U/U/U/U.
    """
    rng = random.Random(seed)
    carrying = Decimal(rng.randrange(80, 221)) * 1000
    acc_dep = Decimal(rng.randrange(20, 81)) * 1000
    cost = carrying + acc_dep
    gain = Decimal(rng.randrange(10, 61)) * 1000
    proceeds = carrying + gain
    lease_pv = Decimal(rng.randrange(30, 121)) * 1000
    opening = Decimal("20000.00")
    initial = _ledger_header(opening, SALE_LEASEBACK_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        "Opening carrying amount: headquarters building",
        [
            ("Assets:Equipment", cost),
            (ACC_DEP, -acc_dep),
            ("Equity:Opening-Balances", acc_dep - cost),
        ],
    )
    doc = (
        "# Sale and leaseback — 2026-01-15 (US GAAP)\n\n"
        f"The company sold its headquarters building (cost USD {money(cost)}, "
        f"accumulated depreciation USD {money(acc_dep)}) for USD {money(proceeds)} "
        "cash, its fair value, and immediately leased it back. The transfer "
        "qualifies as a sale. Present value of leaseback payments: "
        f"USD {money(lease_pv)}.\n"
    )
    policy = POLICY + (
        "- When a sale-and-leaseback transfer qualifies as a sale at fair\n"
        "  value, the seller-lessee derecognizes the asset, recognizes the\n"
        "  full gain (proceeds above carrying amount), and records the\n"
        "  leaseback right-of-use asset and liability at the stated present\n"
        "  value.\n"
    )
    solution = initial + _txn(
        "2026-01-15",
        "Buyer-lessor",
        "Sale of building and leaseback recognition",
        [
            (BANK, proceeds),
            (ACC_DEP, acc_dep),
            (ROU_ASSET, lease_pv),
            ("Assets:Equipment", -cost),
            (LEASE_LIABILITY, -lease_pv),
            (DISPOSAL, -gain),
        ],
    )
    return TaskInstance(
        task_id="sale-and-leaseback-entry",
        family="leases",
        title="Record a qualifying sale and leaseback (US GAAP)",
        instruction=(
            "Record the transaction in `/app/documents/sale_leaseback.md` in "
            "`/app/ledger.beancount` under US GAAP as stated in "
            "`/app/policy.md`. Append new balanced transactions dated "
            "2026-01-15; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(SALE_LEASEBACK_ACCOUNTS),
            "documents/sale_leaseback.md": doc,
        },
        expected=_expected(
            "sale-and-leaseback-entry",
            "leases",
            seed,
            expected_deltas={
                BANK: money(proceeds),
                ACC_DEP: money(acc_dep),
                ROU_ASSET: money(lease_pv),
                "Assets:Equipment": money(-cost),
                LEASE_LIABILITY: money(-lease_pv),
                DISPOSAL: money(-gain),
            },
            expected_new_transactions=[1, 3],
            expected_period=["2026-01-15", "2026-01-15"],
            required_final_balances={
                "Assets:Equipment": "0.00",
                ROU_ASSET: money(lease_pv),
            },
        ),
        solution_ledger=solution,
        difficulty="hard",
        keywords=["sale-leaseback", "asc-842", "right-of-use"],
        level="university",
        skill="analysis",
        framework="us-gaap",
        standards=["asc:842"],
    )


DEBT_SECURITY = "Assets:DebtSecurities"
CREDIT_ALLOWANCE = "Assets:AllowanceForCreditLosses"
CREDIT_LOSS = "Expenses:CreditLoss"
CECL_ACCOUNTS = [
    (DEBT_SECURITY, "Debt securities at amortized cost"),
    (CREDIT_ALLOWANCE, "Allowance for credit losses (contra-asset)"),
    (CREDIT_LOSS, "Credit loss expense"),
]


def debt_security_credit_loss(seed: int) -> TaskInstance:
    """Scenario: expected credit losses on debt securities rise in January.

    Oracle: top the allowance up to the new expected-credit-loss estimate.
    Trap: providing for the whole fair-value decline (including the
    interest-rate component). Level V/U/V/U/U/V/U -> university.
    """
    rng = random.Random(seed)
    amortized = Decimal(rng.randrange(100, 301)) * 1000
    opening_allowance = Decimal(rng.randrange(2, 11)) * 500
    increase = Decimal(rng.randrange(4, 21)) * 500
    required = opening_allowance + increase
    fv_decline = required + Decimal(rng.randrange(10, 41)) * 500
    opening = amortized + Decimal("20000.00")
    initial = (
        _ledger_header(opening, CECL_ACCOUNTS)
        + _txn(
            "2026-01-02",
            "Broker",
            "Corporate bonds purchased",
            [(DEBT_SECURITY, amortized), (BANK, -amortized)],
        )
        + _txn(
            "2026-01-02",
            "Credit review",
            "Initial allowance for expected credit losses",
            [(CREDIT_LOSS, opening_allowance), (CREDIT_ALLOWANCE, -opening_allowance)],
        )
    )
    doc = (
        "# Credit review — corporate bonds, 2026-01-31\n\n"
        f"Amortized cost USD {money(amortized)}. At January 31 expected credit "
        f"losses are re-estimated at USD {money(required)} in total. The bonds' "
        f"fair value has fallen USD {money(fv_decline)} below amortized cost, "
        "mostly because market interest rates rose.\n"
    )
    policy = POLICY + (
        "- Securities at amortized cost carry an allowance for EXPECTED\n"
        "  CREDIT losses only, adjusted to the current estimate through\n"
        "  credit-loss expense. Fair-value declines caused by interest-rate\n"
        "  movements are not credit losses.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Credit review",
        "Increase allowance to expected credit losses",
        [(CREDIT_LOSS, increase), (CREDIT_ALLOWANCE, -increase)],
    )
    return TaskInstance(
        task_id="debt-security-credit-loss",
        family="investments",
        title="Adjust the credit-loss allowance on debt securities",
        instruction=(
            "Record the January adjustment in `/app/documents/credit_review.md` "
            "in `/app/ledger.beancount`, following `/app/policy.md`. Append "
            "exactly one balanced transaction dated 2026-01-31; do not edit "
            "existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(CECL_ACCOUNTS),
            "documents/credit_review.md": doc,
        },
        expected=_expected(
            "debt-security-credit-loss",
            "investments",
            seed,
            expected_deltas={CREDIT_LOSS: money(increase), CREDIT_ALLOWANCE: money(-increase)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={CREDIT_ALLOWANCE: money(-required)},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["cecl", "credit-losses", "debt-securities"],
        level="university",
        framework="us-gaap",
        standards=["asc:326"],
    )


def _annuity_factor(rate: Decimal, years: int) -> Decimal:
    return sum(Decimal(1) / (1 + rate) ** t for t in range(1, years + 1)).quantize(
        Decimal("0.0001")
    )


def _balances_table(title: str, rows: list[tuple[str, Decimal]]) -> str:
    body = "\n".join(f"| {name} | {money(amount)} |" for name, amount in rows)
    return f"# {title}\n\n| Account | Balance (USD) |\n|---|---:|\n{body}\n"


def trial_balance_debit_total(seed: int) -> TaskInstance:
    """Numeric: extract the debit column total from account balances.

    Trap: treating contra-assets (accumulated depreciation, allowance)
    as debits.
    """
    rng = random.Random(seed)

    def amt(lo, hi):
        return Decimal(rng.randrange(lo, hi)) * 100

    cash, ar, supplies, rent, wages, dividends = (
        amt(100, 301),
        amt(80, 241),
        amt(10, 51),
        amt(30, 101),
        amt(60, 181),
        amt(10, 61),
    )
    acc_dep, allowance, ap, stock, sales, retained = (
        amt(30, 121),
        amt(5, 31),
        amt(50, 161),
        amt(100, 301),
        amt(200, 501),
        amt(80, 241),
    )
    other_debits = cash + ar + supplies + rent + wages + dividends
    credits = acc_dep + allowance + ap + stock + sales + retained
    equipment = credits - other_debits
    while equipment < Decimal("30000"):
        retained += 20000
        credits += 20000
        equipment += 20000
    gold = credits
    trap = gold + acc_dep + allowance
    rows = [
        ("Cash", cash),
        ("Accounts receivable", ar),
        ("Supplies", supplies),
        ("Equipment", equipment),
        ("Accumulated depreciation", acc_dep),
        ("Allowance for doubtful accounts", allowance),
        ("Accounts payable", ap),
        ("Common stock", stock),
        ("Retained earnings", retained),
        ("Sales revenue", sales),
        ("Rent expense", rent),
        ("Wages expense", wages),
        ("Dividends", dividends),
    ]
    rng.shuffle(rows)
    data = _balances_table("Account balances — 2026-01-31", rows)
    policy = NORMAL_BALANCE_POLICY + (
        "\nThe balances above foot to a balanced trial balance. Total debits is "
        "the sum of every debit-balance account.\n"
    )
    question = _numeric_question(
        "trial balance debit total",
        "Using `/app/documents/account_balances.md` and `/app/policy.md`, compute "
        "**total debits** on the trial balance in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="trial-balance-debit-total",
        family="ledger-integrity-reporting",
        title="Extract the trial-balance debit total",
        question=question,
        policy=policy,
        data_name="account_balances.md",
        data=data,
        gold=gold,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "trial-balance", "normal-balances"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


def post_closing_debit_total(seed: int) -> TaskInstance:
    """Numeric: post-closing debit total excludes temporary accounts.

    Trap: answering the pre-closing debit total (temporary debits remain).
    """
    rng = random.Random(seed)

    def amt(lo, hi):
        return Decimal(rng.randrange(lo, hi)) * 100

    cash, ar, inventory, equipment, treasury = (
        amt(80, 241),
        amt(60, 201),
        amt(70, 221),
        amt(200, 501),
        amt(10, 61),
    )
    permanent_debits = cash + ar + inventory + equipment + treasury
    acc_dep, ap, stock, retained = amt(40, 141), amt(50, 171), amt(100, 301), amt(80, 241)
    permanent_credits = acc_dep + ap + stock + retained
    expenses, dividends = amt(150, 401), amt(10, 61)
    temporary_debits = expenses + dividends
    sales = permanent_debits + temporary_debits - permanent_credits
    while sales < Decimal("20000"):
        retained += 20000
        permanent_credits += 20000
        sales -= 20000
        equipment += 40000
        permanent_debits += 40000
        sales += 40000
    rows = [
        ("Cash", cash),
        ("Accounts receivable", ar),
        ("Inventory", inventory),
        ("Equipment", equipment),
        ("Treasury stock", treasury),
        ("Accumulated depreciation", acc_dep),
        ("Accounts payable", ap),
        ("Common stock", stock),
        ("Retained earnings (beginning)", retained),
        ("Sales revenue", sales),
        ("Operating expenses", expenses),
        ("Dividends", dividends),
    ]
    rng.shuffle(rows)
    data = _balances_table("Pre-closing balances — 2025-12-31", rows)
    policy = """# Closing conventions (applies to this task)

- Temporary accounts (revenues, expenses, dividends) are closed to zero
  and do not appear on the post-closing trial balance.
- Permanent accounts carry forward: assets (including Treasury stock as
  a debit contra-equity account), contra-assets (credits), liabilities,
  share capital, and retained earnings.
- Post-closing total debits is the sum of permanent DEBIT balances only.
"""
    question = _numeric_question(
        "post-closing trial balance debit total",
        "Using `/app/documents/preclosing_balances.md` and `/app/policy.md`, "
        "compute **post-closing trial balance total debits** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="post-closing-debit-total",
        family="ledger-integrity-reporting",
        title="Compute the post-closing debit total",
        question=question,
        policy=policy,
        data_name="preclosing_balances.md",
        data=data,
        gold=permanent_debits,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "post-closing-trial-balance", "permanent-accounts"],
        abs_tolerance="0.01",
        trap_value=money(permanent_debits + temporary_debits),
    )


def adjusted_wage_expense(seed: int) -> TaskInstance:
    """Numeric: convert cash wages paid to accrual wage expense.

    Trap: answering cash paid.
    """
    rng = random.Random(seed)

    def amt(lo, hi):
        return Decimal(rng.randrange(lo, hi)) * 100

    paid, beginning, ending = amt(300, 801), amt(20, 101), amt(25, 121)
    if beginning == ending:
        ending += 1000
    gold = paid + ending - beginning
    data = (
        "# Wages data — January 2026\n\n| Item | USD |\n|---|---:|\n"
        f"| Cash wages paid | {money(paid)} |\n"
        f"| Wages payable, 2026-01-01 | {money(beginning)} |\n"
        f"| Wages payable, 2026-01-31 | {money(ending)} |\n"
    )
    policy = """# Accrual conversion conventions (applies to this task)

- Wage expense = cash wages paid + ending wages payable - beginning
  wages payable. The beginning balance was expensed last period; the
  ending balance was earned (expensed) this period but is unpaid.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "accrual wage expense",
        "Using `/app/documents/wages_data.md` and `/app/policy.md`, compute "
        "**January wage expense** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="adjusted-wage-expense",
        family="adjustments-corrections",
        title="Convert cash wages paid to wage expense",
        question=question,
        policy=policy,
        data_name="wages_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "accrual-conversion", "wages-payable"],
        abs_tolerance="0.01",
        trap_value=money(paid),
    )


def inventory_method_profit_difference(seed: int) -> TaskInstance:
    """Numeric: FIFO gross profit minus LIFO gross profit in rising costs.

    Trap: answering one method's cost of goods sold instead of the gap.
    """
    rng = random.Random(seed)
    q0 = rng.randrange(100, 401, 25)
    q1 = rng.randrange(150, 501, 25)
    q2 = rng.randrange(150, 501, 25)
    c0 = Decimal(rng.randrange(800, 1801, 25)) / 100
    c1 = c0 + Decimal(rng.randrange(100, 401, 25)) / 100
    c2 = c1 + Decimal(rng.randrange(100, 401, 25)) / 100
    total_units = q0 + q1 + q2
    ending = rng.randrange(q0 // 2, q0 + q1, 25)
    sold = total_units - ending

    def take_value(layers, units):
        value, left = Decimal("0"), units
        for qty, cost in layers:
            take = min(qty, left)
            value += take * cost
            left -= take
            if left == 0:
                break
        return value

    layers = [(q0, c0), (q1, c1), (q2, c2)]
    available = sum(q * c for q, c in layers)
    lifo_ending = take_value(layers, ending)
    fifo_ending = take_value(list(reversed(layers)), ending)
    fifo_cogs = available - fifo_ending
    gold = fifo_ending - lifo_ending
    data = (
        "# Inventory layers — January 2026 (costs rising)\n\n"
        "| Layer | Units | Unit cost (USD) |\n|---|---:|---:|\n"
        f"| Beginning inventory | {q0} | {money(c0)} |\n"
        f"| First purchase | {q1} | {money(c1)} |\n"
        f"| Second purchase | {q2} | {money(c2)} |\n\n"
        f"Units sold: {sold}. Units on hand at month-end: {ending}. "
        "Periodic inventory system under each method.\n"
    )
    policy = """# FIFO/LIFO profit comparison (applies to this task)

- With the same sales revenue, FIFO gross profit - LIFO gross profit
  = LIFO cost of goods sold - FIFO cost of goods sold
  = FIFO ending inventory - LIFO ending inventory.
- Periodic FIFO charges the earliest costs to COGS; periodic LIFO
  charges the latest costs. Answer in USD.
"""
    question = _numeric_question(
        "FIFO versus LIFO gross profit",
        "Using `/app/documents/inventory_layers.md` and `/app/policy.md`, compute "
        "**FIFO gross profit minus LIFO gross profit** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="inventory-method-profit-difference",
        family="inventory",
        title="Compute the FIFO/LIFO gross-profit difference",
        question=question,
        policy=policy,
        data_name="inventory_layers.md",
        data=data,
        gold=gold,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "fifo", "lifo", "gross-profit-impact"],
        abs_tolerance="0.01",
        trap_value=money(fifo_cogs),
    )


def minimum_transfer_price(seed: int) -> TaskInstance:
    """Numeric: minimum transfer price at full capacity.

    Trap: variable production cost only (ignores lost external margin).
    """
    rng = random.Random(seed)
    production_vc = Decimal(rng.randrange(800, 2501, 25)) / 100
    saved_selling = Decimal(rng.randrange(100, 501, 25)) / 100
    external_margin = Decimal(rng.randrange(500, 2001, 25)) / 100
    external_price = production_vc + saved_selling + external_margin
    gold = external_price - saved_selling
    data = (
        "# Selling division data (per unit)\n\n| Item | USD |\n|---|---:|\n"
        f"| Variable production cost | {money(production_vc)} |\n"
        f"| Variable selling cost on external sales | {money(saved_selling)} |\n"
        f"| External selling price | {money(external_price)} |\n\n"
        "The selling division is operating at full capacity; every internal "
        "unit displaces an external sale. The variable selling cost is not "
        "incurred on internal transfers.\n"
    )
    policy = """# Transfer pricing conventions (applies to this task)

- Minimum transfer price = incremental variable cost of the internal
  sale + opportunity cost per unit. At full capacity the opportunity
  cost is the lost external contribution margin (external price minus
  all variable costs of an external sale), so the minimum equals the
  external price less variable costs saved internally.
- Answer in USD per unit.
"""
    question = _numeric_question(
        "minimum transfer price at full capacity",
        "Using `/app/documents/transfer_data.md` and `/app/policy.md`, compute "
        "the **minimum transfer price per unit** in USD.",
        "the USD amount per unit",
    )
    return _numeric_instance(
        task_id="minimum-transfer-price",
        family="responsibility-accounting",
        title="Compute the minimum transfer price",
        question=question,
        policy=policy,
        data_name="transfer_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "transfer-pricing", "opportunity-cost"],
        abs_tolerance="0.01",
        trap_value=money(production_vc),
    )


def debt_modification_percent_change(seed: int) -> TaskInstance:
    """Numeric: 10% cash-flow test percentage for a debt modification.

    Trap: comparing face amounts instead of present values at the
    original effective rate.
    """
    rng = random.Random(seed)
    pct = rng.choice(
        [Decimal("7.50"), Decimal("9.00"), Decimal("11.50"), Decimal("12.50"), Decimal("14.00")]
    )
    old_pv = Decimal(rng.randrange(100, 401)) * 1000
    new_pv = (old_pv * (100 - pct) / 100).quantize(CENT)
    old_face = old_pv + Decimal(rng.randrange(10, 51)) * 1000
    new_face = old_face - Decimal(rng.randrange(0, 21)) * 1000
    trap = ((old_face - new_face) / old_face * 100).quantize(Decimal("0.0001"))
    if abs(trap - pct) <= Decimal("0.01"):
        trap += Decimal("1")
    data = (
        "# Debt modification analysis\n\n| Item | USD |\n|---|---:|\n"
        f"| PV of remaining cash flows, original terms | {money(old_pv)} |\n"
        f"| PV of cash flows, modified terms | {money(new_pv)} |\n"
        f"| Face amount, original debt | {money(old_face)} |\n"
        f"| Face amount, modified debt | {money(new_face)} |\n\n"
        "Both present values use the original effective interest rate and "
        "include fees paid net of fees received.\n"
    )
    policy = """# Debt modification test (applies to this task)

- Percentage change = |PV under modified terms - PV under original
  terms| / PV under original terms x 100, both discounted at the
  ORIGINAL effective rate. Face amounts are not used in the test.
- Answer as a percentage number (for example 12.50 for 12.50%).
"""
    question = _numeric_question(
        "debt modification cash-flow change",
        "Using `/app/documents/debt_modification.md` and `/app/policy.md`, "
        "compute the **percentage change in present value**.",
        "the percentage number",
    )
    return _numeric_instance(
        task_id="debt-modification-percent-change",
        family="borrowings",
        title="Compute the debt-modification PV percentage change",
        question=question,
        policy=policy,
        data_name="debt_modification.md",
        data=data,
        gold=pct,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "debt-modification", "ten-percent-test"],
        abs_tolerance="0.01",
        trap_value=format(trap, "f"),
        standards=["asc:470-50", "ifrs:9"],
    )


TEMPORARY_POLICY = """# Temporary and permanent accounts (applies to this task)

- TEMPORARY (closed to zero each period): revenues, expenses, gains,
  losses, dividends/drawings, and the income summary.
- PERMANENT (carried forward): assets, contra-assets, liabilities,
  share capital, additional paid-in capital, retained earnings, and
  Treasury stock.
"""


def mc_temporary_accounts(seed: int) -> TaskInstance:
    """Multiple-choice: select every temporary (closed) account.

    Traps: dividends look like equity but are temporary, and the
    allowance/accumulated depreciation look like adjustments but are
    permanent contra-assets. Level: policy states the classes.
    """
    rng = random.Random(seed)
    pool: list[tuple[str, bool]] = [
        ("Sales revenue", True),
        ("Cost of goods sold", True),
        ("Rent expense", True),
        ("Dividends", True),
        ("Income summary", True),
        ("Gain on disposal", True),
        ("Cash", False),
        ("Accounts payable", False),
        ("Common stock", False),
        ("Retained earnings", False),
        ("Accumulated depreciation", False),
        ("Treasury stock", False),
    ]
    rng.shuffle(pool)
    chosen = pool[:8]
    option_ids = ["A", "B", "C", "D", "E", "F", "G", "H"]
    gold = sorted(oid for oid, (_, is_temp) in zip(option_ids, chosen, strict=True) if is_temp)
    options_md = "\n".join(
        f"- {oid}. {name} is a TEMPORARY account."
        for oid, (name, _) in zip(option_ids, chosen, strict=True)
    )
    question = _choice_question(
        "temporary accounts",
        "Using `/app/policy.md`, select **all** statements that are true. "
        "Incorrect selections are penalized.",
        options_md,
        '["A", "C"]',
    )
    return TaskInstance(
        task_id="mc-temporary-accounts",
        family="ledger-integrity-reporting",
        title="Select the temporary accounts",
        instruction=(
            "Answer the multiple-choice question in `/app/question.md` "
            "following `/app/policy.md`. Write your selection to "
            "`/app/answer.json` in the exact format shown in the question."
        ),
        app_files={
            "question.md": question,
            "policy.md": TEMPORARY_POLICY,
            "chart_of_accounts.md": _chart_md(),
            "answer.example.json": '{\n  "final_answer": ["A"],\n  "confidence": 50\n}\n',
        },
        expected=_expected(
            "mc-temporary-accounts",
            "ledger-integrity-reporting",
            seed,
            format="multiple-choice",
            gold=gold,
            options=option_ids,
            expected_deltas={},
            expected_new_transactions=0,
            expected_period=None,
        ),
        solution_ledger="",
        solution_answer={"final_answer": gold, "confidence": 100},
        keywords=["multiple-choice", "temporary-accounts", "closing"],
        level="vocational",
        format="multiple-choice",
        skill="remembering-understanding",
    )


FV_LEVELS = ["Level 1", "Level 2", "Level 3"]
FV_CASES = [
    (
        "Shares of a listed company valued at the unadjusted quoted price "
        "on an active stock exchange.",
        "Level 1",
    ),
    (
        "An exchange-traded futures contract valued at its quoted "
        "settlement price in an active market.",
        "Level 1",
    ),
    (
        "A plain-vanilla interest-rate swap valued from an observable yield curve.",
        "Level 2",
    ),
    (
        "Corporate bonds valued using quoted prices for similar bonds and "
        "observable credit spreads.",
        "Level 2",
    ),
    (
        "An unlisted startup investment valued from management's own "
        "cash-flow forecasts and an unobservable growth rate.",
        "Level 3",
    ),
    (
        "A bespoke structured note valued with internally modelled, "
        "unobservable default correlations.",
        "Level 3",
    ),
]


def sc_fair_value_hierarchy(seed: int) -> TaskInstance:
    """Single-choice: classify a valuation into the fair-value hierarchy."""
    rng = random.Random(seed)
    narrative, correct = rng.choice(FV_CASES)
    labels = FV_LEVELS.copy()
    rng.shuffle(labels)
    option_ids = ["A", "B", "C"]
    gold = option_ids[labels.index(correct)]
    options_md = "\n".join(f"- {oid}. {name}" for oid, name in zip(option_ids, labels, strict=True))
    policy = """# Fair-value hierarchy (applies to this task)

- Level 1: unadjusted quoted prices in active markets for IDENTICAL
  assets or liabilities.
- Level 2: other observable inputs, including quoted prices for similar
  items and market-corroborated curves.
- Level 3: significant UNOBSERVABLE inputs based on the entity's own
  assumptions and models.
"""
    question = _choice_question(
        "fair-value hierarchy level",
        f"Valuation: **{narrative}**\n\nUsing `/app/policy.md`, which level "
        "applies? Select exactly one option.",
        options_md,
        '"B"',
    )
    return TaskInstance(
        task_id="sc-fair-value-hierarchy",
        family="fair-value-measurement",
        title="Classify a fair-value measurement",
        instruction=(
            "Answer the single-choice question in `/app/question.md` "
            "following `/app/policy.md`. Write your selection to "
            "`/app/answer.json` in the exact format shown in the question."
        ),
        app_files={
            "question.md": question,
            "policy.md": policy,
            "answer.example.json": '{\n  "final_answer": "A",\n  "confidence": 50\n}\n',
        },
        expected=_expected(
            "sc-fair-value-hierarchy",
            "fair-value-measurement",
            seed,
            format="single-choice",
            gold=gold,
            options=option_ids,
            expected_deltas={},
            expected_new_transactions=0,
            expected_period=None,
        ),
        solution_ledger="",
        solution_answer={"final_answer": gold, "confidence": 100},
        keywords=["single-choice", "fair-value-hierarchy", "level-1-2-3"],
        level="vocational",
        format="single-choice",
        skill="remembering-understanding",
        standards=["asc:820", "ifrs:13"],
    )


DTA = "Assets:DeferredTaxAsset"
TAX_EXPENSE = "Expenses:IncomeTax"
TAX_PAYABLE = "Liabilities:IncomeTaxPayable"
DEFERRED_TAX_ACCOUNTS = [
    (DTA, "Deferred tax asset (future deductible amounts)"),
    (TAX_EXPENSE, "Income tax expense (current and deferred)"),
    (TAX_PAYABLE, "Income taxes currently payable"),
]


def deferred_tax_asset_warranty(seed: int) -> TaskInstance:
    """Scenario: warranty expense is deductible only when claims are paid.

    Oracle: total tax expense = current tax payable less the deferred tax
    benefit on the new deductible temporary difference. Trap: recording
    only current tax. Level V/U/U/U/U/V/U -> university.
    """
    rng = random.Random(seed)
    warranty = Decimal(rng.randrange(40, 161)) * 1000
    rate = rng.choice([Decimal("0.20"), Decimal("0.25"), Decimal("0.30")])
    dta = warranty * rate
    taxable = Decimal(rng.randrange(200, 601)) * 1000
    current_tax = taxable * rate
    total_expense = current_tax - dta
    opening = Decimal("50000.00")
    initial = _ledger_header(opening, DEFERRED_TAX_ACCOUNTS)
    doc = (
        "# Income-tax provision data — January 2026\n\n"
        f"Taxable income for the month: USD {money(taxable)}. Enacted rate: "
        f"{rate * 100:.0f}%. January book profit already deducted warranty "
        f"expense of USD {money(warranty)}; for tax, warranty costs are "
        "deductible only when claims are paid in a later period. No claims "
        "were paid in January.\n"
    )
    policy = POLICY + (
        "- A deductible temporary difference (expensed for books now,\n"
        "  deductible for tax later) creates a deferred tax asset at the\n"
        "  enacted rate. Income-tax expense = current tax payable on\n"
        "  taxable income less the increase in the deferred tax asset.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Tax provision",
        "Current and deferred income tax",
        [(TAX_EXPENSE, total_expense), (DTA, dta), (TAX_PAYABLE, -current_tax)],
    )
    return TaskInstance(
        task_id="deferred-tax-asset-warranty",
        family="income-taxes",
        title="Recognize a deferred tax asset on warranty accruals",
        instruction=(
            "Record January's tax provision in `/app/documents/tax_provision.md` "
            "in `/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated 2026-01-31; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(DEFERRED_TAX_ACCOUNTS),
            "documents/tax_provision.md": doc,
        },
        expected=_expected(
            "deferred-tax-asset-warranty",
            "income-taxes",
            seed,
            expected_deltas={
                TAX_EXPENSE: money(total_expense),
                DTA: money(dta),
                TAX_PAYABLE: money(-current_tax),
            },
            expected_new_transactions=[1, 3],
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={DTA: money(dta)},
        ),
        solution_ledger=solution,
        difficulty="hard",
        keywords=["deferred-tax", "temporary-difference", "warranty"],
        level="university",
        category="tax",
        standards=["asc:740", "ias:12"],
    )


COMMISSION = "Expenses:Commission"
CONSIGNMENT_ACCOUNTS = MERCH_ACCOUNTS + [(COMMISSION, "Consignment commission expense")]


def consignment_sale_recognition(seed: int) -> TaskInstance:
    """Scenario: consignee sells part of the consigned goods in January.

    Oracle (consignor's books): revenue at the gross selling price when
    the consignee sells, commission expensed, cost relieved only for the
    units sold; unsold units remain the consignor's inventory. Trap:
    treating shipment (or the net remittance) as the sale.
    Level V/U/U/U/U/V/U -> university.
    """
    rng = random.Random(seed)
    item = rng.choice(["handmade quilts", "ceramic vases", "wooden toys"])
    shipped = rng.randrange(60, 141, 10)
    sold = rng.randrange(20, shipped - 10, 5)
    unit_cost = Decimal(rng.randrange(1000, 3001, 25)) / 100
    price = (unit_cost * Decimal("2")).quantize(CENT)
    commission_pct = rng.choice([10, 15, 20])
    revenue = sold * price
    commission = (revenue * commission_pct / 100).quantize(CENT)
    remittance = revenue - commission
    cost_sold = sold * unit_cost
    opening = Decimal("20000.00")
    initial = _ledger_header(opening, CONSIGNMENT_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        f"Goods held on consignment at Gallery North: {shipped} {item}",
        [(INVENTORY, shipped * unit_cost), ("Equity:Opening-Balances", -shipped * unit_cost)],
    )
    doc = (
        "# Consignee report — Gallery North, January 2026\n\n"
        f"Of the {shipped} {item} held on consignment, the gallery sold "
        f"{sold} units at USD {money(price)} each, withheld its "
        f"{commission_pct}% commission, and remitted USD {money(remittance)} "
        "to checking on 2026-01-28. The remaining units are still held by "
        "the gallery unsold.\n"
    )
    policy = POLICY + (
        "- Consigned goods remain the consignor's inventory until the\n"
        "  consignee sells them. Revenue is recognized at the gross selling\n"
        "  price on the consignee's sale; the commission is an expense and\n"
        "  cost is relieved only for units sold.\n"
    )
    solution = (
        initial
        + _txn(
            "2026-01-28",
            "Gallery North",
            "Consignment sales remitted net of commission",
            [(BANK, remittance), (COMMISSION, commission), ("Income:Sales", -revenue)],
        )
        + _txn(
            "2026-01-28",
            "Gallery North",
            "Cost of consigned goods sold",
            [(COST_OF_SALES, cost_sold), (INVENTORY, -cost_sold)],
        )
    )
    return TaskInstance(
        task_id="consignment-sale-recognition",
        family="revenue-recognition",
        title="Recognize consignment sales on the consignor's books",
        instruction=(
            "Record the January activity in `/app/documents/consignee_report.md` "
            "in `/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated 2026-01-28; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(CONSIGNMENT_ACCOUNTS),
            "documents/consignee_report.md": doc,
        },
        expected=_expected(
            "consignment-sale-recognition",
            "revenue-recognition",
            seed,
            expected_deltas={
                BANK: money(remittance),
                COMMISSION: money(commission),
                "Income:Sales": money(-revenue),
                COST_OF_SALES: money(cost_sold),
                INVENTORY: money(-cost_sold),
            },
            expected_new_transactions=[1, 3],
            expected_period=["2026-01-28", "2026-01-28"],
            required_final_balances={INVENTORY: money((shipped - sold) * unit_cost)},
        ),
        solution_ledger=solution,
        difficulty="hard",
        keywords=["consignment", "revenue-recognition", "commission"],
        level="university",
        skill="analysis",
        standards=["asc:606", "ifrs:15"],
    )


MINE_ASSET = "Assets:MineralDeposit"
ACC_DEPLETION = "Assets:AccumulatedDepletion"
ORE_INVENTORY = "Assets:OreInventory"
DEPLETION_ACCOUNTS = [
    (MINE_ASSET, "Mineral deposit at cost"),
    (ACC_DEPLETION, "Accumulated depletion (contra-asset)"),
    (ORE_INVENTORY, "Extracted ore inventory"),
    (COST_OF_SALES, "Cost of ore sold"),
]


def natural_resource_depletion(seed: int) -> TaskInstance:
    """Scenario: ore extracted in January, only part of it sold.

    Oracle: deplete the deposit for ALL tons extracted into ore
    inventory, then expense only the tons sold. Trap: depleting (or
    expensing) only the sold tons so the asset/inventory split is wrong.
    Level V/U/V/V/V/V/U -> vocational.
    """
    rng = random.Random(seed)
    rate = (Decimal(rng.randrange(200, 801, 25)) / 100).quantize(CENT)
    total_tons = rng.randrange(50000, 160001, 5000)
    residual = Decimal(rng.randrange(10, 61)) * 1000
    cost = rate * total_tons + residual
    extracted = rng.randrange(2000, 9001, 250)
    sold = rng.randrange(1000, extracted - 250, 250)
    depletion_total = rate * extracted
    cogs = rate * sold
    ore_left = depletion_total - cogs
    opening = Decimal("30000.00")
    initial = _ledger_header(opening, DEPLETION_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        "Mineral deposit opening balance",
        [(MINE_ASSET, cost), ("Equity:Opening-Balances", -cost)],
    )
    doc = (
        "# Mine production report — January 2026\n\n"
        f"Deposit cost USD {money(cost)}; expected residual land value "
        f"USD {money(residual)}; estimated recoverable {total_tons} tons. "
        f"January: {extracted} tons extracted, of which {sold} tons were "
        "sold; the rest is ore inventory on hand.\n"
    )
    policy = POLICY + (
        "- Depletion per ton = (cost - residual value) / estimated tons.\n"
        "  Depletion on tons EXTRACTED is debited to ore inventory; the\n"
        "  portion for tons SOLD moves to cost of goods sold.\n"
    )
    solution = (
        initial
        + _txn(
            "2026-01-31",
            "Mine",
            f"Depletion on {extracted} tons extracted",
            [(ORE_INVENTORY, depletion_total), (ACC_DEPLETION, -depletion_total)],
        )
        + _txn(
            "2026-01-31",
            "Mine",
            f"Cost of {sold} tons sold",
            [(COST_OF_SALES, cogs), (ORE_INVENTORY, -cogs)],
        )
    )
    return TaskInstance(
        task_id="natural-resource-depletion",
        family="fixed-assets",
        title="Deplete a mineral deposit and cost ore sold",
        instruction=(
            "Record January depletion in `/app/documents/mine_report.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated 2026-01-31; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(DEPLETION_ACCOUNTS),
            "documents/mine_report.md": doc,
        },
        expected=_expected(
            "natural-resource-depletion",
            "fixed-assets",
            seed,
            expected_deltas={
                ORE_INVENTORY: money(ore_left),
                ACC_DEPLETION: money(-depletion_total),
                COST_OF_SALES: money(cogs),
            },
            expected_new_transactions=[1, 3],
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={
                ORE_INVENTORY: money(ore_left),
                ACC_DEPLETION: money(-depletion_total),
            },
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["depletion", "natural-resources", "units-of-production"],
        level="vocational",
    )


SOFTWARE_ASSET = "Assets:InternalUseSoftware"
SOFTWARE_EXPENSE = "Expenses:SoftwareProject"
SOFTWARE_ACCOUNTS = [
    (SOFTWARE_ASSET, "Capitalized internal-use software (application stage)"),
    (SOFTWARE_EXPENSE, "Software project expense"),
]


def internal_use_software_costs(seed: int) -> TaskInstance:
    """Scenario (US GAAP): January internal-use software project costs.

    Oracle: preliminary-stage and post-implementation training costs are
    expensed; application-development coding/configuration capitalize.
    Trap: capitalizing every project cost. Level V/U/V/U/U/V/U.
    """
    rng = random.Random(seed)
    preliminary = Decimal(rng.randrange(20, 81)) * 50
    coding = Decimal(rng.randrange(60, 201)) * 50
    configuration = Decimal(rng.randrange(30, 121)) * 50
    training = Decimal(rng.randrange(10, 41)) * 25
    capitalized = coding + configuration
    expensed = preliminary + training
    total = capitalized + expensed
    opening = total + Decimal("20000.00")
    initial = _ledger_header(opening, SOFTWARE_ACCOUNTS)
    doc = (
        "# Internal-use software project — January 2026 (all paid from checking)\n\n"
        "| Cost | USD |\n|---|---:|\n"
        f"| Vendor evaluation and formulation (preliminary) | {money(preliminary)} |\n"
        f"| Application coding (development stage) | {money(coding)} |\n"
        f"| Configuration and interfaces (development stage) | {money(configuration)} |\n"
        f"| User training after go-live | {money(training)} |\n"
    )
    policy = POLICY + (
        "- Internal-use software (US GAAP stages): preliminary-project-stage\n"
        "  and post-implementation training costs are expensed; external\n"
        "  application-development-stage coding and configuration costs are\n"
        "  capitalized.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Software project",
        "January internal-use software costs",
        [(SOFTWARE_ASSET, capitalized), (SOFTWARE_EXPENSE, expensed), (BANK, -total)],
    )
    return TaskInstance(
        task_id="internal-use-software-costs",
        family="intangible-assets",
        title="Capitalize application-stage software costs",
        instruction=(
            "Record the January costs in `/app/documents/software_project.md` "
            "in `/app/ledger.beancount` under US GAAP as stated in "
            "`/app/policy.md`. Append new balanced transactions dated "
            "2026-01-31; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(SOFTWARE_ACCOUNTS),
            "documents/software_project.md": doc,
        },
        expected=_expected(
            "internal-use-software-costs",
            "intangible-assets",
            seed,
            expected_deltas={
                SOFTWARE_ASSET: money(capitalized),
                SOFTWARE_EXPENSE: money(expensed),
                BANK: money(-total),
            },
            expected_new_transactions=[1, 3],
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={SOFTWARE_ASSET: money(capitalized)},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["internal-use-software", "capitalization-stages"],
        level="university",
        framework="us-gaap",
        standards=["asc:350-40"],
    )


LEASE_RECEIVABLE = "Assets:NetInvestmentInLease"
LESSOR_ACCOUNTS = MERCH_ACCOUNTS + [(LEASE_RECEIVABLE, "Net investment in sales-type lease")]


def lessor_sales_type_lease(seed: int) -> TaskInstance:
    """Scenario: dealer-lessor starts a sales-type lease in January.

    Oracle: recognize selling profit at commencement (lease receivable at
    fair value, inventory relieved at cost), like a sale. Trap: operating
    -lease treatment (keep asset, book rent). Level V/U/U/U/U/V/U.
    """
    rng = random.Random(seed)
    units = rng.randrange(5, 21)
    unit_cost = Decimal(rng.randrange(2000, 6001, 100)) / 100
    fair_each = (unit_cost * Decimal("1.5")).quantize(CENT)
    cost_total = units * unit_cost
    fair_total = units * fair_each
    opening = Decimal("30000.00")
    initial = _ledger_header(opening, LESSOR_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        f"Equipment held for lease or sale: {units} units",
        [(INVENTORY, cost_total), ("Equity:Opening-Balances", -cost_total)],
    )
    doc = (
        "# Sales-type lease commencement — 2026-01-10\n\n"
        f"The company leased out all {units} units (cost USD {money(unit_cost)} "
        f"each, fair value USD {money(fair_each)} each). Ownership transfers "
        "at the end of the lease; collectability is probable. The present "
        f"value of lease payments is USD {money(fair_total)}; there is no "
        "unguaranteed residual and no payment at commencement.\n"
    )
    policy = POLICY + (
        "- A sales-type lease is treated as a sale at commencement: record\n"
        "  the net investment in the lease and sales revenue at fair value,\n"
        "  and relieve inventory through cost of goods sold.\n"
    )
    solution = (
        initial
        + _txn(
            "2026-01-10",
            "Lessee",
            "Sales-type lease commencement",
            [(LEASE_RECEIVABLE, fair_total), ("Income:Sales", -fair_total)],
        )
        + _txn(
            "2026-01-10",
            "Lessee",
            "Cost of equipment leased",
            [(COST_OF_SALES, cost_total), (INVENTORY, -cost_total)],
        )
    )
    return TaskInstance(
        task_id="lessor-sales-type-lease",
        family="leases",
        title="Record a lessor's sales-type lease commencement",
        instruction=(
            "Record the commencement in `/app/documents/lease_commencement.md` "
            "in `/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated 2026-01-10; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(LESSOR_ACCOUNTS),
            "documents/lease_commencement.md": doc,
        },
        expected=_expected(
            "lessor-sales-type-lease",
            "leases",
            seed,
            expected_deltas={
                LEASE_RECEIVABLE: money(fair_total),
                "Income:Sales": money(-fair_total),
                COST_OF_SALES: money(cost_total),
                INVENTORY: money(-cost_total),
            },
            expected_new_transactions=[1, 3],
            expected_period=["2026-01-10", "2026-01-10"],
            required_final_balances={
                INVENTORY: "0.00",
                LEASE_RECEIVABLE: money(fair_total),
            },
        ),
        solution_ledger=solution,
        difficulty="hard",
        keywords=["lessor", "sales-type-lease", "selling-profit"],
        level="university",
        skill="analysis",
        standards=["asc:842", "ifrs:16"],
    )


SECURED_BORROWING = "Liabilities:SecuredBorrowing"
FINANCE_FEE = "Expenses:FactoringFee"
FACTORING_ACCOUNTS = [
    (AR, "Trade receivables pledged as collateral"),
    (SECURED_BORROWING, "Secured borrowing against pledged receivables"),
    (FINANCE_FEE, "Factoring and financing fees"),
]


def factoring_secured_borrowing(seed: int) -> TaskInstance:
    """Scenario: receivables pledged with full recourse and control kept.

    Oracle: cash is a secured borrowing net of the factor's fee; the
    receivables stay on the books. Trap: derecognizing receivables as a
    sale. Level V/U/U/U/U/V/U -> university.
    """
    rng = random.Random(seed)
    receivables = Decimal(rng.randrange(80, 241)) * 500
    advance_pct = rng.choice([80, 90])
    advance = receivables * advance_pct / 100
    fee_pct = rng.choice([Decimal("0.02"), Decimal("0.03")])
    fee = advance * fee_pct
    cash = advance - fee
    opening = Decimal("20000.00")
    initial = _ledger_header(opening, FACTORING_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        "Opening trade receivables",
        [(AR, receivables), ("Equity:Opening-Balances", -receivables)],
    )
    doc = (
        "# Factoring agreement — 2026-01-12\n\n"
        f"The company pledged receivables of USD {money(receivables)} to a "
        f"factor, which advanced {advance_pct}% (USD {money(advance)}) less a "
        f"{fee_pct * 100:.0f}% fee on the advance (USD {money(fee)}), paying "
        f"USD {money(cash)} into checking. The company retains full recourse "
        "for uncollectible accounts and keeps control of collections; "
        "customers were not notified.\n"
    )
    policy = POLICY + (
        "- A transfer of receivables that does not surrender control (here:\n"
        "  full recourse and retained collections) is a SECURED BORROWING,\n"
        "  not a sale: cash is debited net of the fee, the fee is expensed,\n"
        "  a secured-borrowing liability is credited for the advance, and\n"
        "  receivables remain on the books.\n"
    )
    solution = initial + _txn(
        "2026-01-12",
        "Factor",
        "Advance against pledged receivables",
        [(BANK, cash), (FINANCE_FEE, fee), (SECURED_BORROWING, -advance)],
    )
    return TaskInstance(
        task_id="factoring-secured-borrowing",
        family="receivables",
        title="Treat a with-recourse factoring as a secured borrowing",
        instruction=(
            "Record the agreement in `/app/documents/factoring_agreement.md` "
            "in `/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated 2026-01-12; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(FACTORING_ACCOUNTS),
            "documents/factoring_agreement.md": doc,
        },
        expected=_expected(
            "factoring-secured-borrowing",
            "receivables",
            seed,
            expected_deltas={
                BANK: money(cash),
                FINANCE_FEE: money(fee),
                SECURED_BORROWING: money(-advance),
            },
            expected_period=["2026-01-12", "2026-01-12"],
            required_final_balances={AR: money(receivables)},
        ),
        solution_ledger=solution,
        difficulty="hard",
        keywords=["factoring", "secured-borrowing", "derecognition"],
        level="university",
        skill="analysis",
        standards=["asc:860", "ifrs:9"],
    )


PENSION_EXPENSE = "Expenses:Pension"
PENSION_LIABILITY = "Liabilities:NetPensionLiability"
PENSION_ACCOUNTS = [
    (PENSION_EXPENSE, "Net periodic pension cost"),
    (PENSION_LIABILITY, "Net defined-benefit pension liability"),
]


def pension_expense_and_contribution(seed: int) -> TaskInstance:
    """Scenario: January pension cost components and a larger cash contribution.

    Oracle: net pension expense = service + interest - expected return
    + amortization; the excess of the cash contribution over expense
    reduces the pension liability. Trap: expensing the cash contribution.
    Level V/U/U/U/U/U/U -> university.
    """
    rng = random.Random(seed)
    service = Decimal(rng.randrange(30, 91)) * 100
    interest = Decimal(rng.randrange(20, 71)) * 100
    expected_return = Decimal(rng.randrange(15, 61)) * 100
    amortization = Decimal(rng.randrange(2, 16)) * 100
    expense = service + interest - expected_return + amortization
    if expense <= 0:
        service += Decimal("10000")
        expense += Decimal("10000")
    contribution = expense + Decimal(rng.randrange(10, 61)) * 100
    reduction = contribution - expense
    opening_liability = contribution * rng.randint(3, 5)
    opening = contribution + Decimal("30000.00")
    initial = _ledger_header(opening, PENSION_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        "Opening net pension liability",
        [("Equity:Opening-Balances", opening_liability), (PENSION_LIABILITY, -opening_liability)],
    )
    doc = (
        "# Pension data — January 2026\n\n| Item | USD |\n|---|---:|\n"
        f"| Service cost | {money(service)} |\n"
        f"| Interest cost on the obligation | {money(interest)} |\n"
        f"| Expected return on plan assets | {money(expected_return)} |\n"
        f"| Amortization of prior actuarial losses | {money(amortization)} |\n"
        f"| Employer cash contribution (2026-01-20) | {money(contribution)} |\n"
    )
    policy = POLICY + (
        "- Net periodic pension cost = service cost + interest cost -\n"
        "  expected return on plan assets + amortization amounts. Employer\n"
        "  cash contributions are funding, not expense: any excess of the\n"
        "  contribution over the period cost reduces the net pension\n"
        "  liability (credit bank for the full contribution).\n"
    )
    solution = initial + _txn(
        "2026-01-20",
        "Pension plan",
        "Pension cost and January funding",
        [(PENSION_EXPENSE, expense), (PENSION_LIABILITY, reduction), (BANK, -contribution)],
    )
    return TaskInstance(
        task_id="pension-expense-and-contribution",
        family="employee-benefits",
        title="Record pension cost and employer funding",
        instruction=(
            "Record the January pension entries in "
            "`/app/documents/pension_data.md` in `/app/ledger.beancount`, "
            "following `/app/policy.md`. Append new balanced transactions "
            "dated 2026-01-20; do not edit existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(PENSION_ACCOUNTS),
            "documents/pension_data.md": doc,
        },
        expected=_expected(
            "pension-expense-and-contribution",
            "employee-benefits",
            seed,
            expected_deltas={
                PENSION_EXPENSE: money(expense),
                PENSION_LIABILITY: money(reduction),
                BANK: money(-contribution),
            },
            expected_new_transactions=[1, 3],
            expected_period=["2026-01-20", "2026-01-20"],
            required_final_balances={PENSION_LIABILITY: money(-(opening_liability - reduction))},
        ),
        solution_ledger=solution,
        difficulty="hard",
        keywords=["defined-benefit", "pension-cost", "funding"],
        level="university",
        skill="analysis",
        standards=["asc:715", "ias:19"],
    )


def irr_from_annuity_factor(seed: int) -> TaskInstance:
    """Numeric: identify IRR by matching the annuity factor.

    Trap: answering the payback period (the same factor, mislabeled).
    """
    rng = random.Random(seed)
    years = rng.choice([4, 5, 6])
    rates = [Decimal("0.08"), Decimal("0.10"), Decimal("0.12")]
    irr = rng.choice(rates)
    factors = {rate: _annuity_factor(rate, years) for rate in rates}
    inflow = Decimal(rng.randrange(15, 61)) * 1000
    initial = (inflow * factors[irr]).quantize(CENT)
    payback = (initial / inflow).quantize(Decimal("0.0001"))
    factor_rows = "\n".join(
        f"| Annuity factor ({rate * 100:.0f}%, {years} years) | {factors[rate]} |" for rate in rates
    )
    data = (
        "# Project data\n\n| Item | Value |\n|---|---:|\n"
        f"| Initial investment | USD {money(initial)} |\n"
        f"| Annual net cash inflow (even) | USD {money(inflow)} |\n"
        f"| Life | {years} years |\n"
        f"{factor_rows}\n\nNo salvage value.\n"
    )
    policy = """# IRR conventions (applies to this task)

- The internal rate of return makes NPV zero: initial investment /
  annual inflow gives the annuity factor for the project's life; the
  IRR is the interest rate whose stated factor matches it (the initial
  amount was built from one of the stated factors).
- Answer as a percentage number (for example 10.00 for 10%).
"""
    question = _numeric_question(
        "internal rate of return",
        "Using `/app/documents/project_data.md` and `/app/policy.md`, compute "
        "the project's **internal rate of return** as a percentage number.",
        "the percentage number",
    )
    return _numeric_instance(
        task_id="irr-from-annuity-factor",
        family="capital-budgeting",
        title="Identify a project's IRR from annuity factors",
        question=question,
        policy=policy,
        data_name="project_data.md",
        data=data,
        gold=(irr * 100).quantize(Decimal("0.01")),
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "irr", "capital-budgeting"],
        abs_tolerance="0.01",
        trap_value=format(payback, "f"),
    )


def c_corporation_taxable_income(seed: int) -> TaskInstance:
    """Numeric: book-to-tax adjustments to C-corporation taxable income.

    Trap: deducting 100% of meals/fines or taxing municipal interest.
    """
    rng = random.Random(seed)

    def amt(lo, hi):
        return Decimal(rng.randrange(lo, hi)) * 1000

    book, muni, fines = amt(300, 801), amt(10, 61), amt(5, 31)
    meals = amt(10, 41) * 2
    excess_tax_dep = amt(20, 91)
    gold = book - muni + fines + meals / 2 - excess_tax_dep
    if gold == book:  # keep the unadjusted-book-income trap distinct
        fines += 5000
        gold += 5000
    data = (
        "# Book-to-tax schedule (Schedule M-1 style), 2025\n\n| Item | USD |\n|---|---:|\n"
        f"| Book (pre-tax financial) income | {money(book)} |\n"
        f"| Municipal bond interest in book income | {money(muni)} |\n"
        f"| Federal fines expensed in book income | {money(fines)} |\n"
        f"| Business meals expensed in book income | {money(meals)} |\n"
        f"| Excess of tax over book depreciation | {money(excess_tax_dep)} |\n"
    )
    policy = """# Taxable-income conventions (applies to this task)

- Start with book income. Subtract tax-exempt municipal interest. Add
  back nondeductible fines in full and 50% of business meals (only half
  is deductible). Subtract tax depreciation in excess of book.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "C-corporation taxable income",
        "Using `/app/documents/book_to_tax.md` and `/app/policy.md`, compute "
        "**taxable income** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="c-corporation-taxable-income",
        family="income-taxes",
        title="Compute C-corporation taxable income",
        question=question,
        policy=policy,
        data_name="book_to_tax.md",
        data=data,
        gold=gold,
        seed=seed,
        category="tax",
        keywords=["numeric", "book-tax-differences", "c-corporation"],
        abs_tolerance="0.01",
        trap_value=money(book),
    )


def s_corporation_aaa_ending(seed: int) -> TaskInstance:
    """Numeric: ending accumulated adjustments account (AAA).

    Trap: increasing AAA by tax-exempt income (which goes to OAA).
    """
    rng = random.Random(seed)

    def amt(lo, hi):
        return Decimal(rng.randrange(lo, hi)) * 1000

    beginning, ordinary, exempt = amt(50, 201), amt(40, 161), amt(5, 31)
    nondeductible, distributions = amt(2, 16), amt(20, 101)
    gold = beginning + ordinary - nondeductible - distributions
    while gold < 0:
        ordinary += 50000
        gold += 50000
    data = (
        "# S-corporation AAA data — 2025\n\n| Item | USD |\n|---|---:|\n"
        f"| AAA, 2025-01-01 | {money(beginning)} |\n"
        f"| Ordinary business income | {money(ordinary)} |\n"
        f"| Tax-exempt interest income | {money(exempt)} |\n"
        f"| Nondeductible expenses (not tax-exempt related) | {money(nondeductible)} |\n"
        f"| Cash distributions to shareholders | {money(distributions)} |\n"
    )
    policy = """# AAA conventions (applies to this task)

- AAA increases by taxable ordinary income and decreases by losses,
  nondeductible expenses, and distributions. TAX-EXEMPT income goes to
  the other adjustments account (OAA), never to AAA.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "ending accumulated adjustments account",
        "Using `/app/documents/aaa_data.md` and `/app/policy.md`, compute "
        "**AAA at 2025-12-31** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="s-corporation-aaa-ending",
        family="passthrough-taxation",
        title="Compute an S corporation's ending AAA",
        question=question,
        policy=policy,
        data_name="aaa_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="tax",
        keywords=["numeric", "s-corporation", "aaa"],
        abs_tolerance="0.01",
        trap_value=money(gold + exempt),
    )


def partnership_outside_basis(seed: int) -> TaskInstance:
    """Numeric: a partner's ending outside basis.

    Trap: forgetting the increase for the partner's share of partnership
    liabilities.
    """
    rng = random.Random(seed)

    def amt(lo, hi):
        return Decimal(rng.randrange(lo, hi)) * 1000

    beginning, contribution, income = amt(30, 121), amt(10, 61), amt(15, 81)
    liability_increase, distributions, exempt = amt(5, 41), amt(10, 51), amt(2, 16)
    gold = beginning + contribution + income + exempt + liability_increase - distributions
    while gold < 0:
        income += 50000
        gold += 50000
    trap = gold - liability_increase
    data = (
        "# Partner outside-basis data — 2025\n\n| Item | USD |\n|---|---:|\n"
        f"| Outside basis, 2025-01-01 | {money(beginning)} |\n"
        f"| Additional cash contribution | {money(contribution)} |\n"
        f"| Share of partnership ordinary income | {money(income)} |\n"
        f"| Share of tax-exempt income | {money(exempt)} |\n"
        f"| Increase in share of partnership liabilities | {money(liability_increase)} |\n"
        f"| Cash distributions received | {money(distributions)} |\n"
    )
    policy = """# Outside-basis conventions (applies to this task)

- Outside basis increases by contributions, shares of taxable AND
  tax-exempt income, and increases in the partner's share of partnership
  liabilities; it decreases by distributions (and loss shares).
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "ending outside basis",
        "Using `/app/documents/outside_basis.md` and `/app/policy.md`, compute "
        "the partner's **outside basis at 2025-12-31** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="partnership-outside-basis",
        family="passthrough-taxation",
        title="Compute a partner's ending outside basis",
        question=question,
        policy=policy,
        data_name="outside_basis.md",
        data=data,
        gold=gold,
        seed=seed,
        category="tax",
        keywords=["numeric", "partnership", "outside-basis"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


def performance_materiality(seed: int) -> TaskInstance:
    """Numeric: performance materiality from an overall materiality base.

    Trap: answering overall materiality.
    """
    rng = random.Random(seed)
    benchmark = Decimal(rng.randrange(200, 801)) * 1000
    overall_pct = rng.choice([1, 5])
    performance_pct = rng.choice([50, 60, 75])
    overall = benchmark * Decimal(overall_pct) / 100
    gold = overall * Decimal(performance_pct) / 100
    data = (
        "# Audit planning data\n\n| Item | Value |\n|---|---:|\n"
        f"| Profit before tax (benchmark) | USD {money(benchmark)} |\n"
        f"| Overall materiality | {overall_pct}% of profit before tax |\n"
        f"| Performance materiality | {performance_pct}% of overall materiality |\n"
    )
    policy = """# Materiality conventions (applies to this task)

- Overall materiality = stated percentage of the benchmark.
- Performance materiality is set BELOW overall materiality (here, the
  stated percentage of overall materiality) to allow for aggregation
  risk. Answer performance materiality in USD.
"""
    question = _numeric_question(
        "performance materiality",
        "Using `/app/documents/audit_planning.md` and `/app/policy.md`, compute "
        "**performance materiality** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="performance-materiality",
        family="audit-planning",
        title="Compute performance materiality",
        question=question,
        policy=policy,
        data_name="audit_planning.md",
        data=data,
        gold=gold,
        seed=seed,
        category="audit-assurance",
        keywords=["numeric", "audit", "materiality"],
        abs_tolerance="0.01",
        trap_value=money(overall),
    )


def cash_and_equivalents_total(seed: int) -> TaskInstance:
    """Numeric: total cash and cash equivalents from a list of balances.

    Trap: including restricted cash/long-maturity deposits or netting an
    overdraft instead of classifying it as a liability.
    """
    rng = random.Random(seed)

    def amt(lo, hi):
        return Decimal(rng.randrange(lo, hi)) * 100

    cash, money_market, tbill = amt(80, 301), amt(30, 151), amt(20, 121)
    restricted, cd, overdraft = amt(20, 101), amt(30, 141), amt(5, 41)
    gold = cash + money_market + tbill
    trap = gold + restricted + cd - overdraft
    rows = [
        ("Checking account", cash),
        ("Money-market fund (withdrawable on demand)", money_market),
        ("Treasury bill bought with 2 months to maturity", tbill),
        ("Restricted cash for a plant expansion in 2 years", restricted),
        ("Certificate of deposit, original maturity 9 months", cd),
        ("Bank overdraft (separate account)", overdraft),
    ]
    rng.shuffle(rows)
    data = _balances_table("Cash-related balances — 2026-01-31", rows)
    policy = """# Cash-equivalent conventions (applies to this task)

- Cash equivalents are short-term, highly liquid investments with an
  ORIGINAL maturity of three months or less (including on-demand money
  market funds). Restricted cash for a long-term purpose is not cash.
- A bank overdraft is a liability; it is not netted against cash here.
- Answer total cash and cash equivalents in USD.
"""
    question = _numeric_question(
        "cash and cash equivalents",
        "Using `/app/documents/cash_balances.md` and `/app/policy.md`, compute "
        "**total cash and cash equivalents** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="cash-and-equivalents-total",
        family="cash-controls",
        title="Classify and total cash and cash equivalents",
        question=question,
        policy=policy,
        data_name="cash_balances.md",
        data=data,
        gold=gold,
        seed=seed,
        category="financial-accounting",
        keywords=["numeric", "cash-equivalents", "classification"],
        abs_tolerance="0.01",
        trap_value=money(trap),
    )


INVESTMENT_CLASSES = [
    "Trading (fair value through profit or loss)",
    "Available-for-sale debt securities",
    "Held-to-maturity (amortized cost)",
]
INVESTMENT_CASES = [
    (
        "Corporate bonds bought to sell within weeks for short-term price movements.",
        "Trading (fair value through profit or loss)",
    ),
    (
        "Corporate bonds the company has the positive intent and ability "
        "to hold until they mature.",
        "Held-to-maturity (amortized cost)",
    ),
    (
        "Corporate bonds that may be sold if liquidity is needed, with no "
        "intent to trade them actively or necessarily hold to maturity.",
        "Available-for-sale debt securities",
    ),
    (
        "A debt portfolio actively bought and sold to profit from short-term price differences.",
        "Trading (fair value through profit or loss)",
    ),
]


def sc_investment_classification(seed: int) -> TaskInstance:
    """Single-choice: US GAAP debt-security classification by intent."""
    rng = random.Random(seed)
    narrative, correct = rng.choice(INVESTMENT_CASES)
    labels = INVESTMENT_CLASSES.copy()
    rng.shuffle(labels)
    option_ids = ["A", "B", "C"]
    gold = option_ids[labels.index(correct)]
    options_md = "\n".join(f"- {oid}. {name}" for oid, name in zip(option_ids, labels, strict=True))
    policy = """# Debt-security classification (US GAAP; applies to this task)

- Trading: bought and held principally to sell in the near term.
- Held-to-maturity: positive intent AND ability to hold to maturity.
- Available-for-sale: debt securities in neither category above.
"""
    question = _choice_question(
        "debt-security classification",
        f"Holding: **{narrative}**\n\nUsing `/app/policy.md`, how is it "
        "classified? Select exactly one option.",
        options_md,
        '"B"',
    )
    return TaskInstance(
        task_id="sc-investment-classification",
        family="investments",
        title="Classify a debt security by intent",
        instruction=(
            "Answer the single-choice question in `/app/question.md` "
            "following `/app/policy.md`. Write your selection to "
            "`/app/answer.json` in the exact format shown in the question."
        ),
        app_files={
            "question.md": question,
            "policy.md": policy,
            "answer.example.json": '{\n  "final_answer": "A",\n  "confidence": 50\n}\n',
        },
        expected=_expected(
            "sc-investment-classification",
            "investments",
            seed,
            format="single-choice",
            gold=gold,
            options=option_ids,
            expected_deltas={},
            expected_new_transactions=0,
            expected_period=None,
        ),
        solution_ledger="",
        solution_answer={"final_answer": gold, "confidence": 100},
        keywords=["single-choice", "debt-securities", "classification"],
        level="vocational",
        framework="us-gaap",
        format="single-choice",
        skill="remembering-understanding",
        standards=["asc:320"],
    )


def mc_reportable_segments(seed: int) -> TaskInstance:
    """Multiple-choice: apply the three 10% reportable-segment tests.

    Segment A qualifies on revenue only, B on profit/assets, C never;
    D (when present) qualifies on assets only. Trap: requiring all three.
    """
    rng = random.Random(seed)
    # Percentage shares are fixed patterns scaled by a random base so the
    # threshold outcomes are construction-guaranteed but amounts vary.
    scale = Decimal(rng.randrange(80, 201)) * 10
    segments = [
        ("Alpha", 14, 4, 5, True),  # revenue alone
        ("Beta", 5, 18, 12, True),  # profit and assets
        ("Gamma", 6, 3, 4, False),  # none
        ("Delta", 4, 2, 15, True),  # assets alone
        ("Epsilon", 2, 1, 3, False),
        ("Zeta", 3, 2, 2, False),
    ]
    chosen = segments[:]
    rng.shuffle(chosen)
    chosen = chosen[:4]
    # Guarantee at least one qualifying and one non-qualifying case.
    if all(q for *_, q in chosen):
        chosen[-1] = segments[2]
    if not any(q for *_, q in chosen):
        chosen[0] = segments[0]
    option_ids = ["A", "B", "C", "D"]
    table_rows = []
    gold = []
    for oid, (name, rev_pct, profit_pct, asset_pct, qualifies) in zip(
        option_ids, chosen, strict=True
    ):
        # Amounts are percentages of different stated totals; scale revenue.
        revenue = (Decimal(rev_pct) * scale).quantize(CENT)
        table_rows.append(
            f"- {oid}. {name} is reportable — revenue USD {money(revenue)} "
            f"({rev_pct}% of combined revenue), profit {profit_pct}% of the "
            f"greater combined profit/loss measure, assets {asset_pct}%."
        )
        if qualifies:
            gold.append(oid)
    options_md = "\n".join(table_rows)
    policy = """# Reportable-segment thresholds (applies to this task)

- A segment is reportable if it meets ANY ONE 10% test: at least 10% of
  combined revenue, at least 10% of the greater of combined segment
  profits/losses, or at least 10% of combined segment assets.
- Meeting two or all three tests is not required.
"""
    question = _choice_question(
        "reportable operating segments",
        "Using `/app/policy.md`, select **all** statements that are true. "
        "Incorrect selections are penalized.",
        options_md,
        '["A", "C"]',
    )
    return TaskInstance(
        task_id="mc-reportable-segments",
        family="segment-reporting",
        title="Apply the 10% reportable-segment tests",
        instruction=(
            "Answer the multiple-choice question in `/app/question.md` "
            "following `/app/policy.md`. Write your selection to "
            "`/app/answer.json` in the exact format shown in the question."
        ),
        app_files={
            "question.md": question,
            "policy.md": policy,
            "answer.example.json": '{\n  "final_answer": ["A"],\n  "confidence": 50\n}\n',
        },
        expected=_expected(
            "mc-reportable-segments",
            "segment-reporting",
            seed,
            format="multiple-choice",
            gold=sorted(gold),
            options=option_ids,
            expected_deltas={},
            expected_new_transactions=0,
            expected_period=None,
        ),
        solution_ledger="",
        solution_answer={"final_answer": sorted(gold), "confidence": 100},
        keywords=["multiple-choice", "reportable-segments", "ten-percent-tests"],
        level="vocational",
        format="multiple-choice",
        skill="application",
        standards=["asc:280", "ifrs:8"],
    )


DERIVATIVE = "Assets:InterestRateSwap"
HEDGE_ACCOUNTS = [
    (DERIVATIVE, "Interest-rate swap at fair value"),
    (AOCI, "Accumulated OCI — cash-flow hedges"),
    (UNREALIZED, "Hedgeineffectiveness gain in profit or loss"),
]


def cash_flow_hedge_fair_value(seed: int) -> TaskInstance:
    """Scenario: cash-flow hedge swap gains value; most is effective.

    Oracle: debit derivative for the full fair-value increase; credit the
    effective portion to OCI and only the ineffective portion to income.
    Trap: putting the whole gain in OCI. Level V/U/U/U/U/U/U.
    """
    rng = random.Random(seed)
    total_gain = Decimal(rng.randrange(20, 101)) * 1000
    effective_pct = rng.choice([80, 90])
    effective = total_gain * effective_pct / 100
    ineffective = total_gain - effective
    opening = Decimal("50000.00")
    initial = _ledger_header(opening, HEDGE_ACCOUNTS)
    doc = (
        "# Hedge valuation — 2026-01-31\n\n"
        "The interest-rate swap (designated and documented as a cash-flow "
        f"hedge) had nil fair value at inception on 2026-01-01 and a fair "
        f"value asset of USD {money(total_gain)} at January 31. Hedge "
        f"accounting testing attributes {effective_pct}% of the change to "
        "the effective portion; the rest is ineffectiveness.\n"
    )
    policy = POLICY + (
        "- For a cash-flow hedge, the effective portion of the derivative's\n"
        "  fair-value change goes to other comprehensive income; any\n"
        "  ineffective portion is recognized immediately in profit or loss.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "Hedge valuation",
        "Cash-flow hedge fair-value gain",
        [(DERIVATIVE, total_gain), (AOCI, -effective), (UNREALIZED, -ineffective)],
    )
    return TaskInstance(
        task_id="cash-flow-hedge-fair-value",
        family="derivatives-hedging",
        title="Split a cash-flow hedge gain between OCI and income",
        instruction=(
            "Record the January valuation in `/app/documents/hedge_valuation.md` "
            "in `/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated 2026-01-31; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(HEDGE_ACCOUNTS),
            "documents/hedge_valuation.md": doc,
        },
        expected=_expected(
            "cash-flow-hedge-fair-value",
            "derivatives-hedging",
            seed,
            expected_deltas={
                DERIVATIVE: money(total_gain),
                AOCI: money(-effective),
                UNREALIZED: money(-ineffective),
            },
            expected_new_transactions=[1, 2],
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={DERIVATIVE: money(total_gain)},
        ),
        solution_ledger=solution,
        difficulty="hard",
        keywords=["derivatives", "cash-flow-hedge", "oci", "ineffectiveness"],
        level="university",
        skill="analysis",
        standards=["asc:815", "ifrs:9"],
    )


RESTRUCTURING_PROVISION = "Liabilities:RestructuringProvision"
RESTRUCTURING_EXPENSE = "Expenses:Restructuring"
PROVISION_ACCOUNTS = [
    (RESTRUCTURING_PROVISION, "Provision for restructuring costs"),
    (RESTRUCTURING_EXPENSE, "Restructuring expense"),
]


def provision_rollforward_topup(seed: int) -> TaskInstance:
    """Scenario: use part of a restructuring provision, then re-estimate it.

    Oracle: payments debit the provision; the January expense is only the
    top-up needed to reach the revised required ending balance. Trap:
    expensing the whole required ending balance (or the payments).
    Level V/U/U/V/U/U/V -> university.
    """
    rng = random.Random(seed)
    opening_provision = Decimal(rng.randrange(80, 201)) * 1000
    used = Decimal(rng.randrange(20, 71)) * 1000
    required = opening_provision - used + Decimal(rng.randrange(10, 61)) * 1000
    topup = required - (opening_provision - used)
    opening = Decimal("80000.00")
    initial = _ledger_header(opening, PROVISION_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        "Opening restructuring provision",
        [
            ("Equity:Opening-Balances", opening_provision),
            (RESTRUCTURING_PROVISION, -opening_provision),
        ],
    )
    doc = (
        "# Restructuring provision — January 2026\n\n"
        f"Opening provision: USD {money(opening_provision)}. Severance "
        f"payments of USD {money(used)} were made from checking in January "
        "and are not yet recorded. At January 31 management re-estimates "
        f"the remaining obligation at USD {money(required)} in total, which "
        "is the provision balance that should remain.\n"
    )
    policy = POLICY + (
        "- Amounts used are charged against the provision (never expensed\n"
        "  again). The period expense is only the adjustment needed to move\n"
        "  the post-use balance to the revised required ending estimate.\n"
    )
    solution = (
        initial
        + _txn(
            "2026-01-20",
            "Severance",
            "Restructuring payments charged to provision",
            [(RESTRUCTURING_PROVISION, used), (BANK, -used)],
        )
        + _txn(
            "2026-01-31",
            "Management",
            "Top provision up to revised estimate",
            [(RESTRUCTURING_EXPENSE, topup), (RESTRUCTURING_PROVISION, -topup)],
        )
    )
    return TaskInstance(
        task_id="provision-rollforward-topup",
        family="provisions-contingencies",
        title="Use and re-estimate a restructuring provision",
        instruction=(
            "Record the January activity in `/app/documents/provision_update.md` "
            "in `/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated in January 2026; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(PROVISION_ACCOUNTS),
            "documents/provision_update.md": doc,
        },
        expected=_expected(
            "provision-rollforward-topup",
            "provisions-contingencies",
            seed,
            expected_deltas={
                RESTRUCTURING_PROVISION: money(used - topup),
                BANK: money(-used),
                RESTRUCTURING_EXPENSE: money(topup),
            },
            expected_new_transactions=[1, 3],
            required_final_balances={RESTRUCTURING_PROVISION: money(-required)},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["provision", "rollforward", "restructuring"],
        level="university",
        standards=["asc:712", "ias:37"],
    )


CAPITAL_ANA = "Equity:AnaCapital"
CAPITAL_BEN = "Equity:BenCapital"
CAPITAL_CARA = "Equity:CaraCapital"
ADMISSION_ACCOUNTS = [
    (CAPITAL_ANA, "Ana, capital"),
    (CAPITAL_BEN, "Ben, capital"),
    (CAPITAL_CARA, "Cara, capital"),
]


def partnership_admission_bonus(seed: int) -> TaskInstance:
    """Scenario: Cara buys into a partnership for more than her book share.

    Oracle (bonus method): Cara is credited only her stated percentage of
    post-admission book capital; the difference is a bonus credited to
    Ana and Ben in their profit ratio. Trap: crediting Cara with her
    full cash contribution. Level V/U/U/V/U/U/U -> university.
    """
    rng = random.Random(seed)
    ana = Decimal(rng.randrange(60, 141)) * 1000
    ben = Decimal(rng.randrange(60, 141)) * 1000
    contribution = Decimal(rng.randrange(80, 181)) * 1000
    share_pct = rng.choice([20, 25])
    # Ensure the contribution exceeds the book share acquired (bonus to old).
    while contribution <= (ana + ben + contribution) * share_pct / 100:
        contribution += 20000
    total_capital = ana + ben + contribution
    cara_credit = total_capital * share_pct / 100
    bonus = contribution - cara_credit
    ana_bonus = bonus * Decimal("0.6")
    ben_bonus = bonus - ana_bonus
    opening = Decimal("20000.00")
    initial = _ledger_header(opening, ADMISSION_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        "Opening partner capital balances",
        [
            ("Equity:Opening-Balances", ana + ben),
            (CAPITAL_ANA, -ana),
            (CAPITAL_BEN, -ben),
        ],
    )
    doc = (
        "# Partnership admission — 2026-01-15\n\n"
        f"Existing capital: Ana USD {money(ana)}, Ben USD {money(ben)} "
        "(profit ratio Ana 60%, Ben 40%). Cara contributed "
        f"USD {money(contribution)} cash for a {share_pct}% interest in "
        "total capital. No assets were revalued; the bonus method applies.\n"
    )
    policy = POLICY + (
        "- Bonus method on admission: the new partner's capital is credited\n"
        "  with the agreed percentage of total book capital AFTER the\n"
        "  contribution. Any difference from the cash paid is a bonus to or\n"
        "  from the old partners in their profit-sharing ratio.\n"
    )
    solution = initial + _txn(
        "2026-01-15",
        "Cara",
        "Cara admitted with bonus to old partners",
        [
            (BANK, contribution),
            (CAPITAL_CARA, -cara_credit),
            (CAPITAL_ANA, -ana_bonus),
            (CAPITAL_BEN, -ben_bonus),
        ],
    )
    return TaskInstance(
        task_id="partnership-admission-bonus",
        family="partnerships",
        title="Admit a partner under the bonus method",
        instruction=(
            "Record the admission in `/app/documents/admission.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated 2026-01-15; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(ADMISSION_ACCOUNTS),
            "documents/admission.md": doc,
        },
        expected=_expected(
            "partnership-admission-bonus",
            "partnerships",
            seed,
            expected_deltas={
                BANK: money(contribution),
                CAPITAL_CARA: money(-cara_credit),
                CAPITAL_ANA: money(-ana_bonus),
                CAPITAL_BEN: money(-ben_bonus),
            },
            expected_new_transactions=[1, 3],
            expected_period=["2026-01-15", "2026-01-15"],
            required_final_balances={CAPITAL_CARA: money(-cara_credit)},
        ),
        solution_ledger=solution,
        difficulty="hard",
        keywords=["partnership", "admission", "bonus-method"],
        level="university",
        skill="analysis",
    )


ENCUMBRANCES = "Expenses:Encumbrances"
BUDGETARY_RESERVE = "Equity:BudgetaryFundBalanceAssigned"
EXPENDITURES = "Expenses:Expenditures"
ENCUMBRANCE_ACCOUNTS = [
    (AP, "Vouchers/accounts payable"),
    (ENCUMBRANCES, "Budgetary encumbrances outstanding"),
    (BUDGETARY_RESERVE, "Budgetary fund balance assigned for encumbrances"),
    (EXPENDITURES, "General fund expenditures"),
]


def governmental_encumbrance_entry(seed: int) -> TaskInstance:
    """Scenario: general-fund purchase order issued, then goods received.

    Oracle: encumber the estimate at order, reverse the whole encumbrance
    on receipt, and record the expenditure/liability at the ACTUAL invoice.
    Trap: recording the expenditure at the estimated order amount.
    Level V/U/U/V/U/U/U -> university.
    """
    rng = random.Random(seed)
    estimate = Decimal(rng.randrange(40, 121)) * 500
    saving = Decimal(rng.randrange(2, 11)) * 100
    actual = estimate - saving
    opening = Decimal("50000.00")
    initial = _ledger_header(opening, ENCUMBRANCE_ACCOUNTS)
    doc = (
        "# General fund purchase — January 2026\n\n"
        f"2026-01-05: purchase order issued for supplies estimated at "
        f"USD {money(estimate)}.\n"
        f"2026-01-20: all goods received with an invoice for "
        f"USD {money(actual)}, unpaid at month-end.\n"
    )
    policy = POLICY + (
        "- Governmental budgetary accounting: issuing a purchase order\n"
        "  debits encumbrances and credits budgetary fund balance assigned.\n"
        "  On receipt, reverse the ORIGINAL estimated encumbrance in full\n"
        "  and record the expenditure and payable at the actual invoice.\n"
    )
    solution = (
        initial
        + _txn(
            "2026-01-05",
            "Purchasing",
            "Encumber purchase order",
            [(ENCUMBRANCES, estimate), (BUDGETARY_RESERVE, -estimate)],
        )
        + _txn(
            "2026-01-20",
            "Purchasing",
            "Reverse encumbrance on receipt",
            [(BUDGETARY_RESERVE, estimate), (ENCUMBRANCES, -estimate)],
        )
        + _txn(
            "2026-01-20",
            "Supplier",
            "Supplies received; invoice recorded",
            [(EXPENDITURES, actual), (AP, -actual)],
        )
    )
    return TaskInstance(
        task_id="governmental-encumbrance-entry",
        family="governmental-accounting",
        title="Encumber and then record a general-fund purchase",
        instruction=(
            "Record the January entries in `/app/documents/purchase_order.md` "
            "in `/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions on their stated January dates; do not edit "
            "existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(ENCUMBRANCE_ACCOUNTS),
            "documents/purchase_order.md": doc,
        },
        expected=_expected(
            "governmental-encumbrance-entry",
            "governmental-accounting",
            seed,
            expected_deltas={
                ENCUMBRANCES: "0.00",
                BUDGETARY_RESERVE: "0.00",
                EXPENDITURES: money(actual),
                AP: money(-actual),
            },
            expected_new_transactions=[1, 4],
            required_final_balances={AP: money(-actual)},
        ),
        solution_ledger=solution,
        difficulty="hard",
        keywords=["governmental", "encumbrance", "budgetary-accounting"],
        level="university",
        skill="application",
        framework="us-gaap",
    )


CONTRACT_COST = "Assets:ContractAcquisitionCost"
COMMISSION_AMORT = "Expenses:CommissionAmortization"
CONTRACT_COST_ACCOUNTS = [
    (CONTRACT_COST, "Capitalized incremental cost of obtaining a contract"),
    (COMMISSION_AMORT, "Amortization of contract acquisition costs"),
    (WAGES, "Sales staff salaries expense"),
]


def contract_acquisition_cost(seed: int) -> TaskInstance:
    """Scenario: incremental sales commission and ordinary sales salaries.

    Oracle: capitalize the incremental commission and amortize one month
    over the 24-month contract; non-incremental salaries are expensed.
    Trap: expensing the commission immediately. Level V/U/V/U/U/V/U.
    """
    rng = random.Random(seed)
    monthly_amort = Decimal(rng.randrange(20, 81)) * 10
    commission = monthly_amort * 24
    salaries = Decimal(rng.randrange(30, 91)) * 100
    opening = commission + salaries + Decimal("20000.00")
    initial = _ledger_header(opening, CONTRACT_COST_ACCOUNTS)
    doc = (
        "# January sales costs (paid from checking)\n\n"
        f"- Commission of USD {money(commission)} paid only because a new "
        "24-month customer contract was signed on 2026-01-01. The cost is "
        "expected to be recovered from the contract.\n"
        f"- Ordinary sales-staff salaries for January: USD {money(salaries)}.\n"
    )
    policy = POLICY + (
        "- Incremental costs of obtaining a contract that are expected to\n"
        "  be recovered are capitalized and amortized straight-line over\n"
        "  the contract term (here 24 months, starting January). Costs that\n"
        "  would be incurred anyway (ordinary salaries) are expensed.\n"
    )
    solution = (
        initial
        + _txn(
            "2026-01-01",
            "Sales team",
            "Capitalize incremental commission; expense salaries",
            [(CONTRACT_COST, commission), (WAGES, salaries), (BANK, -(commission + salaries))],
        )
        + _txn(
            "2026-01-31",
            "Sales team",
            "January amortization of contract cost",
            [(COMMISSION_AMORT, monthly_amort), (CONTRACT_COST, -monthly_amort)],
        )
    )
    return TaskInstance(
        task_id="contract-acquisition-cost",
        family="revenue-recognition",
        title="Capitalize and amortize a contract commission",
        instruction=(
            "Record the January costs in `/app/documents/sales_costs.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md`. Append new "
            "balanced transactions dated in January 2026; do not edit existing "
            "entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(CONTRACT_COST_ACCOUNTS),
            "documents/sales_costs.md": doc,
        },
        expected=_expected(
            "contract-acquisition-cost",
            "revenue-recognition",
            seed,
            expected_deltas={
                CONTRACT_COST: money(commission - monthly_amort),
                WAGES: money(salaries),
                BANK: money(-(commission + salaries)),
                COMMISSION_AMORT: money(monthly_amort),
            },
            expected_new_transactions=[1, 3],
            required_final_balances={CONTRACT_COST: money(commission - monthly_amort)},
        ),
        solution_ledger=solution,
        difficulty="medium",
        keywords=["contract-costs", "incremental-commission", "amortization"],
        level="university",
        standards=["asc:340-40", "ifrs:15"],
    )


ARO = "Liabilities:AssetRetirementObligation"
ACCRETION = "Expenses:Accretion"
ARO_ACCOUNTS = [
    (ARO, "Asset retirement obligation at present value"),
    (ACCRETION, "Accretion expense on retirement obligations"),
]


def aro_accretion(seed: int) -> TaskInstance:
    """Scenario: one month of accretion on an asset retirement obligation.

    Oracle: accretion = opening ARO carrying amount x the stated monthly
    credit-adjusted risk-free rate. Trap: applying the rate to the future
    undiscounted settlement amount. Level V/U/V/V/V/V/U -> vocational.
    """
    rng = random.Random(seed)
    monthly_rate = rng.choice([Decimal("0.004"), Decimal("0.005"), Decimal("0.006")])
    accretion = Decimal(rng.randrange(20, 101)) * 10
    carrying = (accretion / monthly_rate).quantize(CENT)
    settlement = carrying * rng.choice([Decimal("1.6"), Decimal("2")])
    opening = Decimal("50000.00")
    initial = _ledger_header(opening, ARO_ACCOUNTS) + _txn(
        "2026-01-01",
        "Opening",
        "Opening asset retirement obligation",
        [("Equity:Opening-Balances", carrying), (ARO, -carrying)],
    )
    doc = (
        "# Asset retirement obligation — January 2026\n\n"
        f"Carrying amount at 2026-01-01: USD {money(carrying)}. Expected "
        f"undiscounted settlement cost in 10 years: USD {money(settlement)}. "
        f"Credit-adjusted risk-free rate: {monthly_rate * 100:.1f}% per month. "
        "No settlement or estimate revision occurred in January.\n"
    )
    policy = POLICY + (
        "- Accretion for a period is the OPENING carrying amount of the\n"
        "  obligation x the credit-adjusted risk-free rate for that period;\n"
        "  it increases the obligation. The undiscounted settlement amount\n"
        "  is never the accretion base.\n"
    )
    solution = initial + _txn(
        "2026-01-31",
        "ARO",
        "January accretion expense",
        [(ACCRETION, accretion), (ARO, -accretion)],
    )
    return TaskInstance(
        task_id="aro-accretion",
        family="provisions-contingencies",
        title="Accrete an asset retirement obligation",
        instruction=(
            "Record January's accretion in `/app/documents/aro_data.md` in "
            "`/app/ledger.beancount`, following `/app/policy.md`. Append "
            "exactly one balanced transaction dated 2026-01-31; do not edit "
            "existing entries."
        ),
        app_files={
            "ledger.beancount": initial,
            "policy.md": policy,
            "chart_of_accounts.md": _chart_md(ARO_ACCOUNTS),
            "documents/aro_data.md": doc,
        },
        expected=_expected(
            "aro-accretion",
            "provisions-contingencies",
            seed,
            expected_deltas={ACCRETION: money(accretion), ARO: money(-accretion)},
            expected_period=["2026-01-31", "2026-01-31"],
            required_final_balances={ARO: money(-(carrying + accretion))},
        ),
        solution_ledger=solution,
        keywords=["asset-retirement-obligation", "accretion"],
        level="vocational",
        standards=["asc:410", "ias:37"],
    )


def tax_return_crossfoot_difference(seed: int) -> TaskInstance:
    """Numeric: recompute total income and size the reported understatement.

    Trap: subtracting a below-total adjustment that is not an income line.
    """
    rng = random.Random(seed)

    def amt(lo, hi):
        return Decimal(rng.randrange(lo, hi)) * 100

    wages, interest, dividends, business = amt(250, 801), amt(5, 51), amt(5, 41), amt(30, 161)
    omitted = amt(10, 71)
    adjustment = amt(5, 31)
    correct = wages + interest + dividends + business + omitted
    reported = correct - omitted
    data = (
        "# Draft individual return — income section (review copy)\n\n"
        "| Line | USD |\n|---|---:|\n"
        f"| Wages | {money(wages)} |\n"
        f"| Taxable interest | {money(interest)} |\n"
        f"| Ordinary dividends | {money(dividends)} |\n"
        f"| Business income | {money(business)} |\n"
        f"| Capital gain | {money(omitted)} |\n"
        f"| TOTAL income as reported on the draft | {money(reported)} |\n"
        f"| Educator-expense adjustment (below total income) | {money(adjustment)} |\n"
    )
    policy = """# Crossfooting conventions (applies to this task)

- Correct total income is the sum of the five income lines only.
  Adjustments presented below total income do not enter that total.
- Understatement = correct total income - total income as reported.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "understatement in reported total income",
        "Using `/app/documents/draft_return.md` and `/app/policy.md`, compute "
        "the **understatement in reported total income** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="tax-return-crossfoot-difference",
        family="income-taxes",
        title="Crossfoot a draft return's total income",
        question=question,
        policy=policy,
        data_name="draft_return.md",
        data=data,
        gold=omitted,
        seed=seed,
        category="tax",
        keywords=["numeric", "tax-review", "crossfoot"],
        abs_tolerance="0.01",
        trap_value=money(omitted - adjustment),
    )


def tax_cost_recovery_deduction(seed: int) -> TaskInstance:
    """Numeric: cost recovery from a stated recovery table.

    Trap: using book straight-line depreciation.
    """
    rng = random.Random(seed)
    basis = Decimal(rng.randrange(50, 201)) * 1000
    table = {
        5: [Decimal("20.00"), Decimal("32.00"), Decimal("19.20")],
        7: [Decimal("14.29"), Decimal("24.49"), Decimal("17.49")],
    }
    life = rng.choice([5, 7])
    year = rng.choice([2, 3])
    pct = table[life][year - 1]
    gold = (basis * pct / 100).quantize(CENT)
    book = (basis / (life + 3)).quantize(CENT)
    rows = "\n".join(f"| Year {y} | {p}% |" for y, p in enumerate(table[life], start=1))
    data = (
        "# Cost-recovery data\n\n| Item | Value |\n|---|---:|\n"
        f"| Asset basis | USD {money(basis)} |\n"
        f"| Recovery period | {life} years |\n"
        f"| Current recovery year | Year {year} |\n"
        f"| Book life (financial reporting) | {life + 3} years, straight-line |\n\n"
        f"Applicable recovery table ({life}-year):\n\n"
        f"| Recovery year | Rate |\n|---|---:|\n{rows}\n"
    )
    policy = """# Cost-recovery conventions (applies to this task)

- The tax deduction for a recovery year is asset basis x the table rate
  for that recovery year (use the rates exactly as given). Book
  straight-line depreciation over the longer book life is not the tax
  deduction.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "cost-recovery deduction",
        "Using `/app/documents/cost_recovery.md` and `/app/policy.md`, compute "
        f"the **Year {year} cost-recovery deduction** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="tax-cost-recovery-deduction",
        family="income-taxes",
        title="Compute a tax cost-recovery deduction",
        question=question,
        policy=policy,
        data_name="cost_recovery.md",
        data=data,
        gold=gold,
        seed=seed,
        category="tax",
        keywords=["numeric", "cost-recovery", "macrs-table"],
        abs_tolerance="0.01",
        trap_value=money(book),
    )


def passthrough_loss_limitation(seed: int) -> TaskInstance:
    """Numeric: currently deductible passthrough loss through three limits.

    Trap: stopping at the basis limitation.
    """
    rng = random.Random(seed)

    def amt(lo, hi):
        return Decimal(rng.randrange(lo, hi)) * 1000

    passive_income = amt(10, 51)
    at_risk = passive_income + amt(10, 51)
    basis = at_risk + amt(10, 61)
    loss = basis + amt(10, 71)
    data = (
        "# Passthrough loss data — 2025\n\n| Item | USD |\n|---|---:|\n"
        f"| Share of passthrough ordinary loss | {money(loss)} |\n"
        f"| Owner's adjusted basis before the loss | {money(basis)} |\n"
        f"| Amount at risk | {money(at_risk)} |\n"
        f"| Passive income from other activities | {money(passive_income)} |\n"
    )
    policy = """# Loss limitation conventions (applies to this task)

Apply the limits in this order, each capping the deductible amount:
1. Basis limit: no more than adjusted basis.
2. At-risk limit: no more than the amount at risk.
3. Passive limit: a passive loss is currently deductible only up to
   passive income. The currently deductible loss is the smallest of
   the loss and the three limits. Answer in USD.
"""
    question = _numeric_question(
        "currently deductible passthrough loss",
        "Using `/app/documents/loss_limits.md` and `/app/policy.md`, compute "
        "the **currently deductible loss** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="passthrough-loss-limitation",
        family="passthrough-taxation",
        title="Apply passthrough loss limitations",
        question=question,
        policy=policy,
        data_name="loss_limits.md",
        data=data,
        gold=passive_income,
        seed=seed,
        category="tax",
        keywords=["numeric", "loss-limitations", "basis", "at-risk", "passive"],
        abs_tolerance="0.01",
        trap_value=money(basis),
    )


def partnership_distribution_gain(seed: int) -> TaskInstance:
    """Numeric: gain when a cash distribution exceeds outside basis.

    Trap: treating the whole distribution as taxable income.
    """
    rng = random.Random(seed)

    def amt(lo, hi):
        return Decimal(rng.randrange(lo, hi)) * 1000

    basis = amt(20, 101)
    gain = amt(5, 51)
    distribution = basis + gain
    data = (
        "# Partnership distribution — 2025\n\n| Item | USD |\n|---|---:|\n"
        f"| Partner's outside basis before the distribution | {money(basis)} |\n"
        f"| Cash distribution received | {money(distribution)} |\n"
    )
    policy = """# Partnership distribution conventions (applies to this task)

- A cash distribution is tax-free up to outside basis; only cash in
  EXCESS of basis is recognized as gain. Basis cannot go below zero.
- Answer the gain in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "gain on a partnership cash distribution",
        "Using `/app/documents/distribution.md` and `/app/policy.md`, compute "
        "the partner's **gain on the distribution** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="partnership-distribution-gain",
        family="passthrough-taxation",
        title="Compute gain on an excess cash distribution",
        question=question,
        policy=policy,
        data_name="distribution.md",
        data=data,
        gold=gain,
        seed=seed,
        category="tax",
        keywords=["numeric", "partnership", "distribution-gain", "outside-basis"],
        abs_tolerance="0.01",
        trap_value=money(distribution),
    )


def sample_misstatement_projection(seed: int) -> TaskInstance:
    """Numeric: ratio projection of a sample misstatement.

    Trap: reporting only the known sample misstatement.
    """
    rng = random.Random(seed)
    population = Decimal(rng.randrange(400, 1201)) * 1000
    sample_book = Decimal(rng.randrange(50, 201)) * 1000
    pct = rng.choice([Decimal("0.02"), Decimal("0.03"), Decimal("0.05")])
    sample_error = sample_book * pct
    gold = population * pct
    sample_audited = sample_book - sample_error
    data = (
        "# Audit sampling results\n\n| Item | USD |\n|---|---:|\n"
        f"| Recorded population book value | {money(population)} |\n"
        f"| Book value of items sampled | {money(sample_book)} |\n"
        f"| Audited value of items sampled | {money(sample_audited)} |\n"
    )
    policy = """# Ratio projection conventions (applies to this task)

- Projected misstatement = (sample book value - sample audited value)
  / sample book value x recorded population book value.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "projected population misstatement",
        "Using `/app/documents/sampling_results.md` and `/app/policy.md`, compute "
        "the **projected misstatement** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="sample-misstatement-projection",
        family="audit-sampling",
        title="Project a sample misstatement to the population",
        question=question,
        policy=policy,
        data_name="sampling_results.md",
        data=data,
        gold=gold,
        seed=seed,
        category="audit-assurance",
        keywords=["numeric", "audit-sampling", "projection"],
        abs_tolerance="0.01",
        trap_value=money(sample_error),
    )


def capm_expected_return(seed: int) -> TaskInstance:
    """Numeric: expected return under CAPM. Trap: adding beta x market return."""
    rng = random.Random(seed)
    risk_free = rng.choice([Decimal("2.00"), Decimal("3.00"), Decimal("4.00")])
    market = risk_free + Decimal(rng.randrange(4, 9))
    beta = (Decimal(rng.randrange(6, 17)) / 10).quantize(Decimal("0.1"))
    gold = (risk_free + beta * (market - risk_free)).quantize(Decimal("0.0001"))
    trap = (risk_free + beta * market).quantize(Decimal("0.0001"))
    data = (
        "# Market data\n\n| Item | Value |\n|---|---:|\n"
        f"| Risk-free rate | {risk_free:.2f}% |\n"
        f"| Expected market return | {market:.2f}% |\n"
        f"| Stock beta | {format(beta, 'f')} |\n"
    )
    policy = """# CAPM conventions (applies to this task)

- Expected return = risk-free rate + beta x (expected market return
  - risk-free rate). The market risk premium is the excess over the
  risk-free rate, not the whole market return.
- Answer as a percentage number (for example 9.60 for 9.60%).
"""
    question = _numeric_question(
        "expected return under CAPM",
        "Using `/app/documents/market_data.md` and `/app/policy.md`, compute "
        "the stock's **expected return** as a percentage number.",
        "the percentage number",
    )
    return _numeric_instance(
        task_id="capm-expected-return",
        family="cost-of-capital",
        title="Compute expected return under CAPM",
        question=question,
        policy=policy,
        data_name="market_data.md",
        data=data,
        gold=gold,
        seed=seed,
        category="management-accounting",
        keywords=["numeric", "capm", "expected-return", "beta"],
        abs_tolerance="0.01",
        trap_value=format(trap, "f"),
    )


def duplicate_payments_total(seed: int) -> TaskInstance:
    """Numeric: duplicate-payment overpayment from an audit data extract.

    Trap: counting the first legitimate payment in each duplicate set.
    """
    rng = random.Random(seed)
    vendors = ["Acme", "Beacon", "Cobalt", "Delta", "Ember", "Fjord"]
    rows: list[tuple[str, str, Decimal]] = []
    gold = Decimal("0")
    all_duplicate_payments = Decimal("0")
    for i, vendor in enumerate(vendors[:3]):
        amount = Decimal(rng.randrange(20, 121)) * 25
        copies = rng.choice([2, 3])
        gold += amount * (copies - 1)
        all_duplicate_payments += amount * copies
        rows.extend([(vendor, f"INV-10{i + 1}", amount)] * copies)
    for i, vendor in enumerate(vendors[3:]):
        amount = Decimal(rng.randrange(20, 121)) * 25
        rows.append((vendor, f"INV-20{i + 1}", amount))
        # Same amount but a different invoice is not a duplicate.
        rows.append((vendor, f"INV-30{i + 1}", amount))
    rng.shuffle(rows)
    body = "\n".join(
        f"| {vendor} | {invoice} | {money(amount)} |" for vendor, invoice, amount in rows
    )
    data = (
        "# Accounts-payable payment extract\n\n"
        "| Vendor | Invoice | Paid (USD) |\n|---|---|---:|\n" + body + "\n"
    )
    policy = """# Duplicate-payment conventions (applies to this task)

- A duplicate payment is a repeated payment of the same vendor, same
  invoice number, and same amount. The overpayment is the amount paid
  BEYOND the first legitimate payment in each duplicate set.
- Different invoice numbers are not duplicates even if amounts match.
- Answer in USD in `/app/answer.json`.
"""
    question = _numeric_question(
        "duplicate-payment overpayment",
        "Using `/app/documents/payment_extract.md` and `/app/policy.md`, compute "
        "**total duplicate overpayments** in USD.",
        "the USD amount",
    )
    return _numeric_instance(
        task_id="duplicate-payments-total",
        family="audit-analytics",
        title="Total duplicate payments in an AP extract",
        question=question,
        policy=policy,
        data_name="payment_extract.md",
        data=data,
        gold=gold,
        seed=seed,
        category="audit-assurance",
        keywords=["numeric", "audit-analytics", "duplicate-payments"],
        abs_tolerance="0.01",
        trap_value=money(all_duplicate_payments),
    )


AUDIT_PROCEDURES = [
    "External confirmation with the bank/customer",
    "Physical inspection / observation of the asset",
    "Recalculation of the client's computation",
    "Inspection of supporting documents (vouching)",
    "Cutoff testing around the reporting date",
]
AUDIT_PROCEDURE_CASES = [
    (
        "Verify the EXISTENCE and rights of the year-end bank balance.",
        "External confirmation with the bank/customer",
    ),
    (
        "Verify the EXISTENCE of inventory recorded on the balance sheet.",
        "Physical inspection / observation of the asset",
    ),
    (
        "Check the ACCURACY of the depreciation charge for the year.",
        "Recalculation of the client's computation",
    ),
    (
        "Verify that a recorded purchase OCCURRED and is supported by a "
        "supplier invoice and receiving report.",
        "Inspection of supporting documents (vouching)",
    ),
    (
        "Check that sales around year-end are recorded in the CORRECT "
        "period (neither early nor late).",
        "Cutoff testing around the reporting date",
    ),
    (
        "Confirm accounts receivable balances directly with customers for existence and rights.",
        "External confirmation with the bank/customer",
    ),
]


def sc_audit_procedure_selection(seed: int) -> TaskInstance:
    """Single-choice: select the audit procedure for a stated assertion."""
    rng = random.Random(seed)
    narrative, correct = rng.choice(AUDIT_PROCEDURE_CASES)
    labels = AUDIT_PROCEDURES.copy()
    rng.shuffle(labels)
    option_ids = ["A", "B", "C", "D", "E"]
    gold = option_ids[labels.index(correct)]
    options_md = "\n".join(f"- {oid}. {name}" for oid, name in zip(option_ids, labels, strict=True))
    policy = """# Audit procedure selection (applies to this task)

Match the procedure to its primary purpose:
- External confirmation: existence/rights evidence from third parties.
- Physical inspection/observation: existence of tangible assets.
- Recalculation: mathematical accuracy of client computations.
- Vouching to documents: occurrence/support for recorded transactions.
- Cutoff testing: transactions recorded in the correct period.
"""
    question = _choice_question(
        "most appropriate audit procedure",
        f"Audit objective: **{narrative}**\n\nUsing `/app/policy.md`, select "
        "the most appropriate procedure. Select exactly one option.",
        options_md,
        '"B"',
    )
    return TaskInstance(
        task_id="sc-audit-procedure-selection",
        family="audit-evidence",
        title="Select an audit procedure for an assertion",
        instruction=(
            "Answer the single-choice question in `/app/question.md` "
            "following `/app/policy.md`. Write your selection to "
            "`/app/answer.json` in the exact format shown in the question."
        ),
        app_files={
            "question.md": question,
            "policy.md": policy,
            "answer.example.json": '{\n  "final_answer": "A",\n  "confidence": 50\n}\n',
        },
        expected=_expected(
            "sc-audit-procedure-selection",
            "audit-evidence",
            seed,
            format="single-choice",
            gold=gold,
            options=option_ids,
            expected_deltas={},
            expected_new_transactions=0,
            expected_period=None,
        ),
        solution_ledger="",
        solution_answer={"final_answer": gold, "confidence": 100},
        category="audit-assurance",
        keywords=["single-choice", "audit-procedures", "assertions"],
        level="vocational",
        format="single-choice",
        skill="application",
    )


CONTROL_RESPONSES = [
    "Segregate authorization, custody, and recording duties",
    "Require independent bank reconciliation and review",
    "Restrict and log privileged system access with periodic review",
    "Require documented approval before payment release",
    "Perform periodic surprise counts and reconcile to records",
]
CONTROL_GAP_CASES = [
    (
        "One clerk can create a vendor, enter its invoice, and release "
        "payment without anyone else involved.",
        "Segregate authorization, custody, and recording duties",
    ),
    (
        "The person who signs checks also prepares the only bank "
        "reconciliation, and differences are never reviewed.",
        "Require independent bank reconciliation and review",
    ),
    (
        "Several former employees still have administrator access, and "
        "no one reviews who can change prices in the sales system.",
        "Restrict and log privileged system access with periodic review",
    ),
    (
        "Payments leave the bank on a clerk's say-so; no evidence shows a "
        "manager approved the disbursement beforehand.",
        "Require documented approval before payment release",
    ),
    (
        "Warehouse stock records are accepted without ever counting the "
        "physical goods or investigating differences.",
        "Perform periodic surprise counts and reconcile to records",
    ),
]


def sc_control_design_gap(seed: int) -> TaskInstance:
    """Single-choice: choose the control that best addresses a stated gap."""
    rng = random.Random(seed)
    narrative, correct = rng.choice(CONTROL_GAP_CASES)
    labels = CONTROL_RESPONSES.copy()
    rng.shuffle(labels)
    option_ids = ["A", "B", "C", "D", "E"]
    gold = option_ids[labels.index(correct)]
    options_md = "\n".join(f"- {oid}. {name}" for oid, name in zip(option_ids, labels, strict=True))
    policy = """# Control design (applies to this task)

Match the remedy to the weakness:
- Incompatible duties concentrated in one person: segregation of duties.
- Reconciliations prepared by the person handling cash, unreviewed:
  independent preparation/review.
- Excess or stale privileged access: restrict, log, and review access.
- Payments released without evidence of approval: prior documented
  authorization.
- Records never checked to physical assets: periodic surprise counts
  reconciled to records, with differences investigated.
"""
    question = _choice_question(
        "best control for a design gap",
        f"Control weakness: **{narrative}**\n\nUsing `/app/policy.md`, which "
        "control best addresses it? Select exactly one option.",
        options_md,
        '"B"',
    )
    return TaskInstance(
        task_id="sc-control-design-gap",
        family="internal-control",
        title="Match a control weakness to its remedy",
        instruction=(
            "Answer the single-choice question in `/app/question.md` "
            "following `/app/policy.md`. Write your selection to "
            "`/app/answer.json` in the exact format shown in the question."
        ),
        app_files={
            "question.md": question,
            "policy.md": policy,
            "answer.example.json": '{\n  "final_answer": "A",\n  "confidence": 50\n}\n',
        },
        expected=_expected(
            "sc-control-design-gap",
            "internal-control",
            seed,
            format="single-choice",
            gold=gold,
            options=option_ids,
            expected_deltas={},
            expected_new_transactions=0,
            expected_period=None,
        ),
        solution_ledger="",
        solution_answer={"final_answer": gold, "confidence": 100},
        category="audit-assurance",
        keywords=["single-choice", "internal-control", "segregation-of-duties"],
        level="vocational",
        format="single-choice",
        skill="application",
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
    "capitalized-cost-bundle": capitalized_cost_bundle,
    "employer-payroll-taxes": employer_payroll_taxes,
    "current-portion-reclass": current_portion_reclass,
    "periodic-purchase-with-freight": periodic_purchase_with_freight,
    "bad-debt-percent-of-sales": bad_debt_percent_of_sales,
    "cash-discount-receipt": cash_discount_receipt,
    "abc-overhead-assigned": abc_overhead_assigned,
    "high-low-variable-cost": high_low_variable_cost,
    "cash-collections-budget": cash_collections_budget,
    "gross-profit-from-trial-balance": gross_profit_from_trial_balance,
    "ending-retained-earnings": ending_retained_earnings,
    "present-value-lump-sum": present_value_lump_sum,
    "flexible-budget-total-cost": flexible_budget_total_cost,
    "narrative-multi-transactions": narrative_multi_transactions,
    "units-of-production-depreciation": units_of_production_depreciation,
    "warranty-provision-and-claims": warranty_provision_and_claims,
    "sales-tax-collection": sales_tax_collection,
    "petty-cash-replenishment": petty_cash_replenishment,
    "small-stock-dividend": small_stock_dividend,
    "accounting-equation-missing-equity": accounting_equation_missing_equity,
    "current-income-tax-expense": current_income_tax_expense,
    "lease-liability-present-value": lease_liability_present_value,
    "equity-method-carrying-amount": equity_method_carrying_amount,
    "bond-issue-price": bond_issue_price,
    "partnership-income-allocation": partnership_income_allocation,
    "mc-normal-balances": mc_normal_balances,
    "sc-special-journal-routing": sc_special_journal_routing,
    "short-term-note-payment": short_term_note_payment,
    "credit-card-sale-fee": credit_card_sale_fee,
    "patent-amortization": patent_amortization,
    "loss-contingency-accrual": loss_contingency_accrual,
    "bond-issued-at-premium": bond_issued_at_premium,
    "closing-drawing-account": closing_drawing_account,
    "trading-securities-fair-value": trading_securities_fair_value,
    "materials-quantity-variance": materials_quantity_variance,
    "cost-of-goods-manufactured": cost_of_goods_manufactured,
    "payback-period-years": payback_period_years,
    "multiproduct-breakeven-units": multiproduct_breakeven_units,
    "total-current-liabilities": total_current_liabilities,
    "sc-cash-flow-classification": sc_cash_flow_classification,
    "inventory-shrinkage-adjustment": inventory_shrinkage_adjustment,
    "purchase-return-perpetual": purchase_return_perpetual,
    "overhead-variance-disposition": overhead_variance_disposition,
    "unearned-revenue-release": unearned_revenue_release,
    "bond-early-retirement": bond_early_retirement,
    "fvoci-fair-value-adjustment": fvoci_fair_value_adjustment,
    "basket-purchase-allocation": basket_purchase_allocation,
    "labor-efficiency-variance": labor_efficiency_variance,
    "diluted-eps": diluted_eps,
    "asset-turnover-ratio": asset_turnover_ratio,
    "breakeven-sales-dollars": breakeven_sales_dollars,
    "direct-materials-used": direct_materials_used,
    "sc-subsequent-event-classification": sc_subsequent_event_classification,
    "treasury-stock-reissuance": treasury_stock_reissuance,
    "lease-initial-recognition": lease_initial_recognition,
    "fx-payable-remeasurement": fx_payable_remeasurement,
    "development-cost-capitalization": development_cost_capitalization,
    "inventory-error-correction": inventory_error_correction,
    "long-lived-asset-impairment": long_lived_asset_impairment,
    "production-budget-units": production_budget_units,
    "predetermined-overhead-applied": predetermined_overhead_applied,
    "interim-income-tax-expense": interim_income_tax_expense,
    "segment-margin": segment_margin,
    "residual-income": residual_income,
    "cash-collected-from-customers": cash_collected_from_customers,
    "free-cash-flow": free_cash_flow,
    "sc-transaction-statement-impact": sc_transaction_statement_impact,
    "business-combination-acquisition": business_combination_acquisition,
    "consolidation-intercompany-elimination": consolidation_intercompany_elimination,
    "held-for-sale-measurement": held_for_sale_measurement,
    "share-based-compensation-monthly": share_based_compensation_monthly,
    "asset-revaluation-surplus": asset_revaluation_surplus,
    "written-off-receivable-recovery": written_off_receivable_recovery,
    "nfp-conditional-vs-unconditional": nfp_conditional_vs_unconditional,
    "adjusted-receivable-balance": adjusted_receivable_balance,
    "ppe-additions-inferred": ppe_additions_inferred,
    "fixed-overhead-volume-variance": fixed_overhead_volume_variance,
    "cumulative-preferred-dividend": cumulative_preferred_dividend,
    "weighted-average-cost-of-capital": weighted_average_cost_of_capital,
    "standard-cost-per-unit": standard_cost_per_unit,
    "sc-job-vs-process-costing": sc_job_vs_process_costing,
    "government-grant-release": government_grant_release,
    "investment-property-fair-value": investment_property_fair_value,
    "goodwill-impairment": goodwill_impairment,
    "fx-translation-adjustment": fx_translation_adjustment,
    "sale-and-leaseback-entry": sale_and_leaseback_entry,
    "debt-security-credit-loss": debt_security_credit_loss,
    "trial-balance-debit-total": trial_balance_debit_total,
    "post-closing-debit-total": post_closing_debit_total,
    "adjusted-wage-expense": adjusted_wage_expense,
    "inventory-method-profit-difference": inventory_method_profit_difference,
    "minimum-transfer-price": minimum_transfer_price,
    "debt-modification-percent-change": debt_modification_percent_change,
    "mc-temporary-accounts": mc_temporary_accounts,
    "sc-fair-value-hierarchy": sc_fair_value_hierarchy,
    "deferred-tax-asset-warranty": deferred_tax_asset_warranty,
    "consignment-sale-recognition": consignment_sale_recognition,
    "natural-resource-depletion": natural_resource_depletion,
    "internal-use-software-costs": internal_use_software_costs,
    "lessor-sales-type-lease": lessor_sales_type_lease,
    "factoring-secured-borrowing": factoring_secured_borrowing,
    "pension-expense-and-contribution": pension_expense_and_contribution,
    "irr-from-annuity-factor": irr_from_annuity_factor,
    "c-corporation-taxable-income": c_corporation_taxable_income,
    "s-corporation-aaa-ending": s_corporation_aaa_ending,
    "partnership-outside-basis": partnership_outside_basis,
    "performance-materiality": performance_materiality,
    "cash-and-equivalents-total": cash_and_equivalents_total,
    "sc-investment-classification": sc_investment_classification,
    "mc-reportable-segments": mc_reportable_segments,
    "cash-flow-hedge-fair-value": cash_flow_hedge_fair_value,
    "provision-rollforward-topup": provision_rollforward_topup,
    "partnership-admission-bonus": partnership_admission_bonus,
    "governmental-encumbrance-entry": governmental_encumbrance_entry,
    "contract-acquisition-cost": contract_acquisition_cost,
    "aro-accretion": aro_accretion,
    "tax-return-crossfoot-difference": tax_return_crossfoot_difference,
    "tax-cost-recovery-deduction": tax_cost_recovery_deduction,
    "passthrough-loss-limitation": passthrough_loss_limitation,
    "partnership-distribution-gain": partnership_distribution_gain,
    "sample-misstatement-projection": sample_misstatement_projection,
    "capm-expected-return": capm_expected_return,
    "duplicate-payments-total": duplicate_payments_total,
    "sc-audit-procedure-selection": sc_audit_procedure_selection,
    "sc-control-design-gap": sc_control_design_gap,
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
    "capitalized-cost-bundle": 141,
    "employer-payroll-taxes": 142,
    "current-portion-reclass": 143,
    "periodic-purchase-with-freight": 144,
    "bad-debt-percent-of-sales": 145,
    "cash-discount-receipt": 146,
    "abc-overhead-assigned": 147,
    "high-low-variable-cost": 148,
    "cash-collections-budget": 149,
    "gross-profit-from-trial-balance": 150,
    "ending-retained-earnings": 151,
    "present-value-lump-sum": 152,
    "flexible-budget-total-cost": 153,
    "narrative-multi-transactions": 154,
    "units-of-production-depreciation": 155,
    "warranty-provision-and-claims": 156,
    "sales-tax-collection": 157,
    "petty-cash-replenishment": 158,
    "small-stock-dividend": 159,
    "accounting-equation-missing-equity": 160,
    "current-income-tax-expense": 161,
    "lease-liability-present-value": 162,
    "equity-method-carrying-amount": 163,
    "bond-issue-price": 164,
    "partnership-income-allocation": 165,
    "mc-normal-balances": 166,
    "sc-special-journal-routing": 167,
    "short-term-note-payment": 168,
    "credit-card-sale-fee": 169,
    "patent-amortization": 170,
    "loss-contingency-accrual": 171,
    "bond-issued-at-premium": 172,
    "closing-drawing-account": 173,
    "trading-securities-fair-value": 174,
    "materials-quantity-variance": 175,
    "cost-of-goods-manufactured": 176,
    "payback-period-years": 177,
    "multiproduct-breakeven-units": 178,
    "total-current-liabilities": 179,
    "sc-cash-flow-classification": 180,
    "inventory-shrinkage-adjustment": 181,
    "purchase-return-perpetual": 182,
    "overhead-variance-disposition": 183,
    "unearned-revenue-release": 184,
    "bond-early-retirement": 185,
    "fvoci-fair-value-adjustment": 186,
    "basket-purchase-allocation": 187,
    "labor-efficiency-variance": 188,
    "diluted-eps": 189,
    "asset-turnover-ratio": 190,
    "breakeven-sales-dollars": 191,
    "direct-materials-used": 192,
    "sc-subsequent-event-classification": 193,
    "treasury-stock-reissuance": 194,
    "lease-initial-recognition": 195,
    "fx-payable-remeasurement": 196,
    "development-cost-capitalization": 197,
    "inventory-error-correction": 198,
    "long-lived-asset-impairment": 199,
    "production-budget-units": 200,
    "predetermined-overhead-applied": 201,
    "interim-income-tax-expense": 202,
    "segment-margin": 203,
    "residual-income": 204,
    "cash-collected-from-customers": 205,
    "free-cash-flow": 206,
    "sc-transaction-statement-impact": 207,
    "business-combination-acquisition": 208,
    "consolidation-intercompany-elimination": 209,
    "held-for-sale-measurement": 210,
    "share-based-compensation-monthly": 211,
    "asset-revaluation-surplus": 212,
    "written-off-receivable-recovery": 213,
    "nfp-conditional-vs-unconditional": 214,
    "adjusted-receivable-balance": 215,
    "ppe-additions-inferred": 216,
    "fixed-overhead-volume-variance": 217,
    "cumulative-preferred-dividend": 218,
    "weighted-average-cost-of-capital": 219,
    "standard-cost-per-unit": 220,
    "sc-job-vs-process-costing": 221,
    "government-grant-release": 222,
    "investment-property-fair-value": 223,
    "goodwill-impairment": 224,
    "fx-translation-adjustment": 225,
    "sale-and-leaseback-entry": 226,
    "debt-security-credit-loss": 227,
    "trial-balance-debit-total": 228,
    "post-closing-debit-total": 229,
    "adjusted-wage-expense": 230,
    "inventory-method-profit-difference": 231,
    "minimum-transfer-price": 232,
    "debt-modification-percent-change": 233,
    "mc-temporary-accounts": 234,
    "sc-fair-value-hierarchy": 235,
    "deferred-tax-asset-warranty": 236,
    "consignment-sale-recognition": 237,
    "natural-resource-depletion": 238,
    "internal-use-software-costs": 239,
    "lessor-sales-type-lease": 240,
    "factoring-secured-borrowing": 241,
    "pension-expense-and-contribution": 242,
    "irr-from-annuity-factor": 243,
    "c-corporation-taxable-income": 244,
    "s-corporation-aaa-ending": 245,
    "partnership-outside-basis": 246,
    "performance-materiality": 247,
    "cash-and-equivalents-total": 248,
    "sc-investment-classification": 249,
    "mc-reportable-segments": 250,
    "cash-flow-hedge-fair-value": 251,
    "provision-rollforward-topup": 252,
    "partnership-admission-bonus": 253,
    "governmental-encumbrance-entry": 254,
    "contract-acquisition-cost": 255,
    "aro-accretion": 256,
    "tax-return-crossfoot-difference": 257,
    "tax-cost-recovery-deduction": 258,
    "passthrough-loss-limitation": 259,
    "partnership-distribution-gain": 260,
    "sample-misstatement-projection": 261,
    "capm-expected-return": 262,
    "duplicate-payments-total": 263,
    "sc-audit-procedure-selection": 264,
    "sc-control-design-gap": 265,
}
