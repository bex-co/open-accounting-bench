"""Verifier false-accept / false-reject audit.

Each operator below mutates a task's oracle artifact (the solution ledger
or ``answer.json``) into a probe with a declared expected verdict:

- ``false-accept`` probes are wrong answers. The grader must reject them;
  each names the verification layer expected to catch it.
- ``false-reject`` probes are equivalent correct answers (another valid
  Beancount spelling, decomposition, or answer encoding). The grader must
  accept them.

Operators are pure and deterministic: the same task files always yield
the same probes, so audit results are reproducible. An operator returns
``None`` when it does not apply to a task (for example, merging needs two
added transactions and a transaction-count range that admits the merge).

The audit lives outside ``_verifier_core`` on purpose: it exercises the
hermetic grader as a black box and never changes how anything is scored.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from oab._verifier_core import (
    _ACCOUNT,
    _DATE,
    _NUMBER,
    new_transaction_bounds,
    numeric_tolerance,
)
from oab.verify import grade_answer, parse_ledger, resolve_transactions, verify

FALSE_ACCEPT = "false-accept"
FALSE_REJECT = "false-reject"
CENT = Decimal("0.01")

# Built from the grader's own grammar so probes stay inside what it parses;
# the extra groups keep indentation and comments for byte-faithful rewrites.
_RE_HEADER = re.compile(rf"^({_DATE})\s+(\*|!|txn)(\s.*)?$")
_RE_POSTING = re.compile(rf"^(\s+)({_ACCOUNT})(?:\s+({_NUMBER})\s+([A-Z]{{3}}))?\s*(;.*)?$")


@dataclass(frozen=True)
class Probe:
    """One mutated artifact and the verdict a correct grader must give."""

    operator: str
    kind: str  # FALSE_ACCEPT (must be rejected) or FALSE_REJECT (must be accepted)
    layer: str | None  # layer expected to fail, for false-accept probes
    artifact: str
    note: str


@dataclass(frozen=True)
class AuditCase:
    task_id: str
    expected: dict
    oracle: str  # solution ledger text, or solution answer.json text
    initial: str | None = None  # initial ledger text (ledger formats only)

    @property
    def fmt(self) -> str:
        return self.expected.get("format", "journal-entry")


# ---------------------------------------------------------------------------
# Ledger text model: blocks of raw lines, so probes stay byte-faithful except
# for the lines an operator deliberately changes.


@dataclass
class _Posting:
    indent: str
    account: str
    amount: Decimal | None
    currency: str | None
    comment: str | None

    def render(self, amount_text: Callable[[Decimal], str] | None = None) -> str:
        if self.amount is None:
            line = f"{self.indent}{self.account}"
        else:
            text = amount_text(self.amount) if amount_text else _fmt(self.amount)
            line = f"{self.indent}{self.account}  {text} {self.currency}"
        return f"{line}  {self.comment}" if self.comment else line


@dataclass
class _Txn:
    date: str
    flag: str
    rest: str  # payee/narration/tags after the flag, with its leading space
    postings: list[_Posting]
    extra: list[str]  # indented non-posting lines (metadata, comments)

    def render(self, amount_text: Callable[[Decimal], str] | None = None) -> list[str]:
        lines = [f"{self.date} {self.flag}{self.rest}"]
        lines += self.extra
        lines += [p.render(amount_text) for p in self.postings]
        return lines

    def copy(self) -> _Txn:
        return _Txn(
            self.date,
            self.flag,
            self.rest,
            [_Posting(p.indent, p.account, p.amount, p.currency, p.comment) for p in self.postings],
            list(self.extra),
        )


def _fmt(amount: Decimal) -> str:
    return f"{amount.quantize(CENT, rounding=ROUND_HALF_UP):.2f}"


def _blocks(text: str) -> list[list[str]]:
    """Split ledger text into top-level directive blocks (blank lines kept)."""
    blocks: list[list[str]] = []
    for line in text.splitlines():
        if line.startswith((" ", "\t")) and line.strip() and blocks and blocks[-1][0].strip():
            blocks[-1].append(line)
        else:
            blocks.append([line])
    return blocks


def _render(blocks: list[list[str]]) -> str:
    return "\n".join(line for block in blocks for line in block) + "\n"


def _parse_txn(block: list[str]) -> _Txn | None:
    m = _RE_HEADER.match(block[0])
    if not m:
        return None
    postings: list[_Posting] = []
    extra: list[str] = []
    for line in block[1:]:
        pm = _RE_POSTING.match(line)
        if pm:
            amount = Decimal(pm.group(3).replace(",", "")) if pm.group(3) else None
            postings.append(_Posting(pm.group(1), pm.group(2), amount, pm.group(4), pm.group(5)))
        else:
            extra.append(line)
    return _Txn(m.group(1), m.group(2), m.group(3) or "", postings, extra)


def _signature(block: list[str]) -> str | None:
    ledger = parse_ledger("\n".join(block) + "\n")
    if len(ledger.transactions) != 1 or resolve_transactions(ledger):
        return None
    return ledger.transactions[0].signature()


def _transaction_signatures(text: str) -> Counter:
    ledger = parse_ledger(text)
    resolve_transactions(ledger)
    return Counter(txn.signature() for txn in ledger.transactions)


@dataclass
class _LedgerView:
    """Oracle ledger split into initial blocks and the oracle's added txns."""

    blocks: list[list[str]]
    added: list[int]  # indices of added transaction blocks
    last_initial: int | None  # index of the last transaction carried from the initial ledger
    opens: dict[str, str]  # account -> open date, as the grader parses it
    open_currencies: dict[str, set[str]]  # account -> currency constraint

    def txn(self, index: int) -> _Txn:
        txn = _parse_txn(self.blocks[index])
        assert txn is not None
        return txn


