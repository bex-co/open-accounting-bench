"""Task families: parameterized, seed-deterministic accounting scenarios.

Each family is a function ``(seed) -> TaskInstance``. One validated family
yields many distinct instances; the committed tasks under ``tasks/`` are
frozen Stable-track instances (fixed seeds), while the Dynamic track
generates fresh seeds at evaluation time. See docs/task-families.md.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from decimal import Decimal

from oab import GENERATOR_VERSION

CENT = Decimal("0.01")
BANK = "Assets:Bank:Checking"

# Closed vocabularies for the four-axis taxonomy. Extend here (and in
# tasks/manifest.schema.json) before using a new value; never invent
# per-task spellings.
TAXONOMY: dict[str, tuple[str, ...]] = {
    "category": ("financial-accounting", "management-accounting", "tax"),
    "framework": ("core", "ifrs", "us-gaap"),
    "level": ("vocational", "university", "professional"),
    "format": (
        "journal-entry",
        "single-choice",
        "multiple-choice",
        "numeric",
        "open-text",
    ),
}

CHART = [
    ("Assets:Bank:Checking", "Operating bank account"),
    ("Assets:Equipment", "Capitalized equipment (multi-year useful life)"),
    ("Assets:PrepaidInsurance", "Insurance paid in advance"),
    ("Equity:Opening-Balances", "Opening balances"),
    ("Income:Sales", "Sales revenue"),
    ("Expenses:BankFees", "Bank service charges"),
    ("Expenses:Insurance", "Insurance expense for the current period"),
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


def _chart_md() -> str:
    rows = "\n".join(f"- `{account}` — {desc}" for account, desc in CHART)
    return f"# Chart of accounts\n\n{rows}\n"


def _ledger_header(opening_bank: Decimal) -> str:
    opens = "\n".join(f"2026-01-01 open {account} USD" for account, _ in CHART)
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
    # Four-axis taxonomy (docs/task-families.md). Values must stay within
    # TAXONOMY; `oab validate` enforces it.
    category: str = "financial-accounting"
    framework: str = "core"
    level: str = "university"
    format: str = "journal-entry"
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


FAMILIES = {
    "classify-operating-expense": classify_operating_expense,
    "bank-recon-missing-fee": bank_recon_missing_fee,
    "prepaid-insurance-adjustment": prepaid_insurance_adjustment,
    "correct-misclassification": correct_misclassification,
    "mc-capitalization-treatment": mc_capitalization_treatment,
}

# Frozen Stable-track seeds for the committed tasks under tasks/.
STABLE_SEEDS = {
    "classify-operating-expense": 101,
    "bank-recon-missing-fee": 102,
    "prepaid-insurance-adjustment": 103,
    "correct-misclassification": 104,
    "mc-capitalization-treatment": 105,
}
