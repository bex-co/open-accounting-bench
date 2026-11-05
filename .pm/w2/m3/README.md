# w2 · m3 — pass^k and pass@k reliability metrics

**Worker:** worker2 **Goal:** `oab report` and the dataset metric report pass@k and pass^k from multi-attempt runs, so results show both best-case and every-time reliability. **Status:** todo

## Tasks (in order)

| id   | title | est | depends_on |
| ---- | ----- | --- | ---------- |
| t001 | Define the estimators | 30m | — |
| t002 | Aggregate in `oab report` | 60m | t001 |
| t003 | Expose in the dataset metric | 45m | t001 |
| t004 | Document the metrics | 30m | t002 |
| t005 | Adoption surface | 20m | t002, t003, t004 |
| t006 | Simplify | 15m | t005 |
| t007 | Test coverage | 20m | t005 |
| t008 | Closeout | 10m | t007 |

## Definition of done

Runs with k ≥ 2 attempts show pass@k and pass^k in `oab report` and the Harbor dataset metric; the estimators are unit-tested on edge cases; `docs/metrics.md` documents them.

## Source + Goal linkage

- **Source:** brainstorm 2026-11-04 (`/pm-brainstorm for w2`, lessons from accounting benchmarks catalogued by benchmark-radar); APEX-Accounting reports a mean-criteria score above 50% but Pass^8 below 3%.
- **Goal linkage:** B3 — gives labs and agent builders a reliability measure suited to accounting deployment, where every-time correctness matters more than average.
- **Expected outcome:** Anyone running OAB with `-k` sees how often a model is right on every attempt, not only on average.
- **Why now:** It is a prerequisite for the roadmap's first baseline runs; changing the headline metric after baselines are published would force reruns.
- **Closing tasks:** Adoption surface included (new report columns and metric keys). Accounting review omitted: aggregation only, no change to accounting semantics or verifier scoring.