def _view(case: AuditCase) -> _LedgerView:
    """Split the oracle into carried and added transactions.

    Mirrors the grader's ``_added_transactions`` multiset matching, but
    keeps block indices so operators can rewrite exact lines.
    """
    initial_sigs = _transaction_signatures(case.initial or "")
    oracle = parse_ledger(case.oracle)
    blocks = _blocks(case.oracle)
    added: list[int] = []
    last_initial: int | None = None
    for index, block in enumerate(blocks):
        if not _RE_HEADER.match(block[0]):
            continue
        sig = _signature(block)
        if sig is not None and initial_sigs.get(sig, 0) > 0:
            initial_sigs[sig] -= 1
            last_initial = index
        else:
            added.append(index)
    return _LedgerView(blocks, added, last_initial, oracle.opens, oracle.open_currencies)


def _explicit(txn: _Txn) -> _Txn | None:
    """Return a copy with any elided posting made explicit (single currency)."""
    out = txn.copy()
    elided = [p for p in out.postings if p.amount is None]
    if not elided:
        return out
    currencies = {p.currency for p in out.postings if p.currency}
    if len(elided) != 1 or len(currencies) != 1:
        return None
    elided[0].amount = -sum(p.amount for p in out.postings if p.amount is not None)
    elided[0].currency = next(iter(currencies))
    return out


def _count_allows(expected: dict, count: int) -> bool:
    """Whether the grader's ``expected_new_transactions`` admits ``count``."""
    bounds = new_transaction_bounds(expected)
    return bounds is None or bounds[0] <= count <= bounds[1]


def _unrelated_accounts(case: AuditCase, view: _LedgerView) -> list[str]:
    """Opened accounts the task neither expects nor allows to move."""
    protected = set(case.expected.get("expected_deltas", {})) | set(
        case.expected.get("allowed_extra_accounts", [])
    )
    protected |= set(case.expected.get("required_final_balances", {}))
    statement = case.expected.get("reconciliation") or {}
    if statement.get("account"):
        protected.add(statement["account"])
    return sorted(a for a in view.opens if a not in protected and not a.startswith("Equity:"))


def _period_date(case: AuditCase, view: _LedgerView) -> str:
    period = case.expected.get("expected_period")
    if period:
        return period[1]
    return view.txn(view.added[0]).date if view.added else "2026-01-31"


def _next_day(day: str) -> str:
    return (date.fromisoformat(day) + timedelta(days=1)).isoformat()


def _replace(view: _LedgerView, index: int, lines: list[str]) -> str:
    blocks = list(view.blocks)
    blocks[index] = lines
    return _render(blocks)


def _edit_last_initial(view: _LedgerView, mutate: Callable[[_Txn], None]) -> str | None:
    if view.last_initial is None:
        return None
    txn = view.txn(view.last_initial)
    mutate(txn)
    return _replace(view, view.last_initial, txn.render())


def _probe(operator: str, kind: str, layer: str | None, note: str, prepare: Callable):
    """Register an operator: ``prepare(case, view)`` builds its input, the
    decorated function returns the probe artifact or ``None`` (not applicable).
    """

    def wrap(fn: Callable) -> Callable:
        def run(case: AuditCase, view: _LedgerView | None = None) -> Probe | None:
            subject = prepare(case, view)
            artifact = None if subject is None else fn(case, subject)
            if artifact is None or artifact == case.oracle:
                return None
            return Probe(operator, kind, layer, artifact, note)

        run.__name__ = fn.__name__
        run.operator = operator  # type: ignore[attr-defined]
        return run

    return wrap


def _ledger_probe(operator: str, kind: str, layer: str | None, note: str):
    def prepare(case: AuditCase, view: _LedgerView | None) -> _LedgerView | None:
        if case.fmt != "journal-entry":
            return None
        return view or _view(case)

    return _probe(operator, kind, layer, note, prepare)


# ---------------------------------------------------------------------------
# Ledger false-accept probes (wrong answers the grader must reject).


@_ledger_probe("nop", FALSE_ACCEPT, "semantic_accuracy", "untouched initial ledger")
def _nop(case: AuditCase, view: _LedgerView) -> str | None:
    return case.initial


