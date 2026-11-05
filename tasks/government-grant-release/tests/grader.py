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
_WORKFLOW_FORMAT = "workflow"
_DEFAULT_WORKFLOW_ARTIFACT = "/app/workflow.json"
_DATE = r"\d{4}-\d{2}-\d{2}"
_ACCOUNT = r"[A-Z][A-Za-z0-9-]*(?::[A-Z0-9][A-Za-z0-9-]*)+"
_NUMBER = r"-?[\d,]+(?:\.\d+)?"
_RE_OPEN = re.compile(
    rf"^({_DATE})\s+open\s+({_ACCOUNT})(?:\s+([A-Z]{{3}}(?:\s*,\s*[A-Z]{{3}})*))?\b"
)
_RE_BALANCE = re.compile(rf"^({_DATE})\s+balance\s+({_ACCOUNT})\s+({_NUMBER})\s+([A-Z]{{3}})\s*$")
_RE_TXN = re.compile(rf"^({_DATE})\s+(\*|!|txn)(?:\s+(.*?))?\s*$")
_RE_POSTING = re.compile(rf"^\s+({_ACCOUNT})(?:\s+({_NUMBER})\s+([A-Z]{{3}}))?\s*(?:;.*)?$")
_RE_METADATA = re.compile(r"^\s+[a-z][A-Za-z0-9_-]*:(?:\s.*)?$")
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

    def identity(self) -> str:
        """Signature plus flag and description: what append-only preserves."""
        return f"{self.flag}|{' '.join(self.header.split())}|{self.signature()}"


