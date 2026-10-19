# Methodology

Research question: *Can an AI agent correctly transform financial
evidence into a valid, economically accurate, and auditable accounting
state?* (Founding proposal: [memo.md](../memo.md).)

## SWE-bench analogy

| SWE-bench / DeepSWE | Open Accounting Bench |
|---|---|
| Git repository | Beancount ledger + source documents |
| Issue / task prompt | Accounting task (`instruction.md`) |
| Code patch | Appended journal entries (ledger state change) |
| Held-out tests | Five-layer accounting verifier |
| `f2p` / `p2p` fractions | Per-layer scores + `partial` |
| Binary resolved rate | Verified Task Completion Rate |

As in DeepSWE, grading is behavior/state-based: any ledger that reaches
the required accounting state passes, regardless of narration text or
entry decomposition. The reference solution is held out and never used
at grading time.

## Dynamic generation, reproducibility

Each task family is a parameterized generator (`src/oab/families.py`).
An instance is fully determined by `(family, seed, generator_version)`,
all recorded in `task.toml` metadata, `tests/expected.json`, and
`tasks/manifest.json`. Varying only numbers is not enough to resist
overfitting; families also vary vendors, dates, document structure, and
—which accounts/traps are in play — as families grow.

Tracks: **Stable** (frozen seeds, committed), **Dynamic** (fresh seeds
at run time), **Holdout** (unpublished families/seeds for
generalization; see [governance.md](governance.md)).

## Coverage layers

Scores are reported per capability and regulatory context, never as one
opaque global number:

1. **Accounting Core** — double-entry, classification, reconciliation,
   ledger integrity. (All v0.1 tasks.)
2. **Standards** — IFRS / US GAAP policy-specific tasks (`standard`
   metadata field).
3. **Jurisdiction packs** — local tax/statutory tasks with effective
   dates (`jurisdiction` metadata field).

## Environment & execution

Harbor provides isolation and reproducibility: no-network containers,
separate verifier environment, declared artifacts, recorded
trajectories. Beancount is the reference ledger engine, but the graded
contract is the accounting state (account balances/deltas), so agents
are not rewarded for Beancount trivia beyond producing a valid ledger.

## Known limits (v0.1)

- Single-currency, single-period, small-chart scenarios.
- A small Beancount subset (see [verification.md](verification.md)).
- Synthetic documents; no scanned-document OCR tasks yet.
- Deterministic tasks only; judgment-heavy treatments are deferred
  until rubric-based grading is designed.