@_ledger_probe(
    "delete-initial-transaction",
    FALSE_ACCEPT,
    "operational_integrity",
    "removes an existing transaction from the append-only ledger",
)
def _delete_initial(case: AuditCase, view: _LedgerView) -> str | None:
    if view.last_initial is None:
        return None
    return _render([b for i, b in enumerate(view.blocks) if i != view.last_initial])


@_ledger_probe(
    "edit-initial-amount",
    FALSE_ACCEPT,
    "operational_integrity",
    "doubles every amount of an existing transaction (still balanced)",
)
def _edit_initial_amount(case: AuditCase, view: _LedgerView) -> str | None:
    def double(txn: _Txn) -> None:
        for posting in txn.postings:
            if posting.amount is not None:
                posting.amount *= 2

    return _edit_last_initial(view, double)


@_ledger_probe(
    "edit-initial-narration",
    FALSE_ACCEPT,
    "operational_integrity",
    "rewrites the narration of an existing transaction",
)
def _edit_initial_narration(case: AuditCase, view: _LedgerView) -> str | None:
    def amend(txn: _Txn) -> None:
        if '"' in txn.rest:
            head, _, tail = txn.rest.rpartition('"')
            txn.rest = f'{head} (amended)"{tail}'
        else:
            txn.rest = f'{txn.rest} "amended"'

    return _edit_last_initial(view, amend)


@_ledger_probe(
    "edit-initial-flag",
    FALSE_ACCEPT,
    "operational_integrity",
    "changes an existing transaction's flag",
)
def _edit_initial_flag(case: AuditCase, view: _LedgerView) -> str | None:
    def reflag(txn: _Txn) -> None:
        txn.flag = "!" if txn.flag in {"*", "txn"} else "*"

    return _edit_last_initial(view, reflag)


@_ledger_probe(
    "drop-added-transaction",
    FALSE_ACCEPT,
    "semantic_accuracy",
    "omits one of the required new transactions",
)
def _drop_added(case: AuditCase, view: _LedgerView) -> str | None:
    if not view.added:
        return None
    return _render([b for i, b in enumerate(view.blocks) if i != view.added[0]])


@_ledger_probe(
    "scale-added-amounts",
    FALSE_ACCEPT,
    "semantic_accuracy",
    "posts every new transaction at 1.5x the correct amount (still balanced)",
)
def _scale_added(case: AuditCase, view: _LedgerView) -> str | None:
    if not view.added:
        return None
    blocks = list(view.blocks)
    for index in view.added:
        txn = _explicit(view.txn(index))
        if txn is None:
            return None
        for posting in txn.postings:
            posting.amount = (posting.amount * Decimal("1.5")).quantize(CENT)
        residue = sum(p.amount for p in txn.postings)
        txn.postings[-1].amount -= residue
        blocks[index] = txn.render()
    return _render(blocks)


@_ledger_probe(
    "misclassify-added-posting",
    FALSE_ACCEPT,
    "semantic_accuracy",
    "books one required posting to an unrelated opened account (balanced)",
)
def _misclassify(case: AuditCase, view: _LedgerView) -> str | None:
    targets = _unrelated_accounts(case, view)
    expected = set(case.expected.get("expected_deltas", {}))
    for index in view.added:
        txn = view.txn(index)
        for posting in txn.postings:
            if posting.account in expected and targets:
                posting.account = targets[0]
                return _replace(view, index, txn.render())
    return None


@_ledger_probe(
    "extra-unrelated-transaction",
    FALSE_ACCEPT,
    "operational_integrity",
    "adds a balanced in-period transaction between two unrelated accounts",
)
def _extra_unrelated(case: AuditCase, view: _LedgerView) -> str | None:
    accounts = _unrelated_accounts(case, view)
    if len(accounts) < 2:
        return None
    date = _period_date(case, view)
    currency = case.expected.get("currency", "USD")
    block = [
        f'{date} * "Audit probe" "Unrelated reclassification"',
        f"  {accounts[0]}  100.00 {currency}",
        f"  {accounts[1]}  -100.00 {currency}",
    ]
    return _render([*view.blocks, [""], block])


@_ledger_probe(
    "foreign-currency-side-postings",
    FALSE_ACCEPT,
    "structural_validity",
    "adds balanced EUR postings to accounts opened for USD only",
)
def _foreign_currency(case: AuditCase, view: _LedgerView) -> str | None:
    accounts = _unrelated_accounts(case, view)
    currency = case.expected.get("currency", "USD")
    constrained = [a for a in accounts if currency in view.open_currencies.get(a, set())]
    if len(constrained) < 2 or not view.added:
        return None
    index = view.added[0]
    txn = view.txn(index)
    foreign = "EUR" if currency != "EUR" else "GBP"
    txn.postings += [
        _Posting("  ", constrained[0], Decimal("100.00"), foreign, None),
        _Posting("  ", constrained[1], Decimal("-100.00"), foreign, None),
    ]
    return _replace(view, index, txn.render())


