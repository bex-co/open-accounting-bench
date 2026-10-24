"""Crosswalks: typed mappings from OAB generators to external frameworks.

One TOML file per external framework *version* under ``crosswalks/``
(e.g. the AICPA CPA Exam Blueprint 2027, the ACCA 2026-27 syllabi).
Records follow NIST IR 8278A Rev.1 set-theory mapping: the focal element
is an OAB generator (a ``FAMILIES`` key), the reference element an
external item; each record carries a relationship, a rationale, and a
0-10 strength. ``[[out_of_scope]]`` records exclude items OAB judges not
agent-gradable from the gradable denominator. Files hold IDs and
OAB-written summaries only — never
the external framework's text (see PROVENANCE.md and docs/metrics.md).
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from oab.families import FAMILIES

# NIST IR 8278A Rev.1 §3.2.6 / §3.2.5. "not related to" is never recorded.
RELATIONSHIPS = ("equal", "superset-of", "subset-of", "intersects-with")
RATIONALES = ("syntactic", "semantic", "functional")
STATUSES = ("proposed", "reviewed")
# A reference item counts as covered only through a full-containment
# link of at least this strength; weaker links are reported separately.
COVERING = ("equal", "superset-of")
COVER_MIN_STRENGTH = 7
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def text_digest(text: str) -> str:
    """Drift fingerprint of an external item's wording (case/space-folded).

    Lets a new framework version be diffed against a mapping without
    publishing the copyrighted text itself.
    """
    folded = " ".join(text.lower().split())
    return "sha256:" + hashlib.sha256(folded.encode()).hexdigest()


@dataclass
class Crosswalk:
    path: Path
    framework: dict
    mappings: list[dict]
    out_of_scope: list[dict] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.framework.get('id')}@{self.framework.get('version')}"


def load_crosswalks(directory: Path) -> list[Crosswalk]:
    crosswalks = []
    for path in sorted(directory.glob("*.toml")):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        crosswalks.append(
            Crosswalk(
                path,
                data.get("framework", {}),
                data.get("mapping", []),
                data.get("out_of_scope", []),
            )
        )
    return crosswalks


def section_of(target_id: str) -> str:
    return target_id.split(".", 1)[0]


def target_key(mapping: dict) -> str:
    item = mapping.get("target_item")
    return f"{mapping['target_id']}#{item}" if item is not None else mapping["target_id"]


def validate_crosswalk(cw: Crosswalk) -> list[str]:
    name = cw.path.name
    failures: list[str] = []
    fw = cw.framework
    for key in ("id", "version", "title", "publisher", "source"):
        if not isinstance(fw.get(key), str) or not fw[key]:
            failures.append(f"{name}: framework.{key} is required")
    denominators = fw.get("denominators")
    if not isinstance(denominators, dict) or not denominators:
        failures.append(f"{name}: framework.denominators must map sections to item counts")
        denominators = {}
    for section, count in denominators.items():
        if not isinstance(count, int) or count <= 0:
            failures.append(f"{name}: denominator {section}={count!r} must be a positive int")
    if not cw.mappings:
        failures.append(f"{name}: no [[mapping]] records")
    seen: set[tuple[str, str]] = set()
    for i, m in enumerate(cw.mappings):
        where = f"{name}: mapping[{i}]"
        if m.get("generator") not in FAMILIES:
            failures.append(f"{where}: generator {m.get('generator')!r} not in FAMILIES")
        target_id = m.get("target_id")
        if not isinstance(target_id, str) or section_of(target_id) not in denominators:
            failures.append(f"{where}: target_id {target_id!r} must start with a denominator key")
            continue
        item = m.get("target_item")
        if item is not None and (not isinstance(item, int) or item < 1):
            failures.append(f"{where}: target_item must be a 1-based int")
        relationship = m.get("relationship")
        if relationship not in RELATIONSHIPS:
            failures.append(f"{where}: relationship {relationship!r} not in {RELATIONSHIPS}")
        if m.get("rationale") not in RATIONALES:
            failures.append(f"{where}: rationale {m.get('rationale')!r} not in {RATIONALES}")
        strength = m.get("strength")
        if not isinstance(strength, int) or not 0 < strength <= 10:
            failures.append(f"{where}: strength must be an int in 1..10")
        elif (relationship == "equal") != (strength == 10):
            failures.append(f"{where}: strength 10 is reserved for (and required by) equal")
        digest = m.get("target_text_sha256")
        if digest is not None and not _SHA256.match(str(digest)):
            failures.append(f"{where}: target_text_sha256 must be sha256:<64 hex>")
        status = m.get("status")
        if status not in STATUSES:
            failures.append(f"{where}: status {status!r} not in {STATUSES}")
        if status == "reviewed" and not m.get("reviewer"):
            failures.append(f"{where}: reviewed mappings need a reviewer")
        if not m.get("comment"):
            failures.append(f"{where}: comment (OAB-written summary) is required")
        key = (str(m.get("generator")), target_key(m))
        if key in seen:
            failures.append(f"{where}: duplicate mapping {key}")
        seen.add(key)
    triaged = fw.get("triaged", [])
    if not isinstance(triaged, list) or not set(triaged) <= set(denominators):
        failures.append(f"{name}: framework.triaged must list denominator keys")
        triaged = []
    covered = {
        target_key(m)
        for m in cw.mappings
        if m.get("relationship") in COVERING and m.get("target_id")
    }
    excluded: set[str] = set()
    for i, x in enumerate(cw.out_of_scope):
        where = f"{name}: out_of_scope[{i}]"
        target_id = x.get("target_id")
        if not isinstance(target_id, str) or section_of(target_id) not in denominators:
            failures.append(f"{where}: target_id {target_id!r} must start with a denominator key")
            continue
        if section_of(target_id) not in triaged:
            failures.append(f"{where}: section {section_of(target_id)} is not in framework.triaged")
        item = x.get("target_item")
        if item is not None and (not isinstance(item, int) or item < 1):
            failures.append(f"{where}: target_item must be a 1-based int")
        if not x.get("reason"):
            failures.append(f"{where}: reason (OAB-written) is required")
        if x.get("status") not in STATUSES:
            failures.append(f"{where}: status {x.get('status')!r} not in {STATUSES}")
        if x.get("status") == "reviewed" and not x.get("reviewer"):
            failures.append(f"{where}: reviewed exclusions need a reviewer")
        key = target_key(x)
        if key in excluded:
            failures.append(f"{where}: duplicate exclusion {key}")
        if key in covered:
            failures.append(f"{where}: {key} is covered by a mapping but marked out of scope")
        excluded.add(key)
    return failures


def coverage(cw: Crosswalk) -> dict[str, dict]:
    """Per-section counts of distinct reference items, by strongest link.

    covered: an equal/superset-of link with strength >= COVER_MIN_STRENGTH;
    partial: otherwise a subset-of link; touched: only intersects-with or
    weak links. `gradable` is the total minus `[[out_of_scope]]` items,
    or None for sections not listed in `framework.triaged`;
    `unreviewed` counts items whose best link, or whose exclusion, is
    still proposed.
    """
    rank = {"covered": 3, "partial": 2, "touched": 1}
    best: dict[str, tuple[str, bool]] = {}
    for m in cw.mappings:
        if m["relationship"] in COVERING and m["strength"] >= COVER_MIN_STRENGTH:
            tier = "covered"
        elif m["relationship"] == "subset-of":
            tier = "partial"
        else:
            tier = "touched"
        reviewed = m["status"] == "reviewed"
        key = target_key(m)
        current = best.get(key)
        if current is None or (rank[tier], reviewed) > (rank[current[0]], current[1]):
            best[key] = (tier, reviewed)
    result = {}
    for section, total in cw.framework["denominators"].items():
        counts = {
            "total": total,
            "gradable": total if section in cw.framework.get("triaged", []) else None,
            "covered": 0,
            "partial": 0,
            "touched": 0,
            "unreviewed": 0,
        }
        for key, (tier, reviewed) in best.items():
            if section_of(key) == section:
                counts[tier] += 1
                counts["unreviewed"] += not reviewed
        for x in cw.out_of_scope:
            if section_of(x["target_id"]) == section and counts["gradable"] is not None:
                counts["gradable"] -= 1
                counts["unreviewed"] += x["status"] != "reviewed"
        result[section] = counts
    return result


def format_coverage(crosswalks: list[Crosswalk]) -> str:
    lines = [
        "| Framework | Section | Covered | Partial | Touched | Gradable | Items | Unreviewed |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for cw in crosswalks:
        for section, c in coverage(cw).items():
            if c["covered"] + c["partial"] + c["touched"] == 0 and c["gradable"] is None:
                continue
            gradable = "—" if c["gradable"] is None else c["gradable"]
            lines.append(
                f"| {cw.label} | {section} | {c['covered']} | {c['partial']} | "
                f"{c['touched']} | {gradable} | {c['total']} | {c['unreviewed']} |"
            )
    return "\n".join(lines)
