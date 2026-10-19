#!/usr/bin/env python3
"""Open Accounting Bench verifier core (self-contained, stdlib only).

This single file is the source of truth for grading. The ``oab`` package
imports it, and the task generator copies it verbatim into every Harbor
task as ``tests/grader.py`` so verification is hermetic inside the
separate verifier container (no package install, no network).

It parses a deliberately small, unambiguous subset of Beancount syntax
(``option``, ``open``, ``balance`` assertions, and ``*`` transactions with
explicit or single-elided postings) and scores a final ledger against an
initial ledger plus a machine-readable expectation, in five layers:

1. structural_validity      parses, accounts opened, entries balance
2. semantic_accuracy        required account deltas match (classification)
3. economic_consistency     evidence recorded once, in the right period
4. reconciliation_accuracy  ledger-wide equation + statement balances
5. operational_integrity    history preserved, no unrelated changes

Scoring is state-based: equivalent journal representations that reach the
same accounting state pass. A balanced-but-misclassified entry fails
layer 2 even though it passes layer 1.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

ZERO = Decimal("0")
_DATE = r"\d{4}-\d{2}-\d{2}"
_ACCOUNT = r"[A-Z][A-Za-z0-9-]*(?::[A-Z0-9][A-Za-z0-9-]*)+"
_RE_OPEN = re.compile(rf"^({_DATE})\s+open\s+({_ACCOUNT})\b")
_RE_BALANCE = re.compile(
    rf"^({_DATE})\s+balance\s+({_ACCOUNT})\s+(-?[\d,]+\.\d{{2}}|-?\d+)\s+([A-Z]{{3}})\s*$"
)
_RE_TXN = re.compile(rf"^({_DATE})\s+([*!])\s+(\".*\"|\S.*?)\s*$")
_RE_POSTING = re.compile(
    rf"^\s+({_ACCOUNT})(?:\s+(-?[\d,]+\.\d{{2}}|-?\d+)\s+([A-Z]{{3}}))?\s*(?:;.*)?$"
)
_RE_OPTION = re.compile(r'^option\s+"[^"]*"\s+"[^"]*"\s*$')


@dataclass
class Posting:
    account: str
    amount: Decimal | None  # None = elided, interpolated at balance time
    currency: str | None


@dataclass
class Transaction:
    date: str
    flag: str
    header: str
    postings: list[Posting] = field(default_factory=list)

    def signature(self) -> str:
        parts = sorted(f"{p.account}={p.amount}:{p.currency}" for p in self.postings)
        return f"{self.date}|{';'.join(parts)}"


@dataclass
class Ledger:
    opens: dict[str, str] = field(default_factory=dict)
    transactions: list[Transaction] = field(default_factory=list)
    balances_assertions: list[tuple[str, str, Decimal, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _amount(text: str) -> Decimal:
    return Decimal(text.replace(",", ""))


def parse_ledger(text: str) -> Ledger:
    ledger = Ledger()
    current: Transaction | None = None
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            if not line.startswith((" ", "\t")):
                current = None if not stripped else current
            continue
        if _RE_OPTION.match(stripped):
            current = None
            continue
        m = _RE_OPEN.match(stripped)
        if m:
            ledger.opens[m.group(2)] = m.group(1)
            current = None
            continue
        m = _RE_BALANCE.match(stripped)
        if m:
            try:
                ledger.balances_assertions.append(
                    (m.group(1), m.group(2), _amount(m.group(3)), m.group(4))
                )
            except InvalidOperation:
                ledger.errors.append(f"line {lineno}: bad balance amount")
            current = None
            continue
        m = _RE_TXN.match(stripped)
        if m and not line.startswith((" ", "\t")):
            current = Transaction(date=m.group(1), flag=m.group(2), header=m.group(3))
            ledger.transactions.append(current)
            continue
        m = _RE_POSTING.match(line)
        if m and current is not None:
            amount = None
            if m.group(2) is not None:
                try:
                    amount = _amount(m.group(2))
                except InvalidOperation:
                    ledger.errors.append(f"line {lineno}: bad posting amount")
                    continue
            current.postings.append(Posting(m.group(1), amount, m.group(3)))
            continue
        ledger.errors.append(f"line {lineno}: unrecognized directive: {stripped[:80]}")
    return ledger


def resolve_transactions(ledger: Ledger) -> list[str]:
    """Interpolate elided postings in place; return structural problems."""
    problems: list[str] = []
    for txn in ledger.transactions:
        if len(txn.postings) < 2:
            problems.append(f"{txn.date} {txn.header}: fewer than 2 postings")
            continue
        elided = [p for p in txn.postings if p.amount is None]
        if len(elided) > 1:
            problems.append(f"{txn.date} {txn.header}: more than one elided posting")
            continue
        currencies = {p.currency for p in txn.postings if p.currency}
        if elided:
            if len(currencies) != 1:
                problems.append(f"{txn.date} {txn.header}: cannot infer elided currency")
                continue
            total = sum(p.amount for p in txn.postings if p.amount is not None)
            elided[0].amount = -total
            elided[0].currency = next(iter(currencies))
        for currency in {p.currency for p in txn.postings}:
            total = sum(p.amount for p in txn.postings if p.currency == currency)
            if total != ZERO:
                problems.append(f"{txn.date} {txn.header}: unbalanced in {currency} by {total}")
    return problems


def compute_balances(ledger: Ledger) -> dict[tuple[str, str], Decimal]:
    balances: dict[tuple[str, str], Decimal] = {}
    for txn in ledger.transactions:
        for posting in txn.postings:
            if posting.amount is None or posting.currency is None:
                continue
            key = (posting.account, posting.currency)
            balances[key] = balances.get(key, ZERO) + posting.amount
    return balances


def account_deltas(
    initial: dict[tuple[str, str], Decimal],
    final: dict[tuple[str, str], Decimal],
    currency: str,
) -> dict[str, Decimal]:
    accounts = {a for (a, c) in initial if c == currency} | {a for (a, c) in final if c == currency}
    return {
        account: final.get((account, currency), ZERO) - initial.get((account, currency), ZERO)
        for account in sorted(accounts)
    }


@dataclass
class LayerResult:
    score: float
    passed: bool
    failures: list[str] = field(default_factory=list)


@dataclass
class Report:
    layers: dict[str, LayerResult]

    @property
    def reward(self) -> int:
        return 1 if all(layer.passed for layer in self.layers.values()) else 0

    def to_reward_json(self) -> dict[str, float]:
        rewards = {"reward": self.reward}
        for name, layer in self.layers.items():
            rewards[name] = round(layer.score, 6)
        rewards["partial"] = round(
            sum(layer.score for layer in self.layers.values()) / len(self.layers), 6
        )
        return rewards

    def to_report_json(self) -> dict:
        return {
            "reward": self.to_reward_json(),
            "layers": {
                name: {
                    "score": layer.score,
                    "passed": layer.passed,
                    "failures": layer.failures,
                }
                for name, layer in self.layers.items()
            },
        }


def _close(actual: Decimal, expected: Decimal, tolerance: Decimal) -> bool:
    return abs(actual - expected) <= tolerance


def verify(initial_text: str, final_text: str, expected: dict) -> Report:
    currency = expected.get("currency", "USD")
    tolerance = Decimal(str(expected.get("tolerance", "0.01")))
    expected_deltas = {
        account: Decimal(str(value))
        for account, value in expected.get("expected_deltas", {}).items()
    }
    allowed_extra = set(expected.get("allowed_extra_accounts", []))

    initial = parse_ledger(initial_text)
    resolve_transactions(initial)
    final = parse_ledger(final_text)
    structural_problems = list(final.errors)
    structural_problems += resolve_transactions(final)

    # Layer 1: syntax and structure.
    for txn in final.transactions:
        for posting in txn.postings:
            if posting.account not in final.opens:
                structural_problems.append(
                    f"{txn.date}: posting to unopened account {posting.account}"
                )
    final_balances = compute_balances(final)
    initial_balances = compute_balances(initial)
    for date, account, amount, cur in final.balances_assertions:
        actual = final_balances.get((account, cur), ZERO)
        if not _close(actual, amount, tolerance):
            structural_problems.append(
                f"balance assertion {date} {account}: expected {amount} {cur}, got {actual}"
            )
    structural = LayerResult(
        score=1.0 if not structural_problems else 0.0,
        passed=not structural_problems,
        failures=structural_problems,
    )

    deltas = account_deltas(initial_balances, final_balances, currency)

    # Layer 2: accounting semantics (required deltas reached).
    semantic_failures: list[str] = []
    matched = 0
    for account, want in expected_deltas.items():
        got = deltas.get(account, ZERO)
        if _close(got, want, tolerance):
            matched += 1
        else:
            semantic_failures.append(f"{account}: expected delta {want} {currency}, got {got}")
    semantic = LayerResult(
        score=(matched / len(expected_deltas)) if expected_deltas else 1.0,
        passed=not semantic_failures,
        failures=semantic_failures,
    )

    # Layer 3: economic consistency (evidence once, in period, no duplicates).
    economic_failures: list[str] = []
    initial_sigs = Counter(txn.signature() for txn in initial.transactions)
    final_sigs = Counter(txn.signature() for txn in final.transactions)
    new_count = sum((final_sigs - initial_sigs).values())
    want_new = expected.get("expected_new_transactions")
    if want_new is not None:
        low, high = (want_new, want_new) if isinstance(want_new, int) else want_new
        if not (low <= new_count <= high):
            economic_failures.append(f"expected {low}..{high} new transactions, found {new_count}")
    for sig, count in (final_sigs - initial_sigs).items():
        if count > 1 and sig not in initial_sigs:
            economic_failures.append(f"duplicate new transaction recorded {count}x: {sig}")
    period = expected.get("expected_period")
    if period:
        added = _added_transactions(initial, final)
        for txn in added:
            if not (period[0] <= txn.date <= period[1]):
                economic_failures.append(
                    f"new transaction dated {txn.date} outside period {period[0]}..{period[1]}"
                )
    economic = LayerResult(
        score=1.0 if not economic_failures else 0.0,
        passed=not economic_failures,
        failures=economic_failures,
    )

    # Layer 4: financial reconciliation.
    recon_failures: list[str] = []
    total = sum(v for (_, c), v in final_balances.items() if c == currency)
    if not _close(total, ZERO, tolerance):
        recon_failures.append(f"ledger-wide sum is {total} {currency}, expected 0")
    for account, want in expected.get("required_final_balances", {}).items():
        got = final_balances.get((account, currency), ZERO)
        if not _close(got, Decimal(str(want)), tolerance):
            recon_failures.append(f"{account}: expected final balance {want} {currency}, got {got}")
    statement = expected.get("reconciliation", {})
    if statement:
        account = statement["account"]
        got = final_balances.get((account, currency), ZERO)
        want = Decimal(str(statement["statement_balance"]))
        if not _close(got, want, tolerance):
            recon_failures.append(
                f"{account} does not reconcile to statement: expected {want}, got {got}"
            )
    reconciliation = LayerResult(
        score=1.0 if not recon_failures else 0.0,
        passed=not recon_failures,
        failures=recon_failures,
    )

    # Layer 5: operational integrity.
    integrity_failures: list[str] = []
    for sig, count in initial_sigs.items():
        if final_sigs.get(sig, 0) < count:
            integrity_failures.append(f"initial transaction altered or removed: {sig}")
    for account, delta in deltas.items():
        if account in expected_deltas or account in allowed_extra:
            continue
        if not _close(delta, ZERO, tolerance):
            integrity_failures.append(f"unauthorized change to {account}: delta {delta} {currency}")
    if expected.get("forbid_new_accounts", True):
        for account in sorted(set(final.opens) - set(initial.opens)):
            integrity_failures.append(f"new account opened without authorization: {account}")
    integrity = LayerResult(
        score=1.0 if not integrity_failures else 0.0,
        passed=not integrity_failures,
        failures=integrity_failures,
    )

    return Report(
        layers={
            "structural_validity": structural,
            "semantic_accuracy": semantic,
            "economic_consistency": economic,
            "reconciliation_accuracy": reconciliation,
            "operational_integrity": integrity,
        }
    )


def _added_transactions(initial: Ledger, final: Ledger) -> list[Transaction]:
    remaining = Counter(txn.signature() for txn in initial.transactions)
    added: list[Transaction] = []
    for txn in final.transactions:
        sig = txn.signature()
        if remaining.get(sig, 0) > 0:
            remaining[sig] -= 1
        else:
            added.append(txn)
    return added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OAB ledger verifier")
    parser.add_argument("--ledger", required=True, help="final ledger path")
    parser.add_argument("--initial", required=True, help="initial ledger path")
    parser.add_argument("--expected", required=True, help="expected.json path")
    parser.add_argument(
        "--out",
        default="/logs/verifier",
        help="output directory for reward.json / report.json",
    )
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    try:
        expected = json.loads(Path(args.expected).read_text(encoding="utf-8"))
        initial_text = Path(args.initial).read_text(encoding="utf-8")
        final_text = Path(args.ledger).read_text(encoding="utf-8")
        report = verify(initial_text, final_text, expected)
    except Exception as exc:  # verifier crash: no reward.json, test.sh sentinel fires
        print(f"[verifier] ERROR: {exc}", file=sys.stderr)
        return 2
    (out / "reward.json").write_text(
        json.dumps(report.to_reward_json(), indent=2) + "\n", encoding="utf-8"
    )
    (out / "report.json").write_text(
        json.dumps(report.to_report_json(), indent=2) + "\n", encoding="utf-8"
    )
    for name, layer in report.layers.items():
        status = "PASS" if layer.passed else "FAIL"
        print(f"[verifier] {name}: {status} score={layer.score}")
        for failure in layer.failures:
            print(f"[verifier]   - {failure}")
    print(f"[verifier] reward={report.reward}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