def _unused_open_block(case: AuditCase, view: _LedgerView) -> int | None:
    """Index of the last `open` line for an account no transaction touches."""
    used = {
        posting.account
        for block in view.blocks
        if (txn := _parse_txn(block)) is not None
        for posting in txn.postings
    }
    unrelated = set(_unrelated_accounts(case, view)) - used
    for index in range(len(view.blocks) - 1, -1, -1):
        words = view.blocks[index][0].split()
        if len(words) >= 3 and words[1] == "open" and words[2] in unrelated:
            return index
    return None


@_ledger_probe(
    "delete-initial-open",
    FALSE_ACCEPT,
    "operational_integrity",
    "deletes an existing `open` directive for an unused account",
)
def _delete_initial_open(case: AuditCase, view: _LedgerView) -> str | None:
    index = _unused_open_block(case, view)
    if index is None:
        return None
    return _render([b for i, b in enumerate(view.blocks) if i != index])


@_ledger_probe(
    "edit-initial-open-currency",
    FALSE_ACCEPT,
    "operational_integrity",
    "strips the currency constraint from an existing `open` directive",
)
def _edit_initial_open_currency(case: AuditCase, view: _LedgerView) -> str | None:
    index = _unused_open_block(case, view)
    if index is None:
        return None
    day, _open, account, *_constraint = view.blocks[index][0].split()
    if not _constraint:
        return None
    return _replace(view, index, [f"{day} open {account}"])


@_ledger_probe(
    "outside-period",
    FALSE_ACCEPT,
    "economic_consistency",
    "dates every new transaction the day after the reporting period",
)
def _outside_period(case: AuditCase, view: _LedgerView) -> str | None:
    period = case.expected.get("expected_period")
    if not period or not view.added:
        return None
    blocks = list(view.blocks)
    late = _next_day(period[1])
    for index in view.added:
        txn = view.txn(index)
        txn.date = late
        blocks[index] = txn.render()
    return _render(blocks)


@_ledger_probe(
    "duplicate-added-transaction",
    FALSE_ACCEPT,
    "economic_consistency",
    "records one new transaction twice",
)
def _duplicate_added(case: AuditCase, view: _LedgerView) -> str | None:
    if not view.added:
        return None
    return _render([*view.blocks, [""], view.blocks[view.added[0]]])


@_ledger_probe(
    "open-new-account",
    FALSE_ACCEPT,
    "operational_integrity",
    "opens an unauthorized account and posts a required amount to it",
)
def _open_new_account(case: AuditCase, view: _LedgerView) -> str | None:
    if not case.expected.get("forbid_new_accounts", True) or not view.added:
        return None
    expected = set(case.expected.get("expected_deltas", {}))
    index = view.added[0]
    txn = view.txn(index)
    for posting in txn.postings:
        if posting.account in expected:
            posting.account = "Expenses:AuditProbe"
            break
    else:
        return None
    first_open = min(view.opens.values())
    blocks = list(view.blocks)
    blocks[index] = txn.render()
    currency = case.expected.get("currency", "USD")
    blocks.insert(0, [f"{first_open} open Expenses:AuditProbe {currency}"])
    return _render(blocks)


@_ledger_probe(
    "unbalanced-added-transaction",
    FALSE_ACCEPT,
    "structural_validity",
    "shifts one explicit amount by 0.50 so the entry no longer balances",
)
def _unbalanced(case: AuditCase, view: _LedgerView) -> str | None:
    for index in view.added:
        txn = view.txn(index)
        if txn.postings and all(p.amount is not None for p in txn.postings):
            txn.postings[0].amount += Decimal("0.50")
            return _replace(view, index, txn.render())
    return None


# ---------------------------------------------------------------------------
# Ledger false-reject probes (equivalent correct answers the grader must
# accept).


def _map_added(view: _LedgerView, fn: Callable[[_Txn], list[str] | None]) -> str | None:
    if not view.added:
        return None
    blocks = list(view.blocks)
    changed = False
    for index in view.added:
        lines = fn(view.txn(index))
        if lines is not None:
            blocks[index] = lines
            changed = True
    return _render(blocks) if changed else None


@_ledger_probe(
    "elide-last-posting",
    FALSE_REJECT,
    None,
    "leaves the last posting's amount for Beancount to interpolate",
)
def _elide(case: AuditCase, view: _LedgerView) -> str | None:
    def fn(txn: _Txn) -> list[str] | None:
        currencies = {p.currency for p in txn.postings}
        if any(p.amount is None for p in txn.postings) or len(currencies) != 1:
            return None
        txn.postings[-1].amount = None
        return txn.render()

    return _map_added(view, fn)


@_ledger_probe(
    "reverse-posting-order",
    FALSE_REJECT,
    None,
    "lists each new transaction's postings in reverse order",
)
def _reverse_postings(case: AuditCase, view: _LedgerView) -> str | None:
    def fn(txn: _Txn) -> list[str] | None:
        if len(txn.postings) < 2:
            return None
        txn.postings.reverse()
        return txn.render()

    return _map_added(view, fn)


