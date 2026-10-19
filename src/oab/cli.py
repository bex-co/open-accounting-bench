"""``oab`` command-line interface.

oab list                                   list task families
oab generate --all [--out tasks]           (re)generate Stable tasks
oab generate --family F --seed N --out DIR generate one instance
oab verify --task-dir DIR [--ledger PATH]  grade a ledger locally
oab validate [--tasks tasks]               structure + oracle/nop checks
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

from oab.families import FAMILIES, STABLE_SEEDS
from oab.generate import write_dataset_files, write_task
from oab.verify import verify

REQUIRED_FILES = [
    "task.toml",
    "instruction.md",
    "environment/Dockerfile",
    "environment/app/ledger.beancount",
    "tests/test.sh",
    "tests/grader.py",
    "tests/expected.json",
    "tests/initial.beancount",
    "tests/Dockerfile",
    "solution/solve.sh",
    "solution/ledger.beancount",
]


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


def _grade(task_dir: Path, ledger_path: Path) -> dict:
    expected = json.loads((task_dir / "tests" / "expected.json").read_text())
    initial = (task_dir / "tests" / "initial.beancount").read_text()
    final = Path(ledger_path).read_text()
    return verify(initial, final, expected).to_report_json()


def _cmd_verify(args) -> int:
    task_dir = Path(args.task_dir)
    ledger = Path(args.ledger) if args.ledger else task_dir / "solution" / "ledger.beancount"
    report = _grade(task_dir, ledger)
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
        for rel in REQUIRED_FILES:
            if not (task_dir / rel).is_file():
                failures.append(f"{name}: missing {rel}")
        try:
            config = tomllib.loads((task_dir / "task.toml").read_text())
        except Exception as exc:
            failures.append(f"{name}: task.toml does not parse: {exc}")
            continue
        if config.get("schema_version") != "1.3":
            failures.append(f"{name}: schema_version must be 1.3")
        if config.get("artifacts") != ["/app/ledger.beancount"]:
            failures.append(f"{name}: artifacts must declare /app/ledger.beancount")
        if config.get("verifier", {}).get("environment_mode") != "separate":
            failures.append(f"{name}: verifier must use a separate environment")
        if (task_dir / "tests" / "grader.py").read_text() != core:
            failures.append(f"{name}: tests/grader.py drifted from oab._verifier_core")
        initial = (task_dir / "environment" / "app" / "ledger.beancount").read_text()
        if initial != (task_dir / "tests" / "initial.beancount").read_text():
            failures.append(f"{name}: tests/initial.beancount != environment ledger")
        oracle = _grade(task_dir, task_dir / "solution" / "ledger.beancount")
        if oracle["reward"]["reward"] != 1:
            failures.append(f"{name}: oracle solution does not pass: {oracle}")
        nop = _grade(task_dir, task_dir / "tests" / "initial.beancount")
        if nop["reward"]["reward"] != 0:
            failures.append(f"{name}: untouched ledger must not pass")
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
    ver.set_defaults(fn=_cmd_verify)
    val = sub.add_parser("validate")
    val.add_argument("--tasks", default="tasks")
    val.set_defaults(fn=_cmd_validate)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
