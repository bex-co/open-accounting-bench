"""``oab`` command-line interface.

oab list                                   list task families
oab generate --all [--out tasks]           (re)generate Stable tasks
oab generate --family F --seed N --out DIR generate one instance
oab verify --task-dir DIR [--ledger/--answer PATH] grade locally
oab validate [--tasks tasks]               structure + oracle/nop checks
oab report --job DIR [--prices FILE]       aggregate a Harbor job
oab crosswalk [--dir crosswalks]           validate crosswalks + coverage
oab audit [--tasks tasks] [--out DIR]      verifier false-accept/reject audit
oab reviews [--registry reviews.toml]      validate the accounting-review registry
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

from oab.audit import task_dirs as audit_task_dirs
from oab.families import FAMILIES, STABLE_SEEDS, STANDARD_REF, TAXONOMY
from oab.generate import write_dataset_files, write_task
from oab.verify import (
    grade_answer,
    grade_workflow,
    is_no_action,
    load_workflow_artifacts,
    verify,
)
from oab.workflow import (
    LEDGER_ARTIFACT,
    WORKFLOW_FORMAT,
    json_workflow_artifacts,
    validate_workflow_spec,
    workflow_artifact_paths,
)
from oab.workflow_families import ALL_FAMILIES

_COMMON_FILES = [
    "task.toml",
    "instruction.md",
    "environment/Dockerfile",
    "tests/test.sh",
    "tests/grader.py",
    "tests/expected.json",
    "tests/Dockerfile",
    "solution/solve.sh",
]


def required_files(fmt: str) -> list[str]:
    if fmt in {"journal-entry", WORKFLOW_FORMAT}:
        return _COMMON_FILES + [
            "environment/app/ledger.beancount",
            "tests/initial.beancount",
            "solution/ledger.beancount",
        ]
    return _COMMON_FILES + ["solution/answer.json"]


def task_format(task_dir: Path) -> str:
    expected_path = task_dir / "tests" / "expected.json"
    if expected_path.exists():
        return json.loads(expected_path.read_text()).get("format", "journal-entry")
    return "journal-entry"


def artifact_for_format(fmt: str) -> str:
    return LEDGER_ARTIFACT if fmt in {"journal-entry", WORKFLOW_FORMAT} else "/app/answer.json"


def artifact_paths_for_expected(fmt: str, expected: dict) -> list[str]:
    if fmt != WORKFLOW_FORMAT:
        return [artifact_for_format(fmt)]
    return workflow_artifact_paths(expected.get("workflow"))


def _cmd_list(_args) -> int:
    for task_id, fn in sorted(ALL_FAMILIES.items()):
        stable_seed = STABLE_SEEDS.get(task_id)
        seed_label = stable_seed if stable_seed is not None else "dynamic-only"
        print(f"{task_id}\tfamily-seed(stable)={seed_label}\t{fn.__name__}")
    return 0


def _cmd_generate(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.all:
        dirs = []
        for task_id, seed in sorted(STABLE_SEEDS.items()):
            dirs.append(write_task(FAMILIES[task_id](seed), out, track="stable"))
            print(f"generated {dirs[-1]} (seed {seed})")
        from oab.reviews import effective_statuses, load_registry

        registry = Path(args.registry)
        reviews = effective_statuses(load_registry(registry), out) if registry.is_file() else {}
        write_dataset_files(out, dirs, reviews)
        print(f"wrote {out}/dataset.toml, manifest.json, metric.py")
        return 0
    if not args.family or args.seed is None:
        print("error: pass --all, or --family F --seed N", file=sys.stderr)
        return 2
    instance = ALL_FAMILIES[args.family](args.seed)
    track = "stable" if STABLE_SEEDS.get(args.family) == args.seed else "dynamic"
    path = write_task(instance, out, track=track)
    print(f"generated {path} (seed {args.seed}, track {track})")
    return 0


def _expected_shape_failures(name: str, fmt: str, expected: dict) -> list[str]:
    """Format-specific expectations must be present and well-typed."""
    from decimal import Decimal, InvalidOperation

    failures: list[str] = []
    # A no-action control (zero new transactions) legitimately changes nothing.
    needs_deltas = not is_no_action(expected)
    if fmt == "journal-entry":
        if needs_deltas and not expected.get("expected_deltas"):
            failures.append(f"{name}: journal-entry expected_deltas must be non-empty")
    elif fmt == "single-choice":
        if not isinstance(expected.get("gold"), str) or not expected["gold"]:
            failures.append(f"{name}: single-choice gold must be an option id string")
    elif fmt == "multiple-choice":
        gold = expected.get("gold")
        if not isinstance(gold, list) or not gold:
            failures.append(f"{name}: multiple-choice gold must be a non-empty list")
        elif "options" in expected and not set(gold) <= set(expected["options"]):
            failures.append(f"{name}: multiple-choice gold must be subset of options")
    elif fmt == "numeric":
        try:
            Decimal(str(expected.get("gold")))
        except (InvalidOperation, ValueError, TypeError):
            failures.append(f"{name}: numeric gold must be a number")
    elif fmt == WORKFLOW_FORMAT:
        if needs_deltas and not expected.get("expected_deltas"):
            failures.append(f"{name}: workflow expected_deltas must be non-empty")
        failures.extend(
            f"{name}: {failure}" for failure in validate_workflow_spec(expected.get("workflow"))
        )
    elif fmt == "open-text":
        failures.append(f"{name}: open-text has no deterministic grader yet")
    return failures


def _grade(
    task_dir: Path,
    artifact: Path | None,
    artifact_root: Path | None = None,
) -> dict:
    expected = json.loads((task_dir / "tests" / "expected.json").read_text())
    fmt = expected.get("format", "journal-entry")
    if fmt == "journal-entry":
        initial = (task_dir / "tests" / "initial.beancount").read_text()
        final = Path(artifact).read_text() if artifact is not None else initial
        return verify(initial, final, expected).to_report_json()
    if fmt == WORKFLOW_FORMAT:
        initial = (task_dir / "tests" / "initial.beancount").read_text()
        final = Path(artifact).read_text() if artifact is not None else initial
        return grade_workflow(
            initial,
            final,
            expected,
            load_workflow_artifacts(expected, artifact_root),
        ).to_report_json()
    answer_text = Path(artifact).read_text() if artifact is not None else None
    return grade_answer(expected, answer_text).to_report_json()


def _cmd_verify(args) -> int:
    task_dir = Path(args.task_dir)
    fmt = task_format(task_dir)
    artifact_root = None
    if fmt == WORKFLOW_FORMAT:
        artifact = Path(args.ledger) if args.ledger else task_dir / "solution" / "ledger.beancount"
        artifact_root = Path(args.artifact_root) if args.artifact_root else artifact.parent
    elif fmt == "journal-entry":
        artifact = Path(args.ledger) if args.ledger else task_dir / "solution" / "ledger.beancount"
    else:
        artifact = Path(args.answer) if args.answer else task_dir / "solution" / "answer.json"
    report = _grade(task_dir, artifact, artifact_root=artifact_root)
    print(json.dumps(report, indent=2))
    return 0 if report["reward"]["reward"] == 1 else 1


def _workflow_evidence_failures(name: str, task_dir: Path, expected: dict) -> list[str]:
    failures: list[str] = []
    workflow = expected.get("workflow", {})
    if not isinstance(workflow, dict):
        return failures
    for determination in workflow.get("determinations", []):
        if not isinstance(determination, dict):
            continue
        for reference in determination.get("evidence", []):
            if isinstance(reference, str) and "/" in reference:
                if not (task_dir / "environment" / "app" / reference).is_file():
                    failures.append(f"{name}: workflow evidence file missing: {reference}")
    return failures


def validate_tasks(tasks_root: Path) -> list[str]:
    """Return a list of validation failures (empty = all tasks healthy)."""
    failures: list[str] = []
    core = (Path(__file__).with_name("_verifier_core.py")).read_text()
    task_dirs = audit_task_dirs(tasks_root)
    if not task_dirs:
        return [f"no tasks found under {tasks_root}"]
    for task_dir in task_dirs:
        name = task_dir.name
        fmt = task_format(task_dir)
        for rel in required_files(fmt):
            if not (task_dir / rel).is_file():
                failures.append(f"{name}: missing {rel}")
        try:
            config = tomllib.loads((task_dir / "task.toml").read_text())
        except Exception as exc:
            failures.append(f"{name}: task.toml does not parse: {exc}")
            continue
        if config.get("schema_version") != "1.3":
            failures.append(f"{name}: schema_version must be 1.3")
        expected = json.loads((task_dir / "tests" / "expected.json").read_text())
        artifact_paths = artifact_paths_for_expected(fmt, expected)
        if config.get("artifacts") != artifact_paths:
            failures.append(f"{name}: artifacts must declare {artifact_paths}")
        if config.get("verifier", {}).get("environment_mode") != "separate":
            failures.append(f"{name}: verifier must use a separate environment")
        metadata = config.get("metadata", {})
        for axis, allowed in TAXONOMY.items():
            if metadata.get(axis) not in allowed:
                failures.append(f"{name}: metadata.{axis}={metadata.get(axis)!r} not in {allowed}")
        standards = metadata.get("standards")
        if not isinstance(standards, list) or not all(
            isinstance(ref, str) and STANDARD_REF.match(ref) for ref in standards
        ):
            failures.append(f"{name}: metadata.standards={standards!r} must be asc/ias/ifrs refs")
        if metadata.get("format") != expected.get("format"):
            failures.append(f"{name}: task.toml format != expected.json format")
        instruction = (task_dir / "instruction.md").read_text()
        for artifact_path in artifact_paths:
            if artifact_path not in instruction:
                failures.append(f"{name}: instruction must name {artifact_path}")
        if fmt == WORKFLOW_FORMAT:
            for artifact in json_workflow_artifacts(expected.get("workflow")):
                path = artifact.get("path")
                if isinstance(path, str):
                    rel = path.removeprefix("/app/")
                    if not (task_dir / "solution" / rel).is_file():
                        failures.append(f"{name}: missing solution/{rel}")
            failures += _workflow_evidence_failures(name, task_dir, expected)
        if metadata.get("task_id") != name:
            failures.append(f"{name}: metadata.task_id must equal directory name")
        if metadata.get("seed") != expected.get("seed"):
            failures.append(f"{name}: metadata.seed != expected.json seed")
        if not (task_dir / "environment" / "app" / "policy.md").is_file():
            failures.append(f"{name}: environment/app/policy.md is required")
        failures += _expected_shape_failures(name, fmt, expected)
        if (task_dir / "tests" / "grader.py").read_text() != core:
            failures.append(f"{name}: tests/grader.py drifted from oab._verifier_core")
        if fmt in {"journal-entry", WORKFLOW_FORMAT}:
            initial = (task_dir / "environment" / "app" / "ledger.beancount").read_text()
            if initial != (task_dir / "tests" / "initial.beancount").read_text():
                failures.append(f"{name}: tests/initial.beancount != environment ledger")
            solution = (task_dir / "solution" / "ledger.beancount").read_text()
            if not is_no_action(expected) and initial == solution:
                failures.append(f"{name}: solution ledger must differ from initial")
            if fmt == WORKFLOW_FORMAT:
                oracle = _grade(
                    task_dir,
                    task_dir / "solution" / "ledger.beancount",
                    artifact_root=task_dir / "solution",
                )
                nop = _grade(
                    task_dir,
                    task_dir / "tests" / "initial.beancount",
                    artifact_root=None,
                )
                nop_label = "untouched ledger with missing workflow artifacts must not pass"
            else:
                oracle = _grade(task_dir, task_dir / "solution" / "ledger.beancount")
                nop = _grade(task_dir, task_dir / "tests" / "initial.beancount")
                nop_label = "untouched ledger must not pass"
        else:
            oracle = _grade(task_dir, task_dir / "solution" / "answer.json")
            nop = _grade(task_dir, None)
            nop_label = "missing answer must not pass"
        if oracle["reward"]["reward"] != 1:
            failures.append(f"{name}: oracle solution does not pass: {oracle}")
        if nop["reward"]["reward"] != 0:
            failures.append(f"{name}: {nop_label}")
    return failures


def _cmd_report(args) -> int:
    from oab.report import write_report

    prices = json.loads(Path(args.prices).read_text()) if args.prices else None
    try:
        runs, board = write_report(
            Path(args.job),
            Path(args.manifest),
            prices=prices,
            out_dir=Path(args.out) if args.out else None,
            k=args.k,
            reviewed_only=args.reviewed_only,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {runs} and {board}")
    return 0


def _cmd_crosswalk(args) -> int:
    from oab.crosswalk import format_coverage, load_crosswalks, validate_crosswalk

    crosswalks = load_crosswalks(Path(args.dir))
    failures = [f for cw in crosswalks for f in validate_crosswalk(cw)]
    for failure in failures:
        print(f"FAIL {failure}")
    if failures:
        print(f"{len(failures)} failure(s)")
        return 1
    print(format_coverage(crosswalks))
    return 0


def _cmd_audit(args) -> int:
    from oab.audit import render_markdown, run_audit, summarize

    outcomes, skipped = run_audit(Path(args.tasks), sample=args.sample)
    summary = summarize(outcomes, skipped)
    markdown = render_markdown(summary)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "audit.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        (out / "audit.md").write_text(markdown, encoding="utf-8")
    print(markdown, end="")
    return 1 if summary["false_accepts"] or summary["false_rejects"] else 0


def _cmd_reviews(args) -> int:
    from collections import Counter

    from oab.reviews import effective_statuses, fingerprint, load_registry, validate_registry

    tasks_root = Path(args.tasks)
    if args.fingerprint:
        print(fingerprint(tasks_root / args.fingerprint))
        return 0
    rows = load_registry(Path(args.registry))
    to_review = Path(args.to_review).read_text(encoding="utf-8")
    failures = validate_registry(rows, set(STABLE_SEEDS), to_review)
    for failure in failures:
        print(f"FAIL {failure}")
    counts = Counter(effective_statuses(rows, tasks_root).values())
    print(
        f"{len(rows)} families: {counts['reviewed']} reviewed, "
        f"{counts['lapsed']} lapsed (content changed since review), {counts['pending']} pending"
    )
    return 1 if failures else 0


def _cmd_validate(args) -> int:
    failures = validate_tasks(Path(args.tasks))
    for failure in failures:
        print(f"FAIL {failure}")
    print("OK: all tasks valid" if not failures else f"{len(failures)} failure(s)")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="oab", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list").set_defaults(fn=_cmd_list)
    gen = sub.add_parser("generate")
    gen.add_argument("--all", action="store_true")
    gen.add_argument("--family", choices=sorted(ALL_FAMILIES))
    gen.add_argument("--seed", type=int)
    gen.add_argument("--out", default="tasks")
    gen.add_argument(
        "--registry", default="reviews.toml", help="review registry for manifest `review`"
    )
    gen.set_defaults(fn=_cmd_generate)
    ver = sub.add_parser("verify")
    ver.add_argument("--task-dir", required=True)
    ver.add_argument("--ledger", help="defaults to the task's solution ledger")
    ver.add_argument("--answer", help="defaults to the task's solution answer")
    ver.add_argument(
        "--artifact-root",
        help="directory containing /app-relative workflow artifacts (default: ledger directory)",
    )
    ver.set_defaults(fn=_cmd_verify)
    rep = sub.add_parser("report")
    rep.add_argument("--job", required=True, help="Harbor job directory")
    rep.add_argument("--manifest", default="tasks/manifest.json")
    rep.add_argument("--prices", help="JSON price table (see prices.example.json)")
    rep.add_argument("--out", help="output directory (default: the job directory)")
    rep.add_argument(
        "--reviewed-only",
        action="store_true",
        help="score only tasks whose accounting review is on record (reviews.toml)",
    )
    rep.add_argument(
        "--k",
        type=int,
        help="attempts per task for pass@k / pass^k (default: fewest graded attempts on any task)",
    )
    rep.set_defaults(fn=_cmd_report)
    cw = sub.add_parser("crosswalk")
    cw.add_argument("--dir", default="crosswalks")
    cw.set_defaults(fn=_cmd_crosswalk)
    aud = sub.add_parser("audit", help="mutation audit of the verifier over generated tasks")
    aud.add_argument("--tasks", default="tasks")
    aud.add_argument("--out", help="write audit.json and audit.md to this directory")
    aud.add_argument("--sample", type=int, help="audit every N-th task (deterministic subset)")
    aud.set_defaults(fn=_cmd_audit)
    revs = sub.add_parser("reviews", help="validate reviews.toml against Stable families")
    revs.add_argument("--registry", default="reviews.toml")
    revs.add_argument("--to-review", default="TO_REVIEW.md")
    revs.add_argument("--tasks", default="tasks")
    revs.add_argument("--fingerprint", metavar="TASK_ID", help="print a task's review fingerprint")
    revs.set_defaults(fn=_cmd_reviews)
    val = sub.add_parser("validate")
    val.add_argument("--tasks", default="tasks")
    val.set_defaults(fn=_cmd_validate)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
