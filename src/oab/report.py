"""Aggregate a Harbor job into runs + a stratified leaderboard.

Inputs: a Harbor job directory (per-trial result.json, verifier
reward.json, collected artifacts) joined with the dataset manifest
for taxonomy. Outputs (into the job dir by default):

- runs.jsonl      one row per trial (the auditable run registry)
- leaderboard.md  overall + per category/framework/level/format/skill,
                  interpretation bands, cost, confidence calibration

Choice formats aggregate by majority vote over attempts (use -k 3);
other formats by mean reward. Missing rewards count as 0.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from math import comb
from pathlib import Path

AXES = ("category", "framework", "level", "format", "skill")
GROUP_AXES = (*AXES, "family")
DIAGNOSTIC_CLASSES = ("correct", "wrong-account", "wrong-amount", "missing")
DIAGNOSTIC_KEYS = (*DIAGNOSTIC_CLASSES, "extra")
CHOICE_FORMATS = ("single-choice", "multiple-choice")
BANDS = [
    (90, "Excellent (near-expert)"),
    (75, "Strong (professional-level)"),
    (60, "Moderate (requires verification)"),
    (50, "Weak (below professional threshold)"),
    (0, "Poor (not suitable for professional use)"),
]
CONFIDENCE_BINS = [(0, 50), (50, 70), (70, 85), (85, 95), (95, 101)]


def pass_at_k(n: int, c: int, k: int) -> float | None:
    """Unbiased pass@k from n graded attempts with c successes.

    Probability that at least one of k attempts drawn without
    replacement succeeds: 1 - C(n-c, k) / C(n, k). None when n < k.
    """
    if n < k or k < 1:
        return None
    return (comb(n, k) - comb(n - c, k)) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float | None:
    """pass^k: probability that all k attempts succeed, C(c, k) / C(n, k).

    The deployment bar for accounting agents: right every time, not
    right on average. None when n < k.
    """
    if n < k or k < 1:
        return None
    return comb(c, k) / comb(n, k)


def band_for(percent: float) -> str:
    for low, label in BANDS:
        if percent >= low:
            return label
    return BANDS[-1][1]


def _read_json(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _duration_seconds(start: object, finish: object) -> float | None:
    if not isinstance(start, str) or not isinstance(finish, str):
        return None
    try:
        first = datetime.fromisoformat(start.replace("Z", "+00:00"))
        last = datetime.fromisoformat(finish.replace("Z", "+00:00"))
    except ValueError:
        return None
    seconds = (last - first).total_seconds()
    return seconds if seconds >= 0 else None


def _workflow_details(report: dict) -> dict:
    details = report.get("details") or {}
    workflow = details.get("workflow") if isinstance(details, dict) else None
    return workflow if isinstance(workflow, dict) else {}


def _workflow_clusters(details: dict) -> dict[str, float]:
    clusters = details.get("clusters") or {}
    if not isinstance(clusters, dict):
        return {}
    return {
        str(name): float(score)
        for name, score in sorted(clusters.items())
        if isinstance(score, int | float)
    }


def _workflow_checks(details: dict) -> list[dict]:
    checks = details.get("checks") or []
    if not isinstance(checks, list):
        return []
    out = []
    for check in checks:
        if not isinstance(check, dict) or not check.get("id"):
            continue
        out.append(
            {
                "id": str(check["id"]),
                "cluster": str(check.get("cluster") or ""),
                "passed": bool(check.get("passed")),
            }
        )
    return out


def _diagnostic_counts(report: dict) -> dict[str, int] | None:
    """Per-class counts of the grader's account-vs-amount diagnostics.

    Counts only: the classified account names are held-out expectations.
    """
    details = report.get("details")
    diagnostics = details.get("diagnostics") if isinstance(details, dict) else None
    if not isinstance(diagnostics, dict):
        return None
    classes = Counter((diagnostics.get("expected") or {}).values())
    classes["extra"] = len(diagnostics.get("extra") or [])
    return {name: classes[name] for name in DIAGNOSTIC_KEYS}


def _task_id_of(trial_result: dict, trial_dir: Path) -> str:
    name = trial_result.get("task_name") or ""
    if "/" in name:
        return name.rsplit("/", 1)[-1]
    return trial_dir.name.rsplit("__", 1)[0]


def _cost(agent_result: dict, model: str | None, prices: dict | None) -> float | None:
    direct = agent_result.get("cost_usd")
    if isinstance(direct, int | float):
        return float(direct)
    if not prices or not model:
        return None
    entry = (prices.get("models") or {}).get(model)
    if not entry:
        return None
    n_in = agent_result.get("n_input_tokens")
    n_out = agent_result.get("n_output_tokens")
    if not isinstance(n_in, int | float) or not isinstance(n_out, int | float):
        return None
    return (
        float(n_in) * float(entry.get("input_per_1m", 0))
        + float(n_out) * float(entry.get("output_per_1m", 0))
    ) / 1_000_000


def load_runs(job_dir: Path, manifest: dict, prices: dict | None = None) -> list[dict]:
    by_task = {entry["task_id"]: entry for entry in manifest.get("tasks", [])}
    job = _read_json(job_dir / "result.json") or {}
    rows: list[dict] = []
    for trial_dir in sorted(p for p in job_dir.iterdir() if p.is_dir()):
        result = _read_json(trial_dir / "result.json")
        if result is None:
            continue
        task_id = _task_id_of(result, trial_dir)
        entry = by_task.get(task_id, {})
        reward = _read_json(trial_dir / "verifier" / "reward.json") or {}
        verifier_report = _read_json(trial_dir / "verifier" / "report.json") or {}
        workflow_details = (
            _workflow_details(verifier_report)
            if entry.get("format") == "workflow" or "rubric_completion" in reward
            else {}
        )
        exception = (result.get("exception_info") or {}).get("exception_type")
        agent = (result.get("config") or {}).get("agent") or {}
        agent_result = result.get("agent_result") or {}
        answer = _read_json(trial_dir / "artifacts" / "app" / "answer.json")
        row = {
            "job_started_at": job.get("started_at"),
            "trial": trial_dir.name,
            "task_id": task_id,
            "agent": agent.get("name"),
            "model": agent.get("model_name"),
            "reward": float(reward.get("reward", 0) or 0),
            "rewards": reward,
            "rubric_completion": reward.get("rubric_completion"),
            "workflow_check_completion": reward.get("workflow_check_completion"),
            "workflow_clusters": _workflow_clusters(workflow_details),
            "workflow_checks": _workflow_checks(workflow_details),
            "wall_seconds": _duration_seconds(result.get("started_at"), result.get("finished_at")),
            "answer": (answer or {}).get("final_answer"),
            "confidence": reward.get("confidence", (answer or {}).get("confidence")),
            "parse_failure": reward.get("parse_failure"),
            "over_action": reward.get("over_action"),
            "diagnostics": _diagnostic_counts(verifier_report),
            "input_tokens": agent_result.get("n_input_tokens"),
            "output_tokens": agent_result.get("n_output_tokens"),
            "cost_usd": _cost(agent_result, agent.get("model_name"), prices),
            "task_checksum": result.get("task_checksum"),
            # Errored trials never reached grading; they are excluded
            # from score denominators but counted and listed.
            "exception": exception,
            "graded": exception is None and bool(reward),
        }
        for axis in (*AXES, "family", "seed", "generator_version", "track"):
            row[axis] = entry.get(axis)
        rows.append(row)
    return rows


def _answer_key(value) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _numeric_values(rows: list[dict], key: str) -> list[float]:
    return [float(row[key]) for row in rows if isinstance(row.get(key), int | float)]


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _mean_numeric(rows: list[dict], key: str) -> float | None:
    return _mean(_numeric_values(rows, key))


def _numeric_range(rows: list[dict], key: str) -> tuple[float | None, float | None]:
    values = _numeric_values(rows, key)
    return (min(values), max(values)) if values else (None, None)


def _workflow_cluster_means(rows: list[dict]) -> dict[str, float]:
    values: dict[str, list[float]] = {}
    for row in rows:
        for name, score in (row.get("workflow_clusters") or {}).items():
            values.setdefault(name, []).append(score)
    return {name: sum(scores) / len(scores) for name, scores in sorted(values.items())}


def _workflow_check_rates(rows: list[dict]) -> dict[str, dict]:
    rates: dict[str, dict] = {}
    for row in rows:
        for check in row.get("workflow_checks") or []:
            entry = rates.setdefault(
                check["id"],
                {"cluster": check.get("cluster") or "", "passed": 0, "total": 0},
            )
            entry["total"] += 1
            entry["passed"] += 1 if check.get("passed") else 0
    for entry in rates.values():
        entry["rate"] = entry["passed"] / entry["total"] if entry["total"] else 0.0
    return dict(sorted(rates.items()))


def aggregate_tasks(rows: list[dict], k: int | None = None) -> dict[str, dict]:
    """Per-task score over graded trials only.

    Errored trials (infrastructure failures before grading) are
    counted in n_errored but excluded from every denominator, so
    they can neither dilute a score nor form a majority answer.
    Tasks with no graded trial get score None.
    """
    tasks: dict[str, dict] = {}
    for task_id in sorted({r["task_id"] for r in rows}):
        all_trials = [r for r in rows if r["task_id"] == task_id]
        trials = [r for r in all_trials if r.get("graded", True)]
        fmt = all_trials[0].get("format")
        mean_reward = sum(r["reward"] for r in trials) / len(trials) if trials else 0.0
        score: float | None = mean_reward if trials else None
        agreement = None
        if fmt in CHOICE_FORMATS and len(trials) > 1:
            counts = Counter(_answer_key(r["answer"]) for r in trials)
            modal, modal_n = counts.most_common(1)[0]
            agreement = modal_n / len(trials)
            modal_trials = [r for r in trials if _answer_key(r["answer"]) == modal]
            score = sum(r["reward"] for r in modal_trials) / len(modal_trials)

        rubric_min, rubric_max = _numeric_range(trials, "rubric_completion")
        tasks[task_id] = {
            "task_id": task_id,
            "n_trials": len(trials),
            "n_successes": sum(1 for r in trials if r["reward"] == 1),
            "n_errored": len(all_trials) - len(trials),
            "mean_reward": mean_reward,
            "score": score,
            "agreement": agreement,
            "mean_rubric_completion": _mean_numeric(trials, "rubric_completion"),
            "rubric_min": rubric_min,
            "rubric_max": rubric_max,
            "mean_workflow_check_completion": _mean_numeric(trials, "workflow_check_completion"),
            "workflow_cluster_means": _workflow_cluster_means(trials),
            "workflow_check_rates": _workflow_check_rates(trials),
            "parse_failure_rate": _mean_numeric(trials, "parse_failure"),
            "mean_wall_seconds": _mean_numeric(trials, "wall_seconds"),
            "mean_cost_usd": _mean_numeric(trials, "cost_usd"),
            **{axis: all_trials[0].get(axis) for axis in GROUP_AXES},
        }
    # Reliability over repeated attempts, at one k for every task.
    k = k if k is not None else default_k(tasks)
    for task in tasks.values():
        n, c = task["n_trials"], task["n_successes"]
        task["k"] = k
        task["pass_at_k"] = pass_at_k(n, c, k) if k else None
        task["pass_hat_k"] = pass_hat_k(n, c, k) if k else None
    return tasks


def default_k(tasks: dict[str, dict]) -> int | None:
    """Fewest graded attempts on any graded task, so every task has a value."""
    counts = [task["n_trials"] for task in tasks.values() if task["n_trials"]]
    return min(counts) if counts else None


def _pct(value: float | None) -> str:
    return f"{value * 100:.1f}%" if value is not None else "n/a"


def _group_means(
    tasks: dict[str, dict], axis: str, field: str = "score"
) -> dict[str, tuple[int, float]]:
    groups: dict[str, list[float]] = {}
    for task in tasks.values():
        if task.get(field) is None:
            continue
        groups.setdefault(str(task.get(axis)), []).append(task[field])
    return {g: (len(v), sum(v) / len(v)) for g, v in sorted(groups.items())}


def _confidence_bins(rows: list[dict]) -> list[tuple[str, int, float]]:
    out = []
    for low, high in CONFIDENCE_BINS:
        in_bin = [
            r
            for r in rows
            if isinstance(r.get("confidence"), int | float) and low <= float(r["confidence"]) < high
        ]
        if in_bin:
            out.append(
                (
                    f"{low}-{high - 1}" if high <= 100 else f"{low}-100",
                    len(in_bin),
                    sum(r["reward"] for r in in_bin) / len(in_bin),
                )
            )
    return out


def _diagnostics_by_family(rows: list[dict]) -> list[str]:
    """Leaderboard section: diagnostic class shares per family."""
    by_family: dict[str, list[dict]] = {}
    for row in rows:
        if row.get("graded", True) and row.get("diagnostics"):
            by_family.setdefault(str(row.get("family")), []).append(row["diagnostics"])
    if not by_family:
        return []
    lines = [
        "",
        "## Account-vs-amount diagnostics",
        "",
        "Shares of expected account changes per family (informational; never reward): "
        "correct, right amount in the wrong account, right account with the wrong "
        "amount, or missing. Extra = unexplained movements in other accounts.",
        "",
        "| family | Trials | Expected changes | Correct | Wrong account | Wrong amount "
        "| Missing | Extra |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for family, counts in sorted(by_family.items()):
        totals = {name: sum(c[name] for c in counts) for name in DIAGNOSTIC_KEYS}
        changes = sum(totals[name] for name in DIAGNOSTIC_CLASSES)
        shares = " | ".join(
            _pct(totals[name] / changes if changes else None) for name in DIAGNOSTIC_CLASSES
        )
        lines.append(f"| {family} | {len(counts)} | {changes} | {shares} | {totals['extra']} |")
    return lines


def render_leaderboard(rows: list[dict], tasks: dict[str, dict], prices: dict | None) -> str:
    k = next((task["k"] for task in tasks.values()), None)
    graded_tasks = [t for t in tasks.values() if t["score"] is not None]
    overall = sum(t["score"] for t in graded_tasks) / len(graded_tasks) if graded_tasks else 0.0
    n_graded = sum(1 for r in rows if r.get("graded", True))
    n_errored = len(rows) - n_graded
    costs = [r["cost_usd"] for r in rows if isinstance(r.get("cost_usd"), int | float)]
    parse = [r["parse_failure"] for r in rows if isinstance(r.get("parse_failure"), int | float)]
    lines = [
        "# Leaderboard (generated by `oab report`)",
        "",
        f"Overall verified completion: **{overall * 100:.1f}%** "
        f"({band_for(overall * 100)}) over {len(graded_tasks)} graded task(s), "
        f"{n_graded} graded trial(s).",
        "",
    ]
    reliable = [task for task in tasks.values() if task["pass_at_k"] is not None]
    if reliable:
        at = _mean([task["pass_at_k"] for task in reliable])
        hat = _mean([task["pass_hat_k"] for task in reliable])
        lines += [
            f"Reliability (k={k}): pass@{k} **{_pct(at)}**, pass^{k} **{_pct(hat)}** over "
            f"{len(reliable)} task(s) with at least {k} graded attempts. pass^{k} (every "
            "attempt verified) is the deployment bar; mean reward is diagnostic.",
            "",
        ]
    elif k is not None:
        lines += [
            f"Reliability (k={k}): not available (no task has {k} graded attempts).",
            "",
        ]
    if n_errored:
        exceptions = Counter(r.get("exception") for r in rows if not r.get("graded", True))
        detail = ", ".join(f"{name} x{count}" for name, count in sorted(exceptions.items()))
        lines.append(
            f"Excluded as infrastructure errors: {n_errored} trial(s) "
            f"({detail}). Scores below never count these in denominators."
        )
        lines.append("")
    if costs:
        verified = sum(1 for r in rows if r["reward"] == 1)
        lines.append(
            f"Cost: mean {sum(costs) / len(costs):.4f} USD/trial"
            + (f"; {sum(costs) / verified:.4f} USD per verified trial." if verified else ".")
            + (f" Prices as of {prices.get('as_of')}." if prices else "")
        )
    if parse:
        lines.append(f"Parse-failure rate: {sum(parse) / len(parse) * 100:.1f}%.")
    over = _numeric_values(rows, "over_action")
    if over:
        acted = int(sum(over))
        lines.append(
            f"Over-action rate (no-action controls): **{acted / len(over) * 100:.1f}%** "
            f"({acted} of {len(over)} trials changed a ledger that needed no change)."
        )
    lines += [
        "",
        "## Per task",
        "",
        f"| Task | Format | Graded | Errored | Score | Agreement | pass@{k} | pass^{k} |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for task in tasks.values():
        agreement = f"{task['agreement']:.2f}" if task["agreement"] is not None else "-"
        lines.append(
            f"| {task['task_id']} | {task.get('format')} | {task['n_trials']} "
            f"| {task['n_errored']} | {_pct(task['score'])} | {agreement} "
            f"| {_pct(task['pass_at_k'])} | {_pct(task['pass_hat_k'])} |"
        )
    workflow_tasks = [
        task for task in tasks.values() if task.get("mean_rubric_completion") is not None
    ]
    if workflow_tasks:
        lines += [
            "",
            "## Workflow rubric",
            "",
            "Rubric completion is diagnostic; verified completion above still requires reward 1.",
            "",
            "| Task | Graded | Rubric | Rubric range | Checks | Parse failures "
            "| Mean wall (sec) | Mean cost |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for task in workflow_tasks:
            checks = task.get("mean_workflow_check_completion")
            checks_label = f"{checks * 100:.1f}%" if checks is not None else "-"
            rubric_min, rubric_max = task.get("rubric_min"), task.get("rubric_max")
            range_label = (
                f"{rubric_min * 100:.1f}%–{rubric_max * 100:.1f}%"
                if rubric_min is not None and rubric_max is not None
                else "-"
            )
            parse = task.get("parse_failure_rate")
            parse_label = f"{parse * 100:.1f}%" if parse is not None else "-"
            wall = task.get("mean_wall_seconds")
            wall_label = f"{wall:.1f}" if wall is not None else "-"
            cost = task.get("mean_cost_usd")
            cost_label = f"${cost:.4f}" if cost is not None else "-"
            lines.append(
                f"| {task['task_id']} | {task['n_trials']} | "
                f"{task['mean_rubric_completion'] * 100:.1f}% | {range_label} | "
                f"{checks_label} | {parse_label} | {wall_label} | {cost_label} |"
            )
        cluster_tasks = [task for task in workflow_tasks if task.get("workflow_cluster_means")]
        if cluster_tasks:
            lines += [
                "",
                "## Workflow issue clusters",
                "",
                "| Task | Cluster | Mean completion |",
                "|---|---|---:|",
            ]
            for task in cluster_tasks:
                for cluster, mean in task["workflow_cluster_means"].items():
                    lines.append(f"| {task['task_id']} | {cluster} | {mean * 100:.1f}% |")
        check_tasks = [task for task in workflow_tasks if task.get("workflow_check_rates")]
        if check_tasks:
            lines += [
                "",
                "## Workflow checks",
                "",
                "| Task | Check | Cluster | Passed | Rate |",
                "|---|---|---|---:|---:|",
            ]
            for task in check_tasks:
                for check_id, entry in task["workflow_check_rates"].items():
                    lines.append(
                        f"| {task['task_id']} | {check_id} | {entry['cluster']} | "
                        f"{entry['passed']}/{entry['total']} | {entry['rate'] * 100:.1f}% |"
                    )
    for axis in GROUP_AXES:
        lines += [
            "",
            f"## By {axis}",
            "",
            f"| {axis} | Tasks | Score | pass@{k} | pass^{k} |",
            "|---|---:|---:|---:|---:|",
        ]
        at = _group_means(tasks, axis, "pass_at_k")
        hat = _group_means(tasks, axis, "pass_hat_k")
        for group, (count, mean) in _group_means(tasks, axis).items():
            lines.append(
                f"| {group} | {count} | {_pct(mean)} "
                f"| {_pct(at.get(group, (0, None))[1])} | {_pct(hat.get(group, (0, None))[1])} |"
            )
    lines += _diagnostics_by_family(rows)
    bins = _confidence_bins(rows)
    if bins:
        lines += [
            "",
            "## Confidence calibration",
            "",
            "| Confidence | Trials | Reward rate |",
            "|---|---:|---:|",
        ]
        for label, count, rate in bins:
            lines.append(f"| {label} | {count} | {rate * 100:.1f}% |")
    lines.append("")
    return "\n".join(lines)


def write_report(
    job_dir: Path,
    manifest_path: Path,
    prices: dict | None = None,
    out_dir: Path | None = None,
    k: int | None = None,
) -> tuple[Path, Path]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = load_runs(job_dir, manifest, prices=prices)
    if not rows:
        raise ValueError(f"no trial results found under {job_dir}")
    tasks = aggregate_tasks(rows, k=k)
    out = out_dir or job_dir
    out.mkdir(parents=True, exist_ok=True)
    runs_path = out / "runs.jsonl"
    runs_path.write_text(
        "".join(json.dumps(row, default=str) + "\n" for row in rows), encoding="utf-8"
    )
    board_path = out / "leaderboard.md"
    board_path.write_text(render_leaderboard(rows, tasks, prices), encoding="utf-8")
    return runs_path, board_path