@_ledger_probe(
    "reverse-transaction-order",
    FALSE_REJECT,
    None,
    "appends the new transactions in reverse order",
)
def _reverse_txns(case: AuditCase, view: _LedgerView) -> str | None:
    if len(view.added) < 2:
        return None
    blocks = list(view.blocks)
    for index, source in zip(view.added, reversed(view.added), strict=True):
        blocks[index] = view.blocks[source]
    return _render(blocks)


@_ledger_probe(
    "thousands-separators",
    FALSE_REJECT,
    None,
    "writes amounts of 1,000 or more with thousands separators",
)
def _thousands(case: AuditCase, view: _LedgerView) -> str | None:
    def fn(txn: _Txn) -> list[str] | None:
        if not any(p.amount is not None and abs(p.amount) >= 1000 for p in txn.postings):
            return None
        return txn.render(lambda a: f"{a.quantize(CENT):,.2f}")

    return _map_added(view, fn)


@_ledger_probe(
    "comments",
    FALSE_REJECT,
    None,
    "adds a comment line and inline posting comments to each new transaction",
)
def _comments(case: AuditCase, view: _LedgerView) -> str | None:
    def fn(txn: _Txn) -> list[str] | None:
        for posting in txn.postings:
            posting.comment = posting.comment or "; per supporting document"
        return ["; audit probe: explanatory comment", *txn.render()]

    return _map_added(view, fn)


@_ledger_probe(
    "transaction-metadata",
    FALSE_REJECT,
    None,
    "adds a Beancount metadata line (key: value) to each new transaction",
)
def _metadata(case: AuditCase, view: _LedgerView) -> str | None:
    def fn(txn: _Txn) -> list[str] | None:
        txn.extra = ['  source: "audit-probe"', *txn.extra]
        return txn.render()

    return _map_added(view, fn)


@_ledger_probe(
    "txn-keyword",
    FALSE_REJECT,
    None,
    "spells the completed flag with the Beancount `txn` keyword",
)
def _txn_keyword(case: AuditCase, view: _LedgerView) -> str | None:
    def fn(txn: _Txn) -> list[str] | None:
        if txn.flag != "*":
            return None
        txn.flag = "txn"
        return txn.render()

    return _map_added(view, fn)


@_ledger_probe(
    "tags-and-links",
    FALSE_REJECT,
    None,
    "adds a #tag and ^link to each new transaction header",
)
def _tags(case: AuditCase, view: _LedgerView) -> str | None:
    def fn(txn: _Txn) -> list[str] | None:
        txn.rest = f"{txn.rest} #month-end ^audit-probe"
        return txn.render()

    return _map_added(view, fn)


@_ledger_probe(
    "trimmed-decimals",
    FALSE_REJECT,
    None,
    "drops trailing zero decimals from amounts (408.70 -> 408.7, 100.00 -> 100)",
)
def _trimmed(case: AuditCase, view: _LedgerView) -> str | None:
    def trim(amount: Decimal) -> str:
        text = _fmt(amount)
        return text.rstrip("0").rstrip(".") if "." in text else text

    def fn(txn: _Txn) -> list[str] | None:
        if not any(p.amount is not None and _fmt(p.amount).endswith("0") for p in txn.postings):
            return None
        return txn.render(trim)

    return _map_added(view, fn)


@_ledger_probe(
    "extra-precision",
    FALSE_REJECT,
    None,
    "writes amounts with three decimals (408.67 -> 408.670)",
)
def _extra_precision(case: AuditCase, view: _LedgerView) -> str | None:
    return _map_added(view, lambda txn: txn.render(lambda a: f"{a.quantize(CENT):.2f}0"))


@_ledger_probe(
    "split-transaction",
    FALSE_REJECT,
    None,
    "splits one new transaction into two (60%/40%) when the count range allows",
)
def _split(case: AuditCase, view: _LedgerView) -> str | None:
    if not view.added or not _count_allows(case.expected, len(view.added) + 1):
        return None
    index = view.added[0]
    txn = _explicit(view.txn(index))
    if txn is None or len({p.currency for p in txn.postings}) != 1:
        return None
    first, second = txn.copy(), txn.copy()
    for a, b, p in zip(first.postings, second.postings, txn.postings, strict=True):
        a.amount = (p.amount * Decimal("0.6")).quantize(CENT)
        b.amount = p.amount - a.amount
    residue = sum(p.amount for p in first.postings)
    first.postings[-1].amount -= residue
    second.postings[-1].amount += residue
    if any(p.amount == 0 for p in first.postings + second.postings):
        return None
    blocks = list(view.blocks)
    blocks[index] = first.render()
    blocks.insert(index + 1, [""])
    blocks.insert(index + 2, second.render())
    return _render(blocks)


