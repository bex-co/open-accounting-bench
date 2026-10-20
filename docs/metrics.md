# Metrics

Primary metric — **Verified Task Completion Rate**: fraction of tasks
with `reward = 1` (all five verification layers pass). Computed by
`tasks/metric.py` from Harbor's rewards JSONL; missing rewards count
as 0.

| Metric (output key) | Source | Question |
|---|---|---|
| `verified_task_completion_rate` | mean `reward` | Was the accounting objective fully achieved? |
| `structural_validity` | layer mean | Is the ledger well-formed and balanced? |
| `semantic_accuracy` | layer mean | Do entries represent the economic events? |
| `economic_consistency` | layer mean | Recorded once, in the right period? |
| `reconciliation_accuracy` | layer mean | Does the ledger reconcile to evidence? |
| `operational_integrity` | layer mean | Audit trail kept, nothing unrelated changed? |
| `unauthorized_modification_rate` | 1 − integrity | How often did the agent touch what it shouldn't? |
| `partial` | layer mean | Diagnostic only; never a completion claim |

Report alongside every result: track (stable/dynamic/holdout), seeds,
generator version, model + agent + tool access, attempts (`-k`),
concurrency, cost and wall time per verified task (from Harbor job
output). Reliability across generated variations = completion rate
over multiple seeds of the same family; report per family, not only
in aggregate. Model-only and tool-using-agent results are reported
separately.

## Job aggregation (`oab report`)

`oab report --job <harbor-job-dir>` joins trial results with
`tasks/manifest.json` and writes, into the job directory:

- `runs.jsonl` — one row per trial: `task_id`, taxonomy
  (`category`/`framework`/`level`/`format`), `family`, `seed`,
  `generator_version`, `track`, `agent`, `model`, `reward` + full
  `rewards`, `answer`, `confidence`, `parse_failure`, token counts,
  `cost_usd`, `task_checksum`, job timestamp. This is the auditable
  run registry; archive it with any published result.
- `leaderboard.md` — overall completion with interpretation band
  (>=90% Excellent, 75-90% Strong, 60-75% Moderate, 50-60% Weak,
  <50% Poor), per-task scores (majority vote across attempts for
  choice formats, mean reward otherwise; run Harbor with `-k 3`),
  per-taxonomy-axis group means, mean cost per trial and per
  verified trial, parse-failure rate, and confidence-bin reward
  rates. Costs come from Harbor's `cost_usd` when present, else
  token counts × an external price table (`--prices`, see
  `prices.example.json`; always cite its `as_of` date).

Answer-format rewards: `answer_accuracy` is 1/0 for single-choice
and numeric (within absolute + relative tolerance), and
`(correct - incorrect marks) / |gold|` for multiple-choice (may be
negative; `reward` still requires the exact gold set).
`format_validity` / `parse_failure` expose output-format sensitivity
without removing failures from any denominator.
