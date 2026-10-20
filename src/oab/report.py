"""Aggregate a Harbor job into runs + a stratified leaderboard.

Inputs: a Harbor job directory (per-trial result.json, verifier
reward.json, collected artifacts) joined with the dataset manifest
for taxonomy. Outputs (into the job dir by default):

- runs.jsonl      one row per trial (the auditable run registry)
- leaderboard.md  overall + per category/framework/level/format,
                  interpretation bands, cost, confidence calibration

Choice formats aggregate by majority vote over attempts (use -k 3);
other formats by mean reward. Missing rewards count as 0.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

AXES = ("category", "framework", "level", "format")
CHOICE_FORMATS = ("single-choice", "multiple-choice")
BANDS = [
    (90, "Excellent (near-expert)"),
    (75, "Strong (professional-level)"),
    (60, "Moderate (requires verification)"),
    (50, "Weak (below professional threshold)"),
    (0, "Poor (not suitable for professional use)"),
]
CONFIDENCE_BINS = [(0, 50), (50, 70), (70, 85), (85, 95), (95, 101)]


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
            "answer": (answer or {}).get("final_answer"),
            "confidence": reward.get("confidence", (answer or {}).get("confidence")),
            "parse_failure": reward.get("parse_failure"),
            "input_tokens": agent_result.get("n_input_tokens"),
            "output_tokens": agent_result.get("n_output_tokens"),
            "cost_usd": _cost(agent_result, agent.get("model_name"), prices),
            "task_checksum": result.get("task_checksum"),
        }
        for axis in (*AXES, "family", "seed", "generator_version", "track"):
            row[axis] = entry.get(axis)
        rows.append(row)
    return rows


def _answer_key(value) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def aggregate_tasks(rows: list[dict]) -> dict[str, dict]:
    """Per-task score: majority vote for choice formats, mean otherwise."""
    tasks: dict[str, dict] = {}
    for task_id in sorted({r["task_id"] for r in rows}):
        trials = [r for r in rows if r["task_id"] == task_id]
        fmt = trials[0].get("format")
        mean_reward = sum(r["reward"] for r in trials) / len(trials)
        score = mean_reward
        agreement = None
        if fmt in CHOICE_FORMATS and len(trials) > 1:
            counts = Counter(_answer_key(r["answer"]) for r in trials)
            modal, modal_n = counts.most_common(1)[0]
            agreement = modal_n / len(trials)
            modal_trials = [r for r in trials if _answer_key(r["answer"]) == modal]
            score = sum(r["reward"] for r in modal_trials) / len(modal_trials)
        tasks[task_id] = {
            "task_id": task_id,
            "n_trials": len(trials),
            "mean_reward": mean_reward,
            "score": score,
            "agreement": agreement,
            **{axis: trials[0].get(axis) for axis in AXES},
        }
    return tasks


def _group_means(tasks: dict[str, dict], axis: str) -> dict[str, tuple[int, float]]:
    groups: dict[str, list[float]] = {}
    for task in tasks.values():
        groups.setdefault(str(task.get(axis)), []).append(task["score"])
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


def render_leaderboard(rows: list[dict], tasks: dict[str, dict], prices: dict | None) -> str:
    overall = sum(t["score"] for t in tasks.values()) / len(tasks) if tasks else 0.0
    costs = [r["cost_usd"] for r in rows if isinstance(r.get("cost_usd"), int | float)]
    parse = [r["parse_failure"] for r in rows if isinstance(r.get("parse_failure"), int | float)]
    lines = [
        "# Leaderboard (generated by `oab report`)",
        "",
        f"Overall verified completion: **{overall * 100:.1f}%** "
        f"({band_for(overall * 100)}) over {len(tasks)} task(s), {len(rows)} trial(s).",
        "",
    ]
    if costs:
        verified = sum(1 for r in rows if r["reward"] == 1)
        lines.append(
            f"Cost: mean {sum(costs) / len(costs):.4f} USD/trial"
            + (f"; {sum(costs) / verified:.4f} USD per verified trial." if verified else ".")
            + (f" Prices as of {prices.get('as_of')}." if prices else "")
        )
    if parse:
        lines.append(f"Parse-failure rate: {sum(parse) / len(parse) * 100:.1f}%.")
    lines += [
        "",
        "## Per task",
        "",
        "| Task | Format | Trials | Score | Agreement |",
        "|---|---|---:|---:|---:|",
    ]
    for task in tasks.values():
        agreement = f"{task['agreement']:.2f}" if task["agreement"] is not None else "-"
        lines.append(
            f"| {task['task_id']} | {task.get('format')} | {task['n_trials']} "
            f"| {task['score'] * 100:.1f}% | {agreement} |"
        )
    for axis in AXES:
        lines += ["", f"## By {axis}", "", f"| {axis} | Tasks | Score |", "|---|---:|---:|"]
        for group, (count, mean) in _group_means(tasks, axis).items():
            lines.append(f"| {group} | {count} | {mean * 100:.1f}% |")
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
) -> tuple[Path, Path]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = load_runs(job_dir, manifest, prices=prices)
    if not rows:
        raise ValueError(f"no trial results found under {job_dir}")
    tasks = aggregate_tasks(rows)
    out = out_dir or job_dir
    out.mkdir(parents=True, exist_ok=True)
    runs_path = out / "runs.jsonl"
    runs_path.write_text(
        "".join(json.dumps(row, default=str) + "\n" for row in rows), encoding="utf-8"
    )
    board_path = out / "leaderboard.md"
    board_path.write_text(render_leaderboard(rows, tasks, prices), encoding="utf-8")
    return runs_path, board_path