@_ledger_probe(
    "merge-transactions",
    FALSE_REJECT,
    None,
    "merges same-dated new transactions into one compound entry when allowed",
)
def _merge(case: AuditCase, view: _LedgerView) -> str | None:
    by_date: dict[str, list[int]] = {}
    for index in view.added:
        by_date.setdefault(view.txn(index).date, []).append(index)
    group = next((g for g in by_date.values() if len(g) >= 2), None)
    if group is None or not _count_allows(case.expected, len(view.added) - len(group) + 1):
        return None
    txns = [_explicit(view.txn(i)) for i in group]
    if any(t is None for t in txns):
        return None
    merged = txns[0].copy()
    merged.extra = []
    for other in txns[1:]:
        merged.postings += other.postings
    dropped = set(group[1:])
    blocks = [b for i, b in enumerate(view.blocks) if i not in dropped]
    blocks[group[0]] = merged.render()
    return _render(blocks)


@_ledger_probe(
    "post-reverse-rebook",
    FALSE_REJECT,
    None,
    "posts a wrong entry, reverses it, then books the oracle entry",
)
def _reverse_rebook(case: AuditCase, view: _LedgerView) -> str | None:
    if not view.added or not _count_allows(case.expected, len(view.added) + 2):
        return None
    accounts = _unrelated_accounts(case, view)
    txn = _explicit(view.txn(view.added[0]))
    if txn is None or not accounts:
        return None
    wrong = txn.copy()
    swapped = next(
        (p for p in wrong.postings if p.account in case.expected.get("expected_deltas", {})),
        None,
    )
    if swapped is None:
        return None
    swapped.account = accounts[0]
    reversal = wrong.copy()
    for posting in reversal.postings:
        posting.amount = -posting.amount
    reversal.rest = ' "Correction" "Reverse misposted entry"'
    wrong.rest = ' "Draft" "Misposted entry"'
    return _render([*view.blocks, [""], wrong.render(), [""], reversal.render()])


@_ledger_probe(
    "tab-indentation-crlf",
    FALSE_REJECT,
    None,
    "indents postings with a tab and uses CRLF line endings",
)
def _tabs_crlf(case: AuditCase, view: _LedgerView) -> str | None:
    def fn(txn: _Txn) -> list[str] | None:
        for posting in txn.postings:
            posting.indent = "\t"
        return txn.render()

    text = _map_added(view, fn)
    return text.replace("\n", "\r\n") if text else None


LEDGER_OPERATORS = [
    _nop,
    _delete_initial,
    _edit_initial_amount,
    _edit_initial_narration,
    _edit_initial_flag,
    _drop_added,
    _scale_added,
    _misclassify,
    _extra_unrelated,
    _foreign_currency,
    _delete_initial_open,
    _edit_initial_open_currency,
    _outside_period,
    _duplicate_added,
    _open_new_account,
    _unbalanced,
    _elide,
    _reverse_postings,
    _reverse_txns,
    _thousands,
    _comments,
    _metadata,
    _txn_keyword,
    _tags,
    _trimmed,
    _extra_precision,
    _split,
    _merge,
    _reverse_rebook,
    _tabs_crlf,
]


# ---------------------------------------------------------------------------
# Answer-file probes (numeric, single-choice, multiple-choice).


def _answer(case: AuditCase) -> dict:
    return json.loads(case.oracle)


def _dump(value: dict) -> str:
    return json.dumps(value, indent=2) + "\n"


def _answer_probe(operator: str, kind: str, formats: set[str], note: str):
    layer = "answer_accuracy" if kind == FALSE_ACCEPT else None

    def prepare(case: AuditCase, _view: _LedgerView | None) -> dict | None:
        return _answer(case) if case.fmt in formats else None

    def wrap(fn: Callable[[AuditCase, dict], dict | str | None]) -> Callable:
        def artifact(case: AuditCase, answer: dict) -> str | None:
            value = fn(case, answer)
            return value if value is None or isinstance(value, str) else _dump(value)

        artifact.__name__ = fn.__name__
        return _probe(operator, kind, layer, note, prepare)(artifact)

    return wrap


def _tolerance(expected: dict) -> Decimal:
    return numeric_tolerance(expected, Decimal(str(expected["gold"])))


NUMERIC = {"numeric"}
CHOICE = {"single-choice", "multiple-choice"}
ALL_ANSWERS = NUMERIC | CHOICE


@_answer_probe("missing-answer", FALSE_ACCEPT, ALL_ANSWERS, "empty answer file")
def _missing_answer(case: AuditCase, answer: dict) -> str:
    return ""


@_answer_probe(
    "outside-tolerance",
    FALSE_ACCEPT,
    NUMERIC,
    "gold plus twice the tolerance plus one cent",
)
def _outside_tolerance(case: AuditCase, answer: dict) -> dict:
    gold = Decimal(str(case.expected["gold"]))
    return {**answer, "final_answer": str(gold + 2 * _tolerance(case.expected) + CENT)}