@dataclass
class Ledger:
    opens: dict[str, str] = field(default_factory=dict)
    open_currencies: dict[str, set[str]] = field(default_factory=dict)
    transactions: list[Transaction] = field(default_factory=list)
    balances_assertions: list[tuple[str, str, Decimal, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _amount(text: str) -> Decimal:
    return Decimal(text.replace(",", ""))


def parse_ledger(text: str) -> Ledger:
    ledger = Ledger()
    current: Transaction | None = None
    in_entry = False  # metadata lines may follow open/balance/txn directives
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            if not line.startswith((" ", "\t")) and not stripped:
                current, in_entry = None, False
            continue
        if _RE_OPTION.match(stripped):
            current, in_entry = None, False
            continue
        m = _RE_OPEN.match(stripped)
        if m:
            ledger.opens[m.group(2)] = m.group(1)
            if m.group(3):
                ledger.open_currencies[m.group(2)] = {c.strip() for c in m.group(3).split(",")}
            current, in_entry = None, True
            continue
        m = _RE_BALANCE.match(stripped)
        if m:
            try:
                ledger.balances_assertions.append(
                    (m.group(1), m.group(2), _amount(m.group(3)), m.group(4))
                )
            except InvalidOperation:
                ledger.errors.append(f"line {lineno}: bad balance amount")
            current, in_entry = None, True
            continue
        m = _RE_TXN.match(stripped)
        if m and not line.startswith((" ", "\t")):
            flag = "*" if m.group(2) == "txn" else m.group(2)
            current = Transaction(date=m.group(1), flag=flag, header=m.group(3) or "")
            ledger.transactions.append(current)
            in_entry = True
            continue
        if in_entry and _RE_METADATA.match(line):
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
    extras: dict[str, float] = field(default_factory=dict)
    details: dict = field(default_factory=dict)

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
        for name, value in self.extras.items():
            rewards[name] = round(float(value), 6)
        return rewards

    def to_report_json(self) -> dict:
        report = {
            "reward": self.to_reward_json(),
            "layers": {
                name: {
                    "score": layer.score,
                    "passed": layer.passed,
                    "failures": layer.failures,
                }
                for name, layer in self.layers.items()
            },
            "extras": self.extras,
        }
        if self.details:
            report["details"] = self.details
        return report


def _close(actual: Decimal, expected: Decimal, tolerance: Decimal) -> bool:
    return abs(actual - expected) <= tolerance


def new_transaction_bounds(expected: dict) -> tuple[int, int] | None:
    """``expected_new_transactions`` as inclusive ``(low, high)``, or None."""
    want = expected.get("expected_new_transactions")
    if want is None:
        return None
    return (want, want) if isinstance(want, int) else (want[0], want[1])


def is_no_action(expected: dict) -> bool:
    """A control whose correct answer appends nothing (zero new transactions)."""
    return new_transaction_bounds(expected) == (0, 0)


def numeric_tolerance(expected: dict, gold: Decimal) -> Decimal:
    """Allowed absolute error for a numeric answer: abs + rel * |gold|."""
    abs_tol = Decimal(str(expected.get("abs_tolerance", "0")))
    rel_tol = Decimal(str(expected.get("rel_tolerance", "0")))
    return abs_tol + rel_tol * abs(gold)


def _parse_resolved_ledger(text: str) -> tuple[Ledger, list[str]]:
    ledger = parse_ledger(text)
    problems = list(ledger.errors)
    problems += resolve_transactions(ledger)
    return ledger, problems


def verify(initial_text: str, final_text: str, expected: dict) -> Report:
    initial, _initial_problems = _parse_resolved_ledger(initial_text)
    final, structural_problems = _parse_resolved_ledger(final_text)
    return _verify_ledgers(initial, final, expected, structural_problems)


def _verify_ledgers(
    initial: Ledger,
    final: Ledger,
    expected: dict,
    structural_problems: list[str],
) -> Report:
    currency = expected.get("currency", "USD")
    tolerance = Decimal(str(expected.get("tolerance", "0.01")))
    expected_deltas = {
        account: Decimal(str(value))
        for account, value in expected.get("expected_deltas", {}).items()
    }
    allowed_extra = set(expected.get("allowed_extra_accounts", []))

    # Layer 1: syntax and structure.
    for txn in final.transactions:
        for posting in txn.postings:
            if posting.account not in final.opens:
                structural_problems.append(
                    f"{txn.date}: posting to unopened account {posting.account}"
                )
            # Constraints declared in the initial ledger bind even if the
            # agent rewrote the `open` line; new accounts use their own.
            allowed = initial.open_currencies.get(
                posting.account, final.open_currencies.get(posting.account)
            )
            if allowed and posting.currency is not None and posting.currency not in allowed:
                structural_problems.append(
                    f"{txn.date}: {posting.currency} posting to {posting.account}, "
                    f"which is open for {', '.join(sorted(allowed))} only"
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
    bounds = new_transaction_bounds(expected)
    if bounds is not None:
        low, high = bounds
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
    # No-action controls (the correct answer adds nothing): report whether
    # the agent acted anyway. Diagnostic only; the layers decide reward.
    extras = {"over_action": 1.0 if new_count else 0.0} if is_no_action(expected) else {}

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
    initial_ids = Counter(txn.identity() for txn in initial.transactions)
    final_ids = Counter(txn.identity() for txn in final.transactions)
    for identity, count in initial_ids.items():
        if final_ids.get(identity, 0) < count:
            integrity_failures.append(f"initial transaction altered or removed: {identity}")
    for account, opened in sorted(initial.opens.items()):
        if final.opens.get(account) != opened or final.open_currencies.get(
            account
        ) != initial.open_currencies.get(account):
            integrity_failures.append(f"initial open directive altered or removed: {account}")
    # Expected deltas are stated in the reporting currency; any other
    # movement, in any currency, is unauthorized unless explicitly allowed.
    for account, cur in sorted(set(initial_balances) | set(final_balances)):
        if account in allowed_extra or (cur == currency and account in expected_deltas):
            continue
        delta = final_balances.get((account, cur), ZERO) - initial_balances.get(
            (account, cur), ZERO
        )
        if not _close(delta, ZERO, tolerance):
            integrity_failures.append(f"unauthorized change to {account}: delta {delta} {cur}")
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
        },
        extras=extras,
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


def _decimal_value(value) -> Decimal | None:
    if isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _json_path_value(value, path: str):
    current = value
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return False, None
    return True, current


@dataclass
class _WorkflowContext:
    deltas: dict[str, Decimal]
    final_balances: dict[tuple[str, str], Decimal]
    postings_by_account: dict[tuple[str, str], list[tuple[str, Decimal | None]]]
    added_dates: list[str]
    json_artifacts: dict[str, object]
    currency: str
    tolerance: Decimal


@dataclass
class _WorkflowOutcome:
    passed: bool
    actual: object
    expected: object
    failure: str | None = None


def _period_account_delta(postings: list[tuple[str, Decimal | None]], period) -> Decimal | None:
    if not isinstance(period, list) or len(period) != 2:
        return None
    start, end = period
    total = ZERO
    for date, amount in postings:
        if not (start <= date <= end):
            continue
        if amount is None:
            return None
        total += amount
    return total


def _numeric_outcome(
    actual: Decimal, expected, tolerance: Decimal, *, invalid_expected: str
) -> _WorkflowOutcome:
    want = _decimal_value(expected)
    if want is None:
        return _WorkflowOutcome(False, str(actual), expected, invalid_expected)
    return _WorkflowOutcome(_close(actual, want, tolerance), str(actual), str(want))


def _parse_workflow_json(
    spec: dict, artifacts: dict | None
) -> tuple[dict[str, object], list[str], bool]:
    artifacts = artifacts or {}
    parsed: dict[str, object] = {}
    failures: list[str] = []
    parse_failure = False
    for artifact in spec.get("artifacts", []):
        if not isinstance(artifact, dict) or artifact.get("kind") != "json":
            continue
        path = artifact.get("path")
        if not isinstance(path, str):
            continue
        required = artifact.get("required", True) is not False
        raw = artifacts.get(path)
        if raw is None:
            if required:
                failures.append(f"required workflow artifact missing: {path}")
                parse_failure = True
            continue
        if isinstance(raw, dict | list):
            parsed[path] = raw
            continue
        if not isinstance(raw, str) or not raw.strip():
            failures.append(f"workflow artifact is empty: {path}")
            parse_failure = True
            continue
        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            failures.append(f"workflow artifact {path} is not valid JSON: {exc}")
            parse_failure = True
            continue
        if not isinstance(value, dict):
            failures.append(f"workflow artifact {path} must contain a JSON object")
            parse_failure = True
            continue
        parsed[path] = value
    return parsed, failures, parse_failure


def load_workflow_artifacts(expected: dict, artifact_root: Path | None) -> dict[str, str | None]:
    """Read declared JSON workflow artifacts below an `/app`-shaped root."""

    artifacts: dict[str, str | None] = {}
    spec = expected.get("workflow", {})
    if not isinstance(spec, dict):
        return artifacts
    for artifact in spec.get("artifacts", []):
        if not isinstance(artifact, dict) or artifact.get("kind") != "json":
            continue
        path = artifact.get("path")
        if not isinstance(path, str):
            continue
        if artifact_root is None:
            artifacts[path] = None
            continue
        candidate = artifact_root / path.removeprefix("/app/")
        artifacts[path] = candidate.read_text(encoding="utf-8") if candidate.exists() else None
    return artifacts


def _workflow_numeric_equal(actual, expected, tolerance: Decimal) -> bool | None:
    actual_decimal = _decimal_value(actual)
    expected_decimal = _decimal_value(expected)
    if actual_decimal is None or expected_decimal is None:
        return None
    return _close(actual_decimal, expected_decimal, tolerance)


def _evaluate_workflow_check(check: dict, context: _WorkflowContext) -> _WorkflowOutcome:
    check_type = check.get("type")
    currency = str(check.get("currency", context.currency))
    tolerance = _decimal_value(check.get("tolerance", context.tolerance))
    if tolerance is None or tolerance < 0:
        return _WorkflowOutcome(False, None, check.get("expected"), "invalid check tolerance")
    account = check.get("account")
    expected = check.get("expected")

    if check_type in {
        "account_delta",
        "final_balance",
        "subledger_cleared",
        "forbidden_account_delta",
    }:
        if not isinstance(account, str):
            return _WorkflowOutcome(False, None, expected, "check account is missing")
        if check_type == "account_delta":
            return _numeric_outcome(
                context.deltas.get(account, ZERO),
                expected,
                tolerance,
                invalid_expected="expected account delta is not numeric",
            )
        if check_type == "final_balance":
            return _numeric_outcome(
                context.final_balances.get((account, currency), ZERO),
                expected,
                tolerance,
                invalid_expected="expected final balance is not numeric",
            )
        actual = (
            context.final_balances.get((account, currency), ZERO)
            if check_type == "subledger_cleared"
            else context.deltas.get(account, ZERO)
        )
        return _WorkflowOutcome(_close(actual, ZERO, tolerance), str(actual), "0")

    if check_type == "period_account_delta":
        if not isinstance(account, str):
            return _WorkflowOutcome(False, None, expected, "check account is missing")
        actual = _period_account_delta(
            context.postings_by_account.get((account, currency), []),
            check.get("period"),
        )
        if actual is None:
            return _WorkflowOutcome(False, None, expected, "invalid period-account-delta check")
        return _numeric_outcome(
            actual,
            expected,
            tolerance,
            invalid_expected="invalid period-account-delta check",
        )

    if check_type == "cutoff_no_transactions":
        period = check.get("period")
        if not isinstance(period, list) or len(period) != 2:
            return _WorkflowOutcome(False, None, period, "invalid cutoff period")
        offenders = [date for date in context.added_dates if period[0] <= date <= period[1]]
        return _WorkflowOutcome(not offenders, offenders, [])

    if check_type in {"evidence_disposition", "json_value", "cross_artifact_balance"}:
        artifact_path = check.get("artifact", _DEFAULT_WORKFLOW_ARTIFACT)
        document = context.json_artifacts.get(artifact_path)
        path = check.get("path")
        if document is None or not isinstance(path, str):
            return _WorkflowOutcome(
                False,
                None,
                expected,
                f"workflow JSON artifact unavailable: {artifact_path}",
            )
        found, actual = _json_path_value(document, path)
        if not found:
            return _WorkflowOutcome(False, None, expected, f"JSON path not found: {path}")
        if check_type == "evidence_disposition":
            key = check.get("key")
            if not isinstance(actual, dict) or not isinstance(key, str) or key not in actual:
                return _WorkflowOutcome(
                    False,
                    None,
                    expected,
                    f"evidence disposition not found: {path}.{key}",
                )
            actual = actual[key]
            return _WorkflowOutcome(actual == expected, actual, expected)
        if check_type == "json_value":
            numeric = _workflow_numeric_equal(actual, expected, tolerance)
            if numeric is not None:
                return _WorkflowOutcome(numeric, actual, expected)
            return _WorkflowOutcome(actual == expected, actual, expected)
        if not isinstance(account, str):
            return _WorkflowOutcome(False, actual, expected, "check account is missing")
        want = context.final_balances.get((account, currency), ZERO)
        numeric = _workflow_numeric_equal(actual, want, tolerance)
        if numeric is None:
            return _WorkflowOutcome(False, actual, str(want), "cross-artifact value is not numeric")
        return _WorkflowOutcome(numeric, actual, str(want))

    return _WorkflowOutcome(False, None, expected, f"unknown workflow check type {check_type!r}")


def grade_workflow(
    initial_text: str,
    final_text: str,
    expected: dict,
    artifacts: dict | None = None,
) -> Report:
    """Grade a ledger-plus-structured-artifact professional workflow.

    The five ledger layers remain the integrity baseline.  The workflow
    layer evaluates typed checks grouped by determination: duplicating one
    assertion cannot earn more than its determination, while every
    ``gate`` check must pass for reward 1.  ``rubric_completion`` is a
    diagnostic in reward extras; it never substitutes for verified
    completion.
    """

    spec = expected.get("workflow")
    if not isinstance(spec, dict):
        spec = {}
    currency = str(expected.get("currency", "USD"))
    tolerance = _decimal_value(expected.get("tolerance", "0.01"))
    if tolerance is None:
        tolerance = Decimal("0.01")

    initial, _initial_problems = _parse_resolved_ledger(initial_text)
    final, structural_problems = _parse_resolved_ledger(final_text)
    base = _verify_ledgers(initial, final, expected, structural_problems)
    final_balances = compute_balances(final)
    initial_balances = compute_balances(initial)
    deltas = account_deltas(initial_balances, final_balances, currency)
    added = _added_transactions(initial, final)
    postings_by_account: dict[tuple[str, str], list[tuple[str, Decimal | None]]] = {}
    for txn in added:
        for posting in txn.postings:
            if posting.currency is None:
                continue
            postings_by_account.setdefault((posting.account, posting.currency), []).append(
                (txn.date, posting.amount)
            )
    json_artifacts, artifact_failures, parse_failure = _parse_workflow_json(spec, artifacts)
    context = _WorkflowContext(
        deltas=deltas,
        final_balances=final_balances,
        postings_by_account=postings_by_account,
        added_dates=[txn.date for txn in added],
        json_artifacts=json_artifacts,
        currency=currency,
        tolerance=tolerance,
    )

    raw_determinations = spec.get("determinations", [])
    determinations: dict[str, dict] = {}
    if isinstance(raw_determinations, list):
        for item in raw_determinations:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                determinations[item["id"]] = item

    raw_checks = spec.get("checks", [])
    checks = (
        [item for item in raw_checks if isinstance(item, dict)]
        if isinstance(raw_checks, list)
        else []
    )
    results: list[dict] = []
    results_by_determination: dict[str, list[dict]] = {
        determination_id: [] for determination_id in determinations
    }
    gate_failures = list(artifact_failures)
    if not determinations:
        gate_failures.append("workflow spec has no determinations")
    if not checks:
        gate_failures.append("workflow spec has no checks")

    for check in checks:
        determination_id = str(check.get("determination", ""))
        determination = determinations.get(determination_id, {})
        outcome = _evaluate_workflow_check(check, context)
        passed = outcome.passed
        failure = outcome.failure
        actual = outcome.actual
        want = outcome.expected
        if determination_id not in determinations:
            passed = False
            failure = f"unknown determination {determination_id!r}"
        result = {
            "id": check.get("id"),
            "type": check.get("type"),
            "determination": determination_id,
            "cluster": determination.get("cluster"),
            "gate": check.get("gate", True) is not False,
            "passed": bool(passed),
            "actual": actual,
            "expected": want,
        }
        if failure:
            result["failure"] = failure
        elif not passed:
            result["failure"] = f"expected {want!r}, got {actual!r}"
        results.append(result)
        if determination_id in results_by_determination:
            results_by_determination[determination_id].append(result)
        if result["gate"] and not passed:
            gate_failures.append(f"{result['id']}: {result['failure']}")

    determination_details: dict[str, dict] = {}
    weighted_total = 0.0
    weight_sum = 0.0
    cluster_values: dict[str, list[tuple[float, float]]] = {}
    for determination_id, determination in determinations.items():
        own = results_by_determination[determination_id]
        score = (sum(1 for item in own if item["passed"]) / len(own)) if own else 0.0
        weight_value = determination.get("weight", 1)
        weight = (
            float(weight_value)
            if isinstance(weight_value, int | float) and float(weight_value) > 0
            else 1.0
        )
        weighted_total += score * weight
        weight_sum += weight
        cluster = str(determination.get("cluster", ""))
        cluster_values.setdefault(cluster, []).append((score, weight))
        determination_details[determination_id] = {
            "cluster": cluster,
            "weight": weight,
            "score": score,
            "passed": bool(own) and all(item["passed"] for item in own if item["gate"]),
            "checks": [item["id"] for item in own],
        }

    rubric_completion = weighted_total / weight_sum if weight_sum else 0.0
    check_completion = (
        sum(1 for item in results if item["passed"]) / len(results) if results else 0.0
    )
    clusters = {
        cluster: sum(score * weight for score, weight in values)
        / sum(weight for _score, weight in values)
        for cluster, values in sorted(cluster_values.items())
    }
    workflow_layer = LayerResult(
        score=rubric_completion,
        passed=not gate_failures,
        failures=gate_failures,
    )
    layers = dict(base.layers)
    layers["workflow_rubric"] = workflow_layer
    extras = dict(base.extras)
    extras.update(
        {
            "rubric_completion": rubric_completion,
            "workflow_check_completion": check_completion,
            "parse_failure": 1.0 if parse_failure else 0.0,
        }
    )
    return Report(
        layers=layers,
        extras=extras,
        details={
            "workflow": {
                "schema_version": spec.get("schema_version"),
                "checks": results,
                "determinations": determination_details,
                "clusters": clusters,
                "rubric_completion": rubric_completion,
                "workflow_check_completion": check_completion,
            }
        },
    )


def grade_answer(expected: dict, answer_text: str | None) -> Report:
    """Grade an answer-file task (single/multiple choice, numeric).

    Answer contract: a JSON object with `final_answer` (option id,
    list of option ids, or number) and optional `confidence` (0-100).
    Anything unparseable scores 0 with parse_failure=1 and stays in
    the denominator. Multiple-choice accuracy uses the penalized
    formula (correct - incorrect marks) / |gold|, which may be
    negative; reward requires exact set equality.
    """
    fmt = expected.get("format", "")
    failures: list[str] = []
    extras: dict[str, float] = {"parse_failure": 0.0}
    answer: dict | None = None
    if not answer_text or not answer_text.strip():
        failures.append("answer file missing or empty")
    else:
        try:
            parsed = json.loads(answer_text)
            if not isinstance(parsed, dict) or "final_answer" not in parsed:
                failures.append("answer JSON must be an object with final_answer")
            else:
                answer = parsed
        except (json.JSONDecodeError, ValueError) as exc:
            failures.append(f"answer is not valid JSON: {exc}")
    if answer is not None:
        confidence = answer.get("confidence")
        if isinstance(confidence, int | float) and 0 <= float(confidence) <= 100:
            extras["confidence"] = float(confidence)
        elif confidence is not None:
            failures.append("confidence ignored: must be a number in 0..100")
    format_layer = LayerResult(
        score=1.0 if answer is not None else 0.0,
        passed=answer is not None,
        failures=failures,
    )
    if answer is None:
        extras["parse_failure"] = 1.0
        accuracy = LayerResult(score=0.0, passed=False, failures=["no parseable answer"])
        return Report(
            layers={"format_validity": format_layer, "answer_accuracy": accuracy},
            extras=extras,
        )

    final = answer["final_answer"]
    acc_failures: list[str] = []
    score = 0.0
    passed = False
    if fmt == "single-choice":
        gold = str(expected.get("gold", ""))
        if not isinstance(final, str):
            acc_failures.append("final_answer must be a single option id string")
            extras["parse_failure"] = 1.0
            format_layer.passed = False
            format_layer.score = 0.0
            format_layer.failures.append("final_answer has wrong type for single-choice")
        else:
            score = 1.0 if final == gold else 0.0
            passed = score == 1.0
            if not passed:
                acc_failures.append(f"expected option {gold}, got {final}")
    elif fmt == "multiple-choice":
        gold_set = {str(g) for g in expected.get("gold", [])}
        if not isinstance(final, list) or not all(isinstance(x, str) for x in final):
            acc_failures.append("final_answer must be a list of option id strings")
            extras["parse_failure"] = 1.0
            format_layer.passed = False
            format_layer.score = 0.0
            format_layer.failures.append("final_answer has wrong type for multiple-choice")
        elif not gold_set:
            acc_failures.append("expected.json has empty gold set")
        else:
            chosen = set(final)
            correct = len(chosen & gold_set)
            wrong = len(chosen - gold_set)
            score = (correct - wrong) / len(gold_set)
            passed = chosen == gold_set
            if not passed:
                acc_failures.append(
                    f"expected options {sorted(gold_set)}, got {sorted(chosen)} "
                    f"(correct {correct}, incorrect {wrong})"
                )
    elif fmt == "numeric":
        try:
            got = Decimal(str(final))
            gold = Decimal(str(expected.get("gold")))
            allowed_error = numeric_tolerance(expected, gold)
            within = abs(got - gold) <= allowed_error
            score = 1.0 if within else 0.0
            passed = within
            if not within:
                acc_failures.append(f"expected {gold} (+/- {allowed_error}), got {got}")
        except (InvalidOperation, ValueError, TypeError):
            acc_failures.append("final_answer must be a number for numeric tasks")
            extras["parse_failure"] = 1.0
            format_layer.passed = False
            format_layer.score = 0.0
            format_layer.failures.append("final_answer has wrong type for numeric")
    else:
        acc_failures.append(f"format {fmt!r} is not deterministically gradable")
    accuracy = LayerResult(score=score, passed=passed, failures=acc_failures)
    return Report(
        layers={"format_validity": format_layer, "answer_accuracy": accuracy},
        extras=extras,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OAB ledger verifier")
    parser.add_argument("--ledger", help="final ledger path (journal-entry tasks)")
    parser.add_argument("--initial", help="initial ledger path (journal-entry tasks)")
    parser.add_argument("--answer", help="answer.json path (answer-file tasks)")
    parser.add_argument(
        "--artifact-root",
        default="/app",
        help="root for /app workflow artifacts (workflow tasks)",
    )
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
        if expected.get("format", "journal-entry") == "journal-entry":
            initial_text = Path(args.initial).read_text(encoding="utf-8")
            final_text = Path(args.ledger).read_text(encoding="utf-8")
            report = verify(initial_text, final_text, expected)
        elif expected.get("format") == _WORKFLOW_FORMAT:
            initial_text = Path(args.initial).read_text(encoding="utf-8")
            final_text = Path(args.ledger).read_text(encoding="utf-8")
            workflow_artifacts = load_workflow_artifacts(expected, Path(args.artifact_root))
            report = grade_workflow(initial_text, final_text, expected, workflow_artifacts)
        else:
            answer_path = Path(args.answer) if args.answer else None
            answer_text = (
                answer_path.read_text(encoding="utf-8")
                if answer_path is not None and answer_path.exists()
                else None
            )
            report = grade_answer(expected, answer_text)
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
