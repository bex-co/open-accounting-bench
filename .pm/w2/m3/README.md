# w2 · m3 — pass^k and pass@k reliability metrics

**Worker:** worker2 **Goal:** `oab report` reports pass@k and pass^k from multi-attempt runs, so results show both best-case and every-time reliability. **Status:** todo (t001, t002, t004–t007 done)

## Tasks (in order)

| id   | title | est | depends_on |
| ---- | ----- | --- | ---------- |
| t001 | Define the estimators — **DONE** | 30m | — |
| t002 | Aggregate in `oab report` — **DONE** | 60m | t001 |
| t004 | Document the metrics — **DONE** | 30m | t002 |
| t005 | Adoption surface — **DONE** | 20m | t002, t004 |
| t006 | Simplify — **DONE** | 15m | t005 |
| t007 | Test coverage — **DONE** | 20m | t005 |
| t008 | Closeout | 10m | t007 |

## Dropped

- ~~**t003**~~ — Expose in the dataset metric — dropped 2026-11-05: impossible under Harbor 0.24.0. `harbor/metrics/uv_script.py` hands the dataset metric script anonymous reward dicts (one JSON line per trial, `RewardDict = dict[str, NumericReward]`, no task identity), so `tasks/metric.py` cannot group attempts by task. Harbor's own `utils/pass_at_k.py` also returns nothing when a reward dict has more than one key, as OAB's do. `oab report` (t002) is where pass@k and pass^k are computed.

## Definition of done

Runs with k ≥ 2 attempts show pass@k and pass^k in `oab report` (the Harbor dataset metric cannot carry them — see Dropped); the estimators are unit-tested on edge cases; `docs/metrics.md` documents them.

## Source + Goal linkage

- **Source:** brainstorm 2026-11-04 (`/pm-brainstorm for w2`, lessons from accounting benchmarks catalogued by benchmark-radar); APEX-Accounting reports a mean-criteria score above 50% but Pass^8 below 3%.
- **Goal linkage:** B3 — gives labs and agent builders a reliability measure suited to accounting deployment, where every-time correctness matters more than average.
- **Expected outcome:** Anyone running OAB with `-k` sees how often a model is right on every attempt, not only on average.
- **Why now:** It is a prerequisite for the roadmap's first baseline runs; changing the headline metric after baselines are published would force reruns.
- **Closing tasks:** Adoption surface included (new report columns and option). Accounting review omitted: aggregation only, no change to accounting semantics or verifier scoring.
