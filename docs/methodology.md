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

Each task family is a parameterized generator (Stable generators in
`src/oab/families.py`; Dynamic-first workflow generators in
`src/oab/workflow_families.py`). An instance is fully determined by
`(family, seed, generator_version)`, all recorded in `task.toml`
metadata and `tests/expected.json` (and in `tasks/manifest.json` for
Stable instances). Varying only numbers is not enough to resist
overfitting; families also vary vendors, dates, document structure, and
—which accounts/traps are in play — as families grow.

Tracks: **Stable** (frozen seeds, committed), **Dynamic** (fresh seeds
at run time), **Holdout** (unpublished families/seeds for
generalization; see [governance.md](governance.md)).

### Professional workflow lifecycle

Professional workflow generators start Dynamic-first. Before a
calibration panel, the public task contract must disclose or make
derivable every graded disposition code, account choice, sign
convention, and evidence precedence rule; every material evidence item
in scope must map to an intended determination. Hidden exact strings
and evidence that looks actionable but is absent from expectations
are generator defects, not difficulty.

The lifecycle is: oracle/no-op, omission and wrong-disposition
mutants, and equivalent split/combined-entry tests; a preregistered
multi-tier, multi-seed, repeated-attempt panel; failure adjudication
against submitted ledgers and schedules; check/cluster discrimination
analysis; and an explicit promote, tune-and-recalibrate, or reject
verdict. Tuning may change issue activation, evidence conflict,
policy sparsity, cutoff pressure, downstream dependencies, or check
grouping, followed by oracle/mutant/seed sweeps and a confirmation
slice. No Stable freeze follows from length, bulk, ambiguity, or a
design label alone; a freeze is a separate versioned release step.

**Calibration target (from 2026-11-07).** A panel's preregistered
target band is stated on **pass^k** of full-completion reward
(`oab report --k`, [metrics.md](metrics.md#reliability-passk-and-passk)),
not on mean rubric completion, which stays a diagnostic: comparable
close and audit benchmarks drop sharply from single-run to every-run
success, and the 0.8.0 strong tiers sat at 97–99% rubric while
missing full completion. Each panel fixes one per-trial budget tier
(turn, token, or cost limit), applies it to every model tier, and
records it with the panel, because budget alone can move scores by
tens of points; panels at different budgets are not compared.

## Coverage layers

Scores are reported per capability and regulatory context, never as one
opaque global number:

1. **Accounting Core** — double-entry, classification, reconciliation,
   ledger integrity (`framework = "core"`).
2. **Standards** — IFRS / US GAAP policy-specific tasks (`framework`
   metadata field).
3. **Jurisdiction packs** — local tax/statutory tasks with effective
   dates (new `framework` values, added to the taxonomy first).

Every task is also tagged by `category` (financial/management/tax/
audit-assurance), `level` (vocational/university/professional),
`format` (journal-entry, choice, numeric, workflow, open-text), `skill`
(revised-Bloom: remembering-understanding … evaluation), and the
`standards` it rests on; see [task-families.md](task-families.md) for
the coverage matrix.

Professional curricula are linked, not adopted: OAB's taxonomy stays
framework-neutral (the CPA blueprint is US-only and re-edited yearly),
and typed crosswalks to the AICPA blueprint and ACCA syllabus support
claims like "N of 113 FAR representative tasks covered" — the same
separation HELM, MedHELM, and LegalBench keep between their own
taxonomy and external exam outlines.

## Environment & execution

Harbor provides isolation and reproducibility: no-network containers,
separate verifier environment, declared artifacts, recorded
trajectories. Beancount is the reference ledger engine, but the graded
contract is the accounting state (account balances/deltas), so agents
are not rewarded for Beancount trivia beyond producing a valid ledger.

## Relation to WU AccountingBench

[AccountingBench](https://www.boardservice.center/research/methodology.html)
(WU Vienna; Kaburek et al., RWK 4/2026) evaluates LLMs on 520 curated
examination tasks (Financial/Management/Tax; single/multiple choice,
numeric, journal entries, open text), three runs per question,
penalized choice scoring, an LLM judge for entries and open text, and
stratified reporting with cost and confidence analysis. OAB replicates
that measurement structure — five-axis taxonomy (category, framework,
level, format, skill), multi-attempt aggregation (`oab report`, majority
vote for choice formats, plus pass@k and pass^k reliability), interpretation bands, cost and confidence
reporting — with four deliberate deviations:

1. **Generated instances, not curated exam items**: seed-parameterized
   families with rule-derived oracles avoid copyright, contamination,
   and static-snapshot limits (Stable seeds stay comparable; Dynamic
   seeds resist overfitting).
2. **Deterministic journal-entry grading, no LLM judge**: entries are
   graded by resulting ledger state in five layers, so equivalent
   entries pass and balanced-but-wrong entries fail — the judge
   reliability caveat WU lists does not apply to this format.
3. **Unparseable answers stay in the denominator** (`parse_failure`
   is reported separately) instead of being excluded from totals.
4. **Open-text is deferred**: it needs a judge design (verifier
   network/secrets policy plus a human-agreement study) and will be
   reported as a separate track when it lands.

WU's central empirical lesson also shapes our roadmap: globally
documented standards (their IFRS items score 96–100%) saturate
quickly, while jurisdiction-specific rules discriminate. Core
bookkeeping here is therefore a sanity gate; discriminative weight
will come from standards/jurisdiction packs and multi-step workflows.

## Known limits (v0.1)

- Stable scenarios remain mostly single-currency, single-period, and
  small-chart. The workflow contract supports multi-period,
  multi-artifact scenarios, but professional workflow families are
  Dynamic-first until difficulty calibration justifies a Stable freeze.
- A small Beancount subset (see [verification.md](verification.md)).
- Synthetic documents; no scanned-document OCR tasks yet.
- Deterministic tasks only. Professional judgement is admitted only
  where scenario facts and policies fix one defensible state that typed
  workflow checks can grade; open-text judgement remains deferred.
