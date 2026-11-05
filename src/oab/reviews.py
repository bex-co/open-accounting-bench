"""Accounting-review registry: a machine-readable mirror of TO_REVIEW.md.

`reviews.toml` holds one row per Stable family:

    [[family]]
    id = "classify-operating-expense"
    status = "reviewed"            # or "pending"
    reviewer = "Tian Pan (maintainer)"
    date = "2026-10-25"
    fingerprint = "sha256:..."     # task content the reviewer signed off

Only a human reviewer sets `status = "reviewed"`; tooling validates rows
and derives `lapsed` (a reviewed family whose generated content has since
changed), but never writes review status itself.
"""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from pathlib import Path

STATUSES = ("pending", "reviewed")
EFFECTIVE_STATUSES = ("pending", "reviewed", "lapsed")
REVIEWED_FIELDS = ("reviewer", "date", "fingerprint")
_EXCLUDED = {"task.toml", "tests/grader.py", "tests/test.sh", "tests/Dockerfile"}
_VERSION_KEYS = {"generator_version"}


def fingerprint(task_dir: Path) -> str:
    """Hash of what a reviewer signs off: instruction, app files, expectations,
    initial ledger, and solution. Versions, digests, the grader copy, and
    container plumbing are excluded, so only content changes lapse a review.
    """
    digest = hashlib.sha256()
    for path in sorted(p for p in task_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(task_dir).as_posix()
        if rel in _EXCLUDED or rel.endswith("Dockerfile"):
            continue
        data = path.read_bytes()
        if rel == "tests/expected.json":
            expected = {k: v for k, v in json.loads(data).items() if k not in _VERSION_KEYS}
            data = json.dumps(expected, sort_keys=True).encode()
        digest.update(rel.encode() + b"\0" + data + b"\0")
    return "sha256:" + digest.hexdigest()


def load_registry(path: Path) -> list[dict]:
    return tomllib.loads(path.read_text(encoding="utf-8")).get("family", [])


def pending_family_ids(to_review: str) -> set[str]:
    """Backticked identifiers in the Pending section of TO_REVIEW.md."""
    section = to_review.split("## Pending", 1)[-1].split("## Reviewed", 1)[0]
    return set(re.findall(r"`([a-z0-9]+(?:-[a-z0-9]+)+)`", section))


def effective_status(row: dict, tasks_root: Path) -> str:
    if row.get("status") != "reviewed":
        return "pending"
    task_dir = tasks_root / row["id"]
    if not task_dir.is_dir() or fingerprint(task_dir) != row.get("fingerprint"):
        return "lapsed"
    return "reviewed"


def validate_registry(rows: list[dict], family_ids: set[str], to_review: str) -> list[str]:
    """Registry drift: CI fails on any returned message."""
    failures: list[str] = []
    seen: dict[str, int] = {}
    for row in rows:
        family = row.get("id")
        seen[family] = seen.get(family, 0) + 1
        if row.get("status") not in STATUSES:
            failures.append(f"{family}: status must be one of {STATUSES}")
        if row.get("status") == "reviewed":
            failures += [
                f"{family}: reviewed rows need `{name}`"
                for name in REVIEWED_FIELDS
                if not row.get(name)
            ]
    failures += [f"{family}: listed {n} times" for family, n in sorted(seen.items()) if n > 1]
    failures += [f"{family}: no such Stable family" for family in sorted(set(seen) - family_ids)]
    failures += [
        f"{family}: missing from reviews.toml" for family in sorted(family_ids - set(seen))
    ]
    still_pending = pending_family_ids(to_review)
    failures += [
        f"{row['id']}: reviewed in reviews.toml but still listed under Pending in TO_REVIEW.md"
        for row in rows
        if row.get("status") == "reviewed" and row.get("id") in still_pending
    ]
    return failures


def review_summary(rows: list[dict], tasks_root: Path) -> dict[str, int]:
    counts = dict.fromkeys(EFFECTIVE_STATUSES, 0)
    for row in rows:
        counts[effective_status(row, tasks_root)] += 1
    return counts
