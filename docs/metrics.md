# Metrics

Primary metric — **Verified Task Completion Rate**: fraction of tasks
with `reward = 1`. For ledger tasks all five verification layers must
pass; workflow tasks must additionally pass every gate check in their
`workflow_rubric` layer. Computed by `tasks/metric.py` from Harbor's
rewards JSONL; missing rewards count as 0.

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
| `workflow_rubric` | workflow layer mean when present | How much of the determination rubric was reached? |
| `rubric_completion` | weighted determination mean | Diagnostic workflow progress; not verified completion |
| `workflow_check_completion` | raw passed-check fraction | Which individual workflow checks were reached? |
| `over_action` | no-action controls only | Did the agent change a ledger that needed no change? (`oab report` prints the rate) |

Report alongside every result: track (stable/dynamic/holdout), seeds,
generator version, model + agent + tool access, attempts (`-k`),
concurrency, cost and wall time per verified task (from Harbor job
output). Reliability across generated variations = completion rate
over multiple seeds of the same family; report per family, not only
in aggregate. Model-only and tool-using-agent results are reported
separately.

### Reliability: pass@k and pass^k

With `n` graded attempts of a task and `c` of them verified
(`reward = 1`), `oab report` computes, for a chosen `k <= n`:

| Metric | Formula | Question |
|---|---|---|
| pass@k | 1 − C(n−c, k) / C(n, k) | Is at least one of k attempts right? (best case) |
| pass^k | C(c, k) / C(n, k) | Are all k attempts right? (every time) |

Both are unbiased estimates over draws of k attempts without
replacement; with `k = 1` both equal the mean reward. Cite **pass^k**
for deployment and reliability claims — an accounting agent that is
right on average but not every time still needs a reviewer on every
run — and report mean reward and pass@k as diagnostics beside it.
Always state `k` and `n`. Tasks with fewer than `k` graded attempts
are reported as n/a and excluded, never counted as 0; infrastructure
failures stay out of `n` as everywhere else. These metrics exist only
in `oab report`: Harbor's dataset metric receives anonymous per-trial
rewards with no task identity, so `tasks/metric.py` cannot group
attempts by task.

## Job aggregation (`oab report`)

`oab report --job <harbor-job-dir>` joins trial results with
`tasks/manifest.json` and writes, into the job directory:

- `runs.jsonl` — one row per trial: `task_id`, taxonomy
  (`category`/`framework`/`level`/`format`/`skill`), `family`, `seed`,
  `generator_version`, `track`, `agent`, `model`, `reward` + full
  `rewards`, workflow rubric/check completion when present, sanitized
  workflow cluster scores and check IDs/cluster/pass values (never
  verifier expected or actual values), `answer`, `confidence`,
  `parse_failure`, `over_action` (no-action controls), account-vs-amount
  diagnostic counts (`diagnostics`; class counts only), token counts,
  `cost_usd`, `wall_seconds`, the manifest `review` status,
  `task_checksum`, and job timestamp. This is the auditable run
  registry; archive it with any published result.
  Trials with an exception and no reward (infrastructure failures
  before grading) are marked `graded: false` with their
  `exception` type: excluded from every score denominator in
  `oab report`, but counted and listed. (Harbor's own dataset
  metric still averages missing rewards as 0; cite `oab report`
  numbers for capability claims.)
- `leaderboard.md` — overall completion with interpretation band
  (>=90% Excellent, 75-90% Strong, 60-75% Moderate, 50-60% Weak,
  <50% Poor), per-task scores (majority vote across attempts for
  choice formats, mean reward otherwise; run Harbor with `-k 3`),
  per-taxonomy-axis and per-family group means, pass@k and pass^k
  (headline, per task, per group; `--k`, default the fewest graded
  attempts on any task), mean cost per trial and per
  verified trial, parse-failure rate, workflow rubric/check means
  and rubric range, issue-cluster means, per-check pass counts,
  mean wall time and mean cost when workflow reports are present, and
  confidence-bin reward rates, per-family account-vs-amount
  diagnostic shares, the share of graded tasks with an accounting
  review on record (`--reviewed-only` scores only those tasks), and the
  reward rate by token-use tercile (descriptive only: harder tasks draw
  more tokens, so compare budgets by rerunning with a controlled budget). Costs come from Harbor's `cost_usd` when present, else
  token counts × an external price table (`--prices`, see
  `prices.example.json`; always cite its `as_of` date).

Answer-format rewards: `answer_accuracy` is 1/0 for single-choice
and numeric (within absolute + relative tolerance), and
`(correct - incorrect marks) / |gold|` for multiple-choice (may be
negative; `reward` still requires the exact gold set).
`format_validity` / `parse_failure` expose output-format sensitivity
without removing failures from any denominator.

## Workflow difficulty calibration

A workflow family is not called professionally difficult from its
design label alone. Before agents run, record the panel date, exact
agent/model identifiers, generated seeds, attempts per seed, Harbor
settings, generator/scoring version, task checksums, budgets, and
denominators. Every planned trial is accounted for as graded,
infrastructure-excluded, or missing; parse failures with a verifier
result stay graded, while infrastructure failures are counted and
listed but excluded from capability denominators. Retries never
silently replace a capability result.

Report verified completion separately from diagnostic rubric
completion, with rubric/check distributions by seed and attempt,
issue-cluster and per-check pass rates, saturated/dead or duplicated
checks, adjudicated false accepts/rejects, parse failures, cost, and
wall time. A dated model panel is a diagnostic snapshot—not the
definition of accounting correctness and not a vendor ranking. The
release decision is explicitly **promote**, **tune and recalibrate**,
or **reject**, and it must state whether later workflow families may
proceed and whether any Stable freeze is authorized.

The preregistered target band is stated on pass^k of full-completion
reward at one fixed per-trial budget tier, recorded with the panel;
rubric completion is reported as a diagnostic, not as the target
([methodology.md](methodology.md#professional-workflow-lifecycle)).

## Framework coverage

`oab crosswalk` reports, per crosswalk edition and section, how many
distinct external items OAB reaches, each counted once by its
strongest link ([task-families.md](task-families.md#crosswalks-to-external-frameworks)):

- **Covered** — some generator is `equal` to or a `superset-of` the
  item with strength >= 7. Only this tier supports "OAB covers the
  item".
- **Partial** — best link is `subset-of`: OAB tests a slice of the item.
- **Touched** — best link is `intersects-with`, or a weak superset.
- **Unreviewed** — items whose best link is still `proposed`.

- **Gradable** — items left after `[[out_of_scope]]` exclusions (items
  no deterministic grader can check: pure recall, disclosure prose).
  Shown only for sections listed in `framework.triaged`; `—` otherwise.

Cite coverage with its basis and both denominators, e.g. "covers 0 of
97 gradable (113 total) FAR representative tasks (AICPA blueprint 2027;
equal/superset-of, strength >= 7); 9 partial, 4 touched; 0
unreviewed". Never merge partial or touched into
covered, and do not publish a coverage claim while its counted links
are unreviewed. Unreviewed also counts unreviewed exclusions, so the
gradable denominator cannot be cited before its exclusions are
reviewed. Exclusions are recorded, not inclusions: a missing record
keeps an item in the denominator, the conservative direction.