@_answer_probe("trap-value", FALSE_ACCEPT, NUMERIC, "the family's documented trap value")
def _trap_value(case: AuditCase, answer: dict) -> dict | None:
    trap = case.expected.get("trap_value")
    return None if trap is None else {**answer, "final_answer": str(trap)}


@_answer_probe("non-finite-number", FALSE_ACCEPT, NUMERIC, "JSON NaN as the answer")
def _nan(case: AuditCase, answer: dict) -> str:
    return '{"final_answer": NaN}\n'


@_answer_probe("boolean-answer", FALSE_ACCEPT, NUMERIC, "boolean true as the answer")
def _boolean(case: AuditCase, answer: dict) -> dict:
    return {**answer, "final_answer": True}


@_answer_probe("wrapped-in-list", FALSE_ACCEPT, NUMERIC | {"single-choice"}, "gold inside a list")
def _wrapped(case: AuditCase, answer: dict) -> dict:
    return {**answer, "final_answer": [answer["final_answer"]]}


@_answer_probe("wrong-option", FALSE_ACCEPT, {"single-choice"}, "a different listed option")
def _wrong_option(case: AuditCase, answer: dict) -> dict | None:
    other = next((o for o in case.expected.get("options", []) if o != case.expected["gold"]), None)
    return None if other is None else {**answer, "final_answer": other}


@_answer_probe("superset", FALSE_ACCEPT, {"multiple-choice"}, "gold plus one wrong option")
def _superset(case: AuditCase, answer: dict) -> dict | None:
    gold = case.expected["gold"]
    extra = next((o for o in case.expected.get("options", []) if o not in gold), None)
    return None if extra is None else {**answer, "final_answer": [*gold, extra]}


@_answer_probe("subset", FALSE_ACCEPT, {"multiple-choice"}, "gold minus one option")
def _subset(case: AuditCase, answer: dict) -> dict:
    return {**answer, "final_answer": list(case.expected["gold"])[:-1]}


@_answer_probe("number-as-string", FALSE_REJECT, NUMERIC, "the gold value as a JSON string")
def _as_string(case: AuditCase, answer: dict) -> dict:
    return {**answer, "final_answer": str(case.expected["gold"])}


@_answer_probe("tolerance-edge", FALSE_REJECT, NUMERIC, "gold minus exactly the tolerance")
def _edge(case: AuditCase, answer: dict) -> dict | None:
    tol = _tolerance(case.expected)
    if tol == 0:
        return None
    return {**answer, "final_answer": str(Decimal(str(case.expected["gold"])) - tol)}


@_answer_probe("trailing-zeros", FALSE_REJECT, NUMERIC, "gold written with extra trailing zeros")
def _trailing(case: AuditCase, answer: dict) -> dict:
    gold = str(case.expected["gold"])
    return {**answer, "final_answer": f"{gold}00" if "." in gold else f"{gold}.00"}


@_answer_probe(
    "extra-keys",
    FALSE_REJECT,
    ALL_ANSWERS,
    "adds rationale and confidence keys beside final_answer",
)
def _extra_keys(case: AuditCase, answer: dict) -> dict:
    return {**answer, "rationale": "audit probe", "confidence": 55}


@_answer_probe("reordered", FALSE_REJECT, {"multiple-choice"}, "gold options in reverse order")
def _reordered(case: AuditCase, answer: dict) -> dict | None:
    gold = list(case.expected["gold"])
    return None if len(gold) < 2 else {**answer, "final_answer": gold[::-1]}


ANSWER_OPERATORS = [
    _missing_answer,
    _outside_tolerance,
    _trap_value,
    _nan,
    _boolean,
    _wrapped,
    _wrong_option,
    _superset,
    _subset,
    _as_string,
    _edge,
    _trailing,
    _extra_keys,
    _reordered,
]


def probes(case: AuditCase) -> list[Probe]:
    """Every applicable probe for one task, in operator order."""
    if case.fmt == "journal-entry":
        view = _view(case)
        return [probe for op in LEDGER_OPERATORS if (probe := op(case, view)) is not None]
    return [probe for op in ANSWER_OPERATORS if (probe := op(case)) is not None]


def load_case(task_dir: Path) -> AuditCase | None:
    """Read one generated task; ``None`` for formats the audit does not cover."""
    expected = json.loads((task_dir / "tests" / "expected.json").read_text())
    fmt = expected.get("format", "journal-entry")
    if fmt == "journal-entry":
        return AuditCase(
            task_dir.name,
            expected,
            (task_dir / "solution" / "ledger.beancount").read_text(),
            (task_dir / "tests" / "initial.beancount").read_text(),
        )
    if fmt in ALL_ANSWERS:
        return AuditCase(
            task_dir.name, expected, (task_dir / "solution" / "answer.json").read_text()
        )
    return None


def grade_probe(case: AuditCase, probe: Probe):
    """Grade a probe with the hermetic grader; returns the verifier ``Report``."""
    if case.fmt == "journal-entry":
        return verify(case.initial or "", probe.artifact, case.expected)
    return grade_answer(case.expected, probe.artifact)


