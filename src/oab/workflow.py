"""Authoring contract for professional, multi-artifact workflow tasks.

A workflow scenario is modeled as an issue graph rather than as one long
instruction.  Seeded facts and evidence lead to named accounting
*determinations*; each determination is graded through typed, deterministic
checks against accounting state (ledger balances/deltas and structured
schedule/report values).  This module is the public author-facing schema and
validator.  The hermetic verifier interprets the same JSON shape from its
single-file core.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

WORKFLOW_SCHEMA_VERSION = 1
WORKFLOW_FORMAT = "workflow"
LEDGER_ARTIFACT = "/app/ledger.beancount"
DEFAULT_WORKFLOW_ARTIFACT = "/app/workflow.json"

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_ACCOUNT_RE = re.compile(r"^[A-Z][A-Za-z0-9-]*(?::[A-Z0-9][A-Za-z0-9-]*)+$")

_ARTIFACT_FIELDS = {"path", "kind", "required"}
_DETERMINATION_FIELDS = {"id", "cluster", "title", "evidence", "weight"}
_COMMON_CHECK_FIELDS = {"id", "type", "determination", "gate", "artifact", "tolerance", "currency"}
# Every type-specific field is currently required; this one table is both
# the closed type vocabulary and the required-field schema.
_CHECK_FIELDS: dict[str, set[str]] = {
    "account_delta": {"account", "expected"},
    "period_account_delta": {"account", "expected", "period"},
    "final_balance": {"account", "expected"},
    "subledger_cleared": {"account"},
    "cutoff_no_transactions": {"period"},
    "evidence_disposition": {"path", "key", "expected"},
    "json_value": {"path", "expected"},
    "forbidden_account_delta": {"account"},
    "cross_artifact_balance": {"path", "account"},
}
CHECK_TYPES = tuple(_CHECK_FIELDS)


def workflow_artifact(path: str, kind: str, *, required: bool = True) -> dict[str, Any]:
    return {"path": path, "kind": kind, "required": required}


def default_workflow_artifacts(json_path: str = DEFAULT_WORKFLOW_ARTIFACT) -> list[dict[str, Any]]:
    return [
        workflow_artifact(LEDGER_ARTIFACT, "ledger"),
        workflow_artifact(json_path, "json"),
    ]


def workflow_determination(
    determination_id: str,
    cluster: str,
    title: str,
    *,
    evidence: Iterable[str] = (),
    weight: float = 1.0,
) -> dict[str, Any]:
    return {
        "id": determination_id,
        "cluster": cluster,
        "title": title,
        "evidence": list(evidence),
        "weight": weight,
    }


def workflow_check(
    check_id: str,
    check_type: str,
    determination: str,
    *,
    gate: bool = True,
    **params: Any,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "type": check_type,
        "determination": determination,
        "gate": gate,
        **params,
    }


def workflow_spec(
    determinations: Iterable[dict[str, Any]],
    checks: Iterable[dict[str, Any]],
    *,
    artifacts: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "artifacts": list(artifacts) if artifacts is not None else default_workflow_artifacts(),
        "determinations": list(determinations),
        "checks": list(checks),
    }


def workflow_artifacts(spec: Any) -> list[dict[str, Any]]:
    """Artifact declarations from a workflow spec, ignoring malformed rows."""

    if not isinstance(spec, dict):
        return []
    artifacts = spec.get("artifacts", [])
    if not isinstance(artifacts, list):
        return []
    return [artifact for artifact in artifacts if isinstance(artifact, dict)]


def json_workflow_artifacts(spec: Any) -> list[dict[str, Any]]:
    return [artifact for artifact in workflow_artifacts(spec) if artifact.get("kind") == "json"]


def workflow_artifact_paths(spec: Any) -> list[str]:
    paths = [
        artifact["path"]
        for artifact in workflow_artifacts(spec)
        if isinstance(artifact.get("path"), str)
    ]
    return paths or [LEDGER_ARTIFACT, DEFAULT_WORKFLOW_ARTIFACT]


def _is_id(value: Any) -> bool:
    return isinstance(value, str) and bool(_ID_RE.match(value))


def _is_account(value: Any) -> bool:
    return isinstance(value, str) and bool(_ACCOUNT_RE.match(value))


def _decimal_or_none(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _is_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_period(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and _is_date(value[0])
        and _is_date(value[1])
        and value[0] <= value[1]
    )


def _is_json_path(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and all(value.split("."))


def _unknown_fields(
    item: dict[str, Any], allowed: set[str], where: str, failures: list[str]
) -> None:
    for field in sorted(set(item) - allowed):
        failures.append(f"{where}: unknown field {field!r}")


def _validate_artifacts(spec: dict[str, Any], failures: list[str]) -> dict[str, dict[str, Any]]:
    artifacts = spec.get("artifacts")
    by_path: dict[str, dict[str, Any]] = {}
    if not isinstance(artifacts, list) or not artifacts:
        failures.append("workflow.artifacts must be a non-empty list")
        return by_path
    ledgers = 0
    json_artifacts = 0
    for index, artifact in enumerate(artifacts):
        where = f"workflow.artifacts[{index}]"
        if not isinstance(artifact, dict):
            failures.append(f"{where}: must be an object")
            continue
        _unknown_fields(artifact, _ARTIFACT_FIELDS, where, failures)
        path = artifact.get("path")
        kind = artifact.get("kind")
        required = artifact.get("required", True)
        if not isinstance(path, str) or not path.startswith("/app/") or ".." in path.split("/"):
            failures.append(f"{where}: path must be an absolute /app path")
        elif path in by_path:
            failures.append(f"{where}: duplicate artifact path {path}")
        else:
            by_path[path] = artifact
        if kind not in {"ledger", "json"}:
            failures.append(f"{where}: kind must be 'ledger' or 'json'")
        if not isinstance(required, bool):
            failures.append(f"{where}: required must be a boolean")
        if kind == "ledger":
            ledgers += 1
            if path != LEDGER_ARTIFACT:
                failures.append(f"{where}: ledger artifact must be {LEDGER_ARTIFACT}")
        elif kind == "json":
            json_artifacts += 1
    if ledgers != 1:
        failures.append("workflow.artifacts must declare exactly one ledger artifact")
    if json_artifacts < 1:
        failures.append("workflow.artifacts must declare at least one JSON artifact")
    return by_path


def _validate_determinations(
    spec: dict[str, Any], failures: list[str]
) -> dict[str, dict[str, Any]]:
    determinations = spec.get("determinations")
    by_id: dict[str, dict[str, Any]] = {}
    if not isinstance(determinations, list) or not determinations:
        failures.append("workflow.determinations must be a non-empty list")
        return by_id
    for index, item in enumerate(determinations):
        where = f"workflow.determinations[{index}]"
        if not isinstance(item, dict):
            failures.append(f"{where}: must be an object")
            continue
        _unknown_fields(item, _DETERMINATION_FIELDS, where, failures)
        determination_id = item.get("id")
        if not _is_id(determination_id):
            failures.append(f"{where}: id must be a lowercase slug")
        elif determination_id in by_id:
            failures.append(f"{where}: duplicate determination id {determination_id}")
        else:
            by_id[determination_id] = item
        if not _is_id(item.get("cluster")):
            failures.append(f"{where}: cluster must be a lowercase slug")
        if not isinstance(item.get("title"), str) or not item["title"].strip():
            failures.append(f"{where}: title must be a non-empty string")
        evidence = item.get("evidence", [])
        if not isinstance(evidence, list) or not all(
            isinstance(value, str) and value for value in evidence
        ):
            failures.append(f"{where}: evidence must be a list of non-empty strings")
        weight = item.get("weight", 1)
        if isinstance(weight, bool) or not isinstance(weight, int | float) or float(weight) <= 0:
            failures.append(f"{where}: weight must be a positive number")
    return by_id


def _validate_check_params(
    check: dict[str, Any],
    check_type: str,
    artifacts: dict[str, dict[str, Any]],
    where: str,
    failures: list[str],
) -> None:
    for field in sorted(_CHECK_FIELDS[check_type] - set(check)):
        failures.append(f"{where}: missing required field {field!r}")
    if "account" in check and not _is_account(check.get("account")):
        failures.append(f"{where}: account must be a Beancount account name")
    if "currency" in check:
        currency = check.get("currency")
        if not isinstance(currency, str) or len(currency) != 3 or not currency.isupper():
            failures.append(f"{where}: currency must be a three-letter uppercase code")
    if "period" in check and not _is_period(check.get("period")):
        failures.append(f"{where}: period must be [start, end] ISO dates in order")
    if check_type in {"account_delta", "period_account_delta", "final_balance"}:
        if "expected" in check and _decimal_or_none(check.get("expected")) is None:
            failures.append(f"{where}: expected must be a decimal number")
    if "tolerance" in check:
        tolerance = _decimal_or_none(check.get("tolerance"))
        if tolerance is None or tolerance < 0:
            failures.append(f"{where}: tolerance must be a non-negative decimal")
    if check_type in {"evidence_disposition", "json_value", "cross_artifact_balance"}:
        if "path" in check and not _is_json_path(check.get("path")):
            failures.append(f"{where}: path must be a dotted JSON path")
        artifact_path = check.get("artifact", DEFAULT_WORKFLOW_ARTIFACT)
        artifact = artifacts.get(artifact_path) if isinstance(artifact_path, str) else None
        if artifact is None or artifact.get("kind") != "json":
            failures.append(f"{where}: artifact must name a declared JSON artifact")
    if check_type == "evidence_disposition":
        if "key" in check and (not isinstance(check.get("key"), str) or not check["key"]):
            failures.append(f"{where}: key must be a non-empty string")
        if "expected" in check and not isinstance(check.get("expected"), str):
            failures.append(f"{where}: expected disposition must be a string")


def _validate_checks(
    spec: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
    determinations: dict[str, dict[str, Any]],
    failures: list[str],
) -> None:
    checks = spec.get("checks")
    if not isinstance(checks, list) or not checks:
        failures.append("workflow.checks must be a non-empty list")
        return
    seen_ids: set[str] = set()
    seen_signatures: set[str] = set()
    referenced: set[str] = set()
    gate_count = 0
    for index, check in enumerate(checks):
        where = f"workflow.checks[{index}]"
        if not isinstance(check, dict):
            failures.append(f"{where}: must be an object")
            continue
        check_id = check.get("id")
        if not _is_id(check_id):
            failures.append(f"{where}: id must be a lowercase slug")
        elif check_id in seen_ids:
            failures.append(f"{where}: duplicate check id {check_id}")
        else:
            seen_ids.add(check_id)
        check_type = check.get("type")
        if check_type not in CHECK_TYPES:
            failures.append(f"{where}: unknown check type {check_type!r}")
            continue
        _unknown_fields(
            check,
            _COMMON_CHECK_FIELDS | _CHECK_FIELDS[check_type],
            where,
            failures,
        )
        determination = check.get("determination")
        if determination not in determinations:
            failures.append(f"{where}: unknown determination {determination!r}")
        else:
            referenced.add(determination)
        if not isinstance(check.get("gate", True), bool):
            failures.append(f"{where}: gate must be a boolean")
        elif check.get("gate", True):
            gate_count += 1
        _validate_check_params(check, check_type, artifacts, where, failures)
        signature = json.dumps(
            {key: value for key, value in check.items() if key not in {"id", "gate"}},
            sort_keys=True,
            default=str,
        )
        if signature in seen_signatures:
            failures.append(f"{where}: duplicate check assertion")
        seen_signatures.add(signature)
    if gate_count == 0:
        failures.append("workflow.checks must include at least one gate check")
    for determination_id in sorted(set(determinations) - referenced):
        failures.append(f"workflow.determinations: {determination_id} has no checks")


def validate_workflow_spec(spec: Any) -> list[str]:
    """Return schema/semantic failures for an ``expected['workflow']`` object."""

    failures: list[str] = []
    if not isinstance(spec, dict):
        return ["workflow must be an object"]
    _unknown_fields(
        spec, {"schema_version", "artifacts", "determinations", "checks"}, "workflow", failures
    )
    if spec.get("schema_version") != WORKFLOW_SCHEMA_VERSION:
        failures.append(f"workflow.schema_version must be {WORKFLOW_SCHEMA_VERSION}")
    artifacts = _validate_artifacts(spec, failures)
    determinations = _validate_determinations(spec, failures)
    _validate_checks(spec, artifacts, determinations, failures)
    return failures
