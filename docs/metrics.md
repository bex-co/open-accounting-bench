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