# ---------------------------------------------------------------------------
# Running the audit.


@dataclass(frozen=True)
class Outcome:
    task_id: str
    operator: str
    kind: str
    reward: int
    declared_layer: str | None
    failed_layers: tuple[str, ...]

    @property
    def misjudged(self) -> bool:
        return self.reward != (0 if self.kind == FALSE_ACCEPT else 1)

    @property
    def verdict(self) -> str:
        return self.kind if self.misjudged else "ok"

    @property
    def layer_mismatch(self) -> bool:
        """A wrong answer rejected, but not by the layer that should catch it."""
        return (
            self.kind == FALSE_ACCEPT
            and not self.misjudged
            and self.declared_layer not in self.failed_layers
        )


def audit_case(case: AuditCase) -> list[Outcome]:
    outcomes = []
    for probe in probes(case):
        report = grade_probe(case, probe)
        failed = tuple(name for name, layer in report.layers.items() if not layer.passed)
        outcomes.append(
            Outcome(
                case.task_id,
                probe.operator,
                probe.kind,
                report.reward,
                probe.layer,
                failed,
            )
        )
    return outcomes


def task_dirs(tasks_root: Path) -> list[Path]:
    return sorted(p for p in tasks_root.iterdir() if p.is_dir() and (p / "task.toml").exists())


def run_audit(tasks_root: Path, sample: int | None = None) -> tuple[list[Outcome], list[str]]:
    """Audit every (or every ``sample``-th) task; returns outcomes and skipped task ids.

    ``sample=N`` keeps every N-th task in sorted order, a deterministic
    subset for fast CI runs.
    """
    dirs = task_dirs(tasks_root)
    if sample and sample > 1:
        dirs = dirs[::sample]
    outcomes: list[Outcome] = []
    skipped: list[str] = []
    for task_dir in dirs:
        case = load_case(task_dir)
        if case is None:
            skipped.append(task_dir.name)
            continue
        outcomes.extend(audit_case(case))
    return outcomes, skipped


def summarize(outcomes: list[Outcome], skipped: list[str]) -> dict:
    """Machine-readable audit summary (stable key order for byte-identical output)."""
    operators: dict[str, dict] = {}
    for outcome in outcomes:
        row = operators.setdefault(
            outcome.operator,
            {"kind": outcome.kind, "probes": 0, "misjudged": 0, "tasks": []},
        )
        row["probes"] += 1
        if outcome.misjudged:
            row["misjudged"] += 1
            row["tasks"].append(outcome.task_id)
    tasks: dict[str, dict] = {}
    for outcome in outcomes:
        row = tasks.setdefault(
            outcome.task_id, {"probes": 0, "false_accepts": 0, "false_rejects": 0}
        )
        row["probes"] += 1
        if outcome.verdict == "false-accept":
            row["false_accepts"] += 1
        elif outcome.verdict == "false-reject":
            row["false_rejects"] += 1
    fa_probes = [o for o in outcomes if o.kind == FALSE_ACCEPT]
    fr_probes = [o for o in outcomes if o.kind == FALSE_REJECT]
    return {
        "tasks_audited": len(tasks),
        "tasks_skipped": sorted(skipped),
        "probes": len(outcomes),
        "false_accept_probes": len(fa_probes),
        "false_accepts": sum(o.misjudged for o in fa_probes),
        "false_reject_probes": len(fr_probes),
        "false_rejects": sum(o.misjudged for o in fr_probes),
        "layer_mismatches": sorted(
            f"{o.task_id}:{o.operator}" for o in outcomes if o.layer_mismatch
        ),
        "operators": dict(sorted(operators.items())),
        "tasks": dict(sorted(tasks.items())),
    }


def render_markdown(summary: dict) -> str:
    def rate(bad: int, total: int) -> str:
        return f"{bad}/{total} ({bad / total:.1%})" if total else "0/0"

    lines = [
        "# Verifier mutation audit",
        "",
        f"- Tasks audited: {summary['tasks_audited']}"
        + (
            f" (skipped: {', '.join(summary['tasks_skipped'])})" if summary["tasks_skipped"] else ""
        ),
        f"- Probes: {summary['probes']}",
        "- False accepts (wrong answer passed): "
        + rate(summary["false_accepts"], summary["false_accept_probes"]),
        "- False rejects (equivalent answer failed): "
        + rate(summary["false_rejects"], summary["false_reject_probes"]),
        "- Wrong answers caught by a different layer than declared: "
        + str(len(summary["layer_mismatches"])),
        "",
        "| Operator | Probe | Applied | Misjudged | Example tasks |",
        "|---|---|---:|---:|---|",
    ]
    for name, row in summary["operators"].items():
        examples = ", ".join(row["tasks"][:3]) + (" …" if len(row["tasks"]) > 3 else "")
        lines.append(
            f"| `{name}` | {row['kind']} | {row['probes']} | {row['misjudged']} | {examples} |"
        )
    return "\n".join(lines) + "\n"
