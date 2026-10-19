# Open Accounting Bench

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

The agent works in an isolated, no-network container and edits
`/app/ledger.beancount`. Grading uses Harbor's separate verifier
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

## v0.1 task families

Four families, one frozen Stable instance each; each generator yields
hundreds of reproducible instances. The 90-day target is 12–15 validated
generators (see [docs/task-families.md](docs/task-families.md) and
[docs/roadmap.md](docs/roadmap.md)).

| Task | Family | Trap it catches |
|---|---|---|
| `classify-operating-expense` | Transaction classification | Capitalizing a consumable as an asset |
| `bank-recon-missing-fee` | Bank reconciliation | Duplicate import; missing bank fee |
| `prepaid-insurance-adjustment` | Adjustments & corrections | Expensing a full 12-month prepayment |
| `correct-misclassification` | Ledger integrity & reporting | Rewriting history instead of correcting entries |

## Quickstart

Run with [Harbor](https://docs.harborframework.com/getting-started/installation)
(Pier, the Harbor-compatible runner used by DeepSWE, also works):

```bash
git clone https://github.com/bex-co/open-accounting-bench
cd open-accounting-bench

# Sanity-check solvability with the Oracle agent (no API key needed)
harbor run -p tasks/classify-operating-expense -a oracle

# Evaluate an agent on the Stable track
export ANTHROPIC_API_KEY=...
harbor run -p tasks -a "<agent>" -m "anthropic/<model>"
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
  cli.py        oab generate / verify / validate / list
tasks/          Stable-track Harbor dataset (+ dataset.toml, manifest, metric.py)
tests/          Repo tests: verifier layers, generator determinism, task health
docs/           Methodology, verification, metrics, governance, roadmap
memo.md         Founding strategy proposal
```

## Contributing

New task families, verifiers, and jurisdiction packs are welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md). All scenarios are original synthetic
data ([PROVENANCE.md](PROVENANCE.md)).

## License

Apache-2.0. See [LICENSE](LICENSE).
