"""``oab`` command-line interface.

oab list                                   list task families
oab generate --all [--out tasks]           (re)generate Stable tasks
oab generate --family F --seed N --out DIR generate one instance
oab verify --task-dir DIR [--ledger/--answer PATH] grade locally
oab validate [--tasks tasks]               structure + oracle/nop checks
oab report --job DIR [--prices FILE]       aggregate a Harbor job
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

from oab.families import FAMILIES, STABLE_SEEDS, TAXONOMY
from oab.generate import write_dataset_files, write_task
from oab.verify import grade_answer, verify

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
    if fmt == "journal-entry":
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
    return "/app/ledger.beancount" if fmt == "journal-entry" else "/app/answer.json"


def _cmd_list(_args) -> int:
    for task_id, fn in sorted(FAMILIES.items()):
        print(f"{task_id}\tfamily-seed(stable)={STABLE_SEEDS[task_id]}\t{fn.__name__}")
    return 0


def _cmd_generate(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.all:
        dirs = []
        for task_id, seed in sorted(STABLE_SEEDS.items()):
            dirs.append(write_task(FAMILIES[task_id](seed), out, track="stable"))
            print(f"generated {dirs[-1]} (seed {seed})")
        write_dataset_files(out, dirs)
        print(f"wrote {out}/dataset.toml, manifest.json, metric.py")
        return 0
    if not args.family or args.seed is None:
        print("error: pass --all, or --family F --seed N", file=sys.stderr)
        return 2
    instance = FAMILIES[args.family](args.seed)
    track = "stable" if STABLE_SEEDS.get(args.family) == args.seed else "dynamic"
    path = write_task(instance, out, track=track)
    print(f"generated {path} (seed {args.seed}, track {track})")
    return 0


def _expected_shape_failures(name: str, fmt: str, expected: dict) -> list[str]:
    """Format-specific expectations must be present and well-typed."""
    from decimal import Decimal, InvalidOperation

    failures: list[str] = []
    if fmt == "journal-entry":
        if not expected.get("expected_deltas"):
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
    elif fmt == "open-text":
        failures.append(f"{name}: open-text has no deterministic grader yet")
    return failures


def _grade(task_dir: Path, artifact: Path | None) -> dict:
    expected = json.loads((task_dir / "tests" / "expected.json").read_text())
    if expected.get("format", "journal-entry") == "journal-entry":
        initial = (task_dir / "tests" / "initial.beancount").read_text()
        final = Path(artifact).read_text() if artifact is not None else initial
        return verify(initial, final, expected).to_report_json()
    answer_text = Path(artifact).read_text() if artifact is not None else None
    return grade_answer(expected, answer_text).to_report_json()


def _cmd_verify(args) -> int:
    task_dir = Path(args.task_dir)
    fmt = task_format(task_dir)
    if fmt == "journal-entry":
        artifact = Path(args.ledger) if args.ledger else task_dir / "solution" / "ledger.beancount"
    else:
        artifact = Path(args.answer) if args.answer else task_dir / "solution" / "answer.json"
    report = _grade(task_dir, artifact)
    print(json.dumps(report, indent=2))
    return 0 if report["reward"]["reward"] == 1 else 1


def validate_tasks(tasks_root: Path) -> list[str]:
    """Return a list of validation failures (empty = all tasks healthy)."""
    failures: list[str] = []
    core = (Path(__file__).with_name("_verifier_core.py")).read_text()
    task_dirs = sorted(p for p in tasks_root.iterdir() if p.is_dir() and (p / "task.toml").exists())
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
        if config.get("artifacts") != [artifact_for_format(fmt)]:
            failures.append(f"{name}: artifacts must declare {artifact_for_format(fmt)}")
        if config.get("verifier", {}).get("environment_mode") != "separate":
            failures.append(f"{name}: verifier must use a separate environment")
        metadata = config.get("metadata", {})
        for axis, allowed in TAXONOMY.items():
            if metadata.get(axis) not in allowed:
                failures.append(f"{name}: metadata.{axis}={metadata.get(axis)!r} not in {allowed}")
        expected = json.loads((task_dir / "tests" / "expected.json").read_text())
        if metadata.get("format") != expected.get("format"):
            failures.append(f"{name}: task.toml format != expected.json format")
        instruction = (task_dir / "instruction.md").read_text()
        if artifact_for_format(fmt) not in instruction:
            failures.append(f"{name}: instruction must name {artifact_for_format(fmt)}")
        if metadata.get("task_id") != name:
            failures.append(f"{name}: metadata.task_id must equal directory name")
        if metadata.get("seed") != expected.get("seed"):
            failures.append(f"{name}: metadata.seed != expected.json seed")
        if not (task_dir / "environment" / "app" / "policy.md").is_file():
            failures.append(f"{name}: environment/app/policy.md is required")
        failures += _expected_shape_failures(name, fmt, expected)
        if (task_dir / "tests" / "grader.py").read_text() != core:
            failures.append(f"{name}: tests/grader.py drifted from oab._verifier_core")
        if fmt == "journal-entry":
            initial = (task_dir / "environment" / "app" / "ledger.beancount").read_text()
            if initial != (task_dir / "tests" / "initial.beancount").read_text():
                failures.append(f"{name}: tests/initial.beancount != environment ledger")
            if initial == (task_dir / "solution" / "ledger.beancount").read_text():
                failures.append(f"{name}: solution ledger must differ from initial")
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
    gen.add_argument("--family", choices=sorted(FAMILIES))
    gen.add_argument("--seed", type=int)
    gen.add_argument("--out", default="tasks")
    gen.set_defaults(fn=_cmd_generate)
    ver = sub.add_parser("verify")
    ver.add_argument("--task-dir", required=True)
    ver.add_argument("--ledger", help="defaults to the task's solution ledger")
    ver.add_argument("--answer", help="defaults to the task's solution answer")
    ver.set_defaults(fn=_cmd_verify)
    val = sub.add_parser("validate")
    val.add_argument("--tasks", default="tasks")
    val.set_defaults(fn=_cmd_validate)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
