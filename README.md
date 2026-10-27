# Open Accounting Bench

[![CI](https://github.com/bex-co/open-accounting-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/bex-co/open-accounting-bench/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![GitHub stars](https://img.shields.io/github/stars/bex-co/open-accounting-bench?style=social)](https://github.com/bex-co/open-accounting-bench/stargazers)

> ⭐ If this looks useful, please star the repo — it helps other agent
> and accounting builders find it.

> **Status: under active development (pre-alpha).** This repository is
> an early v0.2 work in progress, not a stable benchmark release. Task
> families, generators, verifiers, and scoring may change without
> notice, and results produced today are not comparable across
> revisions and should not be cited. See
> [docs/roadmap.md](docs/roadmap.md) for what is done and what is next.

**The open, living, and executable benchmark for AI accounting agents.**

Open Accounting Bench (OAB) measures whether an AI agent can *do*
accounting correctly — transform financial evidence into a valid,
economically accurate, auditable ledger state — not merely whether it can
answer questions about accounting. Design rationale:
[memo.md](memo.md).

Three principles:

1. **Dynamic task generation** — fresh instances are generated from
   validated, parameterized task families with deterministic seeds,
   instead of a fixed question bank.
2. **Executable verification** — grading is deterministic and state-based
   (five layers, see [docs/verification.md](docs/verification.md)); no
   LLM judge is required. A balanced-but-misclassified entry fails.
3. **Operational evaluation** — agents edit a real [Beancount](https://beancount.github.io/)
   ledger in an isolated [Harbor](https://docs.harborframework.com/tasks/overview)
   environment; only the resulting accounting state is graded.

## Task format

OAB tasks use the [Harbor task format](https://docs.harborframework.com/tasks/overview),
following the conventions of [DeepSWE](https://github.com/datacurve-ai/deep-swe):

```text
task.toml         Metadata (family, seed, generator version, limits)
instruction.md    The prompt the agent sees (canary-guarded)
environment/      Dockerfile + /app ledger, policy, chart, source documents
tests/            Separate-verifier image, grader, held-out expectations
solution/         Reference final ledger (held out from the agent)
```

The agent works in an isolated, no-network container and produces one
graded file (`/app/ledger.beancount`, or `/app/answer.json` for
choice/numeric formats). Grading uses Harbor's separate verifier
environment: the ledger is declared as an artifact in `task.toml`,
copied into a pristine verifier container, and graded there. The
reference ledger in `solution/` is never used at grading time; it exists
so reviewers (and the Oracle agent) can spot-check solvability.

The verifier writes under `/logs/verifier/`:

```text
reward.json   Binary reward + five layer scores + partial
report.json   Per-layer pass/fail with human-readable failures
run.log       Raw verifier output
```

Primary metric: **Verified Task Completion Rate** (all five layers
pass). See [docs/metrics.md](docs/metrics.md).

## Tracks

| Track | Purpose | How |
|---|---|---|
| Stable | Frozen, versioned instances for comparability | Committed under `tasks/` (fixed seeds) |
| Dynamic | Fresh instances from the same families | `oab generate --family F --seed N` |
| Holdout | Generalization check vs. generator overfitting | Unpublished families/seeds; governance in [docs/governance.md](docs/governance.md) |

## Task families

182 frozen Stable instances so far, one per generator family; each
generator yields hundreds of reproducible instances. Tasks are tagged by
category, framework, level, format, and skill, and crosswalked to the
AICPA CPA blueprint and ACCA syllabus (`crosswalks/`). The table below
shows the original fifteen seed families; the full, current catalog is
[`tasks/manifest.json`](tasks/manifest.json), with the coverage matrix in
[docs/task-families.md](docs/task-families.md) (see also
[docs/roadmap.md](docs/roadmap.md)).

| Task | Format | Trap it catches |
|---|---|---|
| `classify-operating-expense` | journal-entry | Capitalizing a consumable as an asset |
| `bank-recon-missing-fee` | journal-entry | Duplicate import; missing bank fee |
| `prepaid-insurance-adjustment` | journal-entry | Expensing a full 12-month prepayment |
| `correct-misclassification` | journal-entry | Rewriting history instead of correcting entries |
| `mc-capitalization-treatment` | multiple-choice | Selecting the expense-it-now distractor |
| `mgmt-break-even-units` | numeric | Answering current volume instead of break-even |
| `ifrs-capitalize-borrowing-costs` | journal-entry (IFRS) | Expensing qualifying borrowing costs |
| `receivable-allowance-trueup` | journal-entry | Expensing the full required allowance, ignoring the existing balance |
| `accrual-deferral-reversal` | journal-entry | Booking the full bill without reversing the accrual |
| `payables-statement-recon` | journal-entry | Booking timing differences to force the ledger to the supplier statement |
| `ppe-disposal` | journal-entry | Computing the gain without the disposal month's depreciation |
| `inventory-costing-nrv` | journal-entry | Average cost under a FIFO policy; skipping the NRV write-down |
| `revenue-bundle-allocation` | journal-entry | Allocating on invoice line prices instead of standalone selling prices |
| `suspense-clearance` | journal-entry | Zeroing the clearing account without fixing its causes |
| `loan-effective-interest` | journal-entry | Expensing only the coupon instead of effective interest |

## Quickstart

Run with [Harbor](https://docs.harborframework.com/getting-started/installation)
(Pier, the Harbor-compatible runner used by DeepSWE, also works):

```bash
git clone https://github.com/bex-co/open-accounting-bench
cd open-accounting-bench

# Sanity-check solvability with the Oracle agent (no API key needed)
harbor run -p tasks/classify-operating-expense -a oracle

# Evaluate an agent on the Stable track (3 attempts per task), then aggregate
export ANTHROPIC_API_KEY=...
harbor run -p tasks -a "<agent>" -m "anthropic/<model>" -k 3 -o jobs --job-name eval-1
uv run oab report --job jobs/eval-1   # writes runs.jsonl + leaderboard.md
```

Generate fresh Dynamic-track instances and grade locally without Harbor:

```bash
uv run oab list
uv run oab generate --family bank-recon-missing-fee --seed 777 --out /tmp/oab-dynamic
uv run oab verify --task-dir /tmp/oab-dynamic/bank-recon-missing-fee   # oracle ledger
uv run oab validate --tasks tasks                                     # repo health
```

## Repository layout

```text
src/oab/        Generator + verifier package (stdlib only)
  families.py   Parameterized task families (seed -> instance)
  generate.py   Instance -> Harbor task directory, dataset files
  _verifier_core.py  Five-layer grader; copied verbatim into each task
  cli.py        oab generate / verify / validate / report / list
  report.py     Harbor job -> runs.jsonl + stratified leaderboard.md
tasks/          Stable-track Harbor dataset (+ dataset.toml, manifest, metric.py)
tests/          Repo tests: verifier layers, generator determinism, task health
docs/           Methodology, verification, metrics, governance, roadmap
memo.md         Founding strategy proposal
AGENTS.md       Guide for coding agents (Codex, Claude Code)
.agents/skills/ Development skills: /pm, /pm-brainstorm, /loopx, /ship
.pm/            Public roadmap board
```

## Contributing

New task families, verifiers, and jurisdiction packs are welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md). All scenarios are original synthetic
data ([PROVENANCE.md](PROVENANCE.md)).

## License

Apache-2.0. See [LICENSE](LICENSE).
