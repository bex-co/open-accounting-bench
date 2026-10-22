# Task families

A family is a validated, parameterized accounting scenario:
`(family, seed, generator_version)` → instruction, initial state,
source documents, policy, expectations, reference solution. Authoring
guide: [CONTRIBUTING.md](../CONTRIBUTING.md) and
[task-family-template.md](task-family-template.md).

Every task carries a five-axis taxonomy (`task.toml [metadata]`,
`manifest.json`; vocabularies in `oab.families.TAXONOMY`):

- `category`: financial-accounting / management-accounting / tax /
  audit-assurance (reviewing others' books: finding and evidencing
  errors; no family yet)
- `framework`: core / ifrs / us-gaap (jurisdiction packs add values)
- `level`: vocational / university / professional — who is expected
  to do the work ([rubric](#assigning-level))
- `format`: journal-entry / single-choice / multiple-choice / numeric /
  open-text (open-text has no deterministic grader yet)
- `skill`: remembering-understanding / application / analysis /
  evaluation — the cognitive operation the task demands, using the
  AICPA blueprint's revised-Bloom levels so crosswalks compare like
  with like

Plus `standards`, an optional list of authoritative references
(`asc:<topic>[-<subtopic>…]`, `ias:<n>`, `ifrs:<n>`, `ifric:<n>`;
pattern `oab.families.STANDARD_REF`). Standard numbers are stable
across exam editions, so they are the content anchor crosswalks pivot
through. Core tasks that rest on no single standard leave it empty.

The primary taxonomy is OAB-owned and changes only through this file.
External curricula (CPA blueprint, ACCA syllabus) are never taxonomy
values; they are linked through [crosswalks](#crosswalks-to-external-frameworks).

### Assigning `level`

Level is set by how much of the problem the task hands the solver, not
by topic: the same topic (a bank reconciliation, a prepayment) can be
vocational or professional. Score the task as delivered — instruction,
`policy.md`, and documents — on seven dimensions, each V / U / P:

| Dimension | V (vocational) | U (university) | P (professional) |
|---|---|---|---|
| Rule provision | The decisive rule or formula is stated | The principle is given; mechanics must be known | Solver must identify the governing standard, its scope and exceptions |
| Dependent steps | One or two; amounts read off a document | Three or more, with derived intermediates | Long chains across topics (measure → tax effect → presentation) |
| Problem identification | Exact transaction and action named | A goal is given; solver finds the items | Solver must notice something is wrong, often in prior work |
| Evidence quality | One clean document | Several documents, with distractors a plausible mistake uses | Incomplete or conflicting evidence; solver decides what to rely on |
| Judgement | One admissible treatment | Choose among defined methods or classify against stated criteria | Estimates, materiality, substance over form; the task fixes one defensible answer by construction |
| Scope | One transaction, period, entity | Several periods or linked accounts | Several entities, restatement, cross-period effects |
| Standards depth | Bookkeeping conventions | The main rule of one standard | Boundaries, exceptions, interacting standards |

Rule: **professional** if at least two dimensions score P and one of
them is problem identification, evidence quality, or judgement;
otherwise **university** if at least two score U or higher; otherwise
**vocational**. A `policy.md` that states the decisive rule, or an
instruction that names the problem, scores V on that dimension however
advanced the topic.

## Implemented

| Task ID | Family | Format | Framework | Skill | Standards | Trap |
|---|---|---|---|---|---|---|
| `classify-operating-expense` | transaction-classification | journal-entry | core | application | — | Capitalize a consumable |
| `bank-recon-missing-fee` | bank-reconciliation | journal-entry | core | analysis | — | Delete duplicate; ignore fee |
| `prepaid-insurance-adjustment` | adjustments-corrections | journal-entry | core | application | — | Expense all 12 months |
| `correct-misclassification` | ledger-integrity-reporting | journal-entry | core | application | — | Edit history in place |
| `mc-capitalization-treatment` | transaction-classification | multiple-choice | core | application | — | Expense-it distractor |
| `mgmt-break-even-units` | cost-volume-profit | numeric | core | application | — | Answer current volume |
| `ifrs-capitalize-borrowing-costs` | adjustments-corrections | journal-entry | ifrs | application | `ias:23` | Expense qualifying interest |

Stable seeds: 101–107 (`STABLE_SEEDS` in `src/oab/families.py`).

## Coverage matrix (category × framework)

Cell values: number of Stable tasks; `planned` cells are roadmap
placeholders tracked as issues, not directories.

| Category | core | ifrs | us-gaap | jurisdiction pack |
|---|---:|---:|---:|---|
| financial-accounting | 5 | 1 | planned | planned |
| management-accounting | 1 | planned | planned | planned |
| tax | planned | — | — | planned |
| audit-assurance | planned | — | planned | — |

Format coverage: journal-entry ×5, multiple-choice ×1, numeric ×1;
single-choice grader exists without a committed family; open-text is
deferred (needs a judge design — see [methodology.md](methodology.md)).

## Roadmap to 12–15 generators (memo §10)

| Family | Target generators | Candidate scenarios |
|---|---:|---|
| Transaction classification & journal entries | 4 | + revenue on account, refund/credit note, inter-account transfer |
| Bank reconciliation | 4 | + outstanding check (timing), deposit in transit, partial payment |
| Adjustments & corrections | 3 | + accrued wages, unearned revenue release |
| Ledger integrity & reporting | 3 | + roll-forward break, period-cutoff error |

Plus a small expert-authored adversarial set: balanced-but-wrong
entries, misleading narrations, ambiguous account names, duplicate
documents, period-boundary dates.

## Crosswalks to external frameworks

`crosswalks/<framework>-<version>.toml` maps OAB generators to items
of an external curriculum: the AICPA CPA Exam Blueprint
(`aicpa-cpa-blueprint-2026.toml`, in force through 2026, and
`aicpa-cpa-blueprint-2027.toml`; AUD/FAR/REG/BAR/ISC/TCP) and the
ACCA syllabus (`acca-syllabus-2026-27.toml`; FA/FR/SBR). Each record
follows NIST IR 8278A Rev.1 set-theory mapping — the OAB generator is
the focal element:

| Field | Meaning |
|---|---|
| `generator` | `FAMILIES` key (generators, not family labels: two generators in one family can test different things) |
| `target_id` | The framework's own numbering — AICPA `Section.Area.Group[.Topic]` (`FAR.II.A`), ACCA `Exam.<capability><section>(<outcome>)` (`FA.E1(c)`) |
| `target_item` | AICPA only: 1-based row of the representative task within `target_id`. The blueprint does not number tasks, so OAB assigns these per edition |
| `target_skill` | The framework's level for that item (AICPA skill; ACCA `K`/`S` or `1`–`3`) |
| `target_text_sha256` | `oab.crosswalk.text_digest` of the item's wording — detects drift between editions without publishing the text |
| `relationship` | `equal` / `superset-of` / `subset-of` / `intersects-with`, read "the OAB generator is … the item" |
| `rationale` | `syntactic` / `semantic` / `functional` (strictest that applies) |
| `strength` | 1–10; 10 only for `equal` (NIST 8278A Rev.1 §3.2.12 scale) |
| `status`, `mapper`, `reviewer` | `proposed` until an accounting reviewer signs; `reviewed` requires `reviewer` |
| `comment` | OAB-written summary of what the generator does and does not test |

Rules:

- One file per framework **edition**. A new blueprint or syllabus year
  is a new file; old files are never edited, so historical coverage
  claims stay reproducible. Carry mappings forward by comparing
  `target_text_sha256`.
- IDs, digests, and OAB-written summaries only — never the external
  text (AICPA and ACCA copyright; see [PROVENANCE.md](../PROVENANCE.md)).
- A crosswalk is a view of the dataset, not task metadata: editing one
  never regenerates tasks or changes scores.
- New mappings need the same accounting review as new families.

`oab crosswalk` (CI) validates every file and prints coverage; counting
rules are in [metrics.md](metrics.md#framework-coverage). As of this
edition no generator fully covers any blueprint or syllabus item —
current links are `subset-of` or `intersects-with`, all `proposed`.

## Instance contract

Every generated task must satisfy, before merge:

- Oracle solution scores `reward = 1`; untouched initial state (or a
  missing answer file) scores 0. (`oab validate`, CI.)
- At least one plausible wrong attempt fails on a non-structural
  dimension (trap test under `tests/`).
- Same seed → byte-identical task directory (digest in manifest).
- Instruction states absolute paths and the single output file
  (`/app/ledger.beancount` or `/app/answer.json`); policy in
  `/app/policy.md` removes accounting ambiguity.
