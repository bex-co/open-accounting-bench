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

Reaching P under deterministic grading: every task ships a `policy.md`
so the oracle is unique, which pushes rule provision toward V. A task
can still score P there when the policy cites the governing standard
and supplies the facts and thresholds that standard needs, but not the
conclusion rule for the case — the oracle is then the standard applied
to seeded facts. A policy that states the decisive rule cannot score P
on rule provision.

The two-dimension thresholds make labels sensitive to a single score.
Record all seven scores in the family PR and mark the level
**borderline** when flipping any one dimension would change it.

**Score at the strict reading** (adopted 2026-10-25, applied to every
task): a dimension is U or P only if the task as delivered actually
demands it. Dependent steps count only when an intermediate value must
be derived — amounts readable off a document, or a target balance the
instruction states, do not count. A document counts as a distractor
only if a plausible mistake uses it; combining several clean documents
is not enough. Scope is U only for genuinely multi-period work or
several accounts whose movement the solver must work out. When in
doubt, score V.

Current Stable tasks (R = rule provision, S = dependent steps,
I = problem identification, E = evidence, J = judgement, C = scope,
D = standards depth):

| Task | R | S | I | E | J | C | D | Level |
|---|---|---|---|---|---|---|---|---|
| `classify-operating-expense` | V | V | V | V | V | V | V | vocational |
| `bank-recon-missing-fee` | V | V | V | V | V | V | V | vocational |
| `prepaid-insurance-adjustment` | V | V | V | V | V | U | V | vocational |
| `correct-misclassification` | V | V | V | V | V | V | V | vocational |
| `mc-capitalization-treatment` | V | V | V | U | V | V | V | vocational |
| `mgmt-break-even-units` | V | V | V | V | V | V | V | vocational |
| `ifrs-capitalize-borrowing-costs` | V | V | V | V | V | V | U | vocational |
| `ppe-disposal` | V | U | V | V | V | V | V | vocational |
| `inventory-costing-nrv` | V | U | V | V | V | V | V | vocational |
| `receivable-allowance-trueup` | V | U | V | V | V | U | V | university (borderline) |
| `accrual-deferral-reversal` | V | U | V | V | V | U | V | university (borderline) |
| `payables-statement-recon` | V | V | U | U | V | V | V | university (borderline) |
| `suspense-clearance` | V | V | U | U | V | V | V | university (borderline) |
| `loan-effective-interest` | V | U | V | V | V | V | U | university (borderline) |
| `revenue-bundle-allocation` | V | U | V | U | V | V | U | university |
| `perpetual-sale-with-cost` | V | U | V | V | V | V | V | vocational |
| `sales-return-restock` | V | U | V | V | V | V | V | vocational |
| `supplies-adjustment` | V | V | V | V | V | V | V | vocational |
| `accrued-wages-adjustment` | V | V | V | V | V | V | V | vocational |
| `straight-line-depreciation` | V | U | V | V | V | V | V | vocational |
| `note-interest-accrual` | V | U | V | V | V | V | V | vocational |
| `payroll-withholdings` | V | U | V | V | V | V | V | vocational |
| `bond-discount-amortization` | V | U | V | V | V | V | U | vocational |
| `cvp-target-profit-units` | V | U | V | V | V | V | V | vocational |
| `process-costing-equivalent-units` | V | U | V | V | V | V | V | vocational |
| `operating-cash-flow-indirect` | V | U | V | V | V | V | U | vocational |
| `inventory-days-on-hand` | V | U | V | V | V | V | V | vocational |
| `equity-issue-above-par` | V | U | V | V | V | V | V | vocational |
| `cash-dividend-declaration` | V | V | V | V | V | V | V | vocational |
| `treasury-stock-repurchase` | V | V | V | V | V | V | V | vocational |
| `closing-entries-income-summary` | V | U | V | V | V | V | V | vocational |
| `job-overhead-applied` | V | U | V | U | V | V | V | vocational |
| `note-dishonored` | V | U | V | V | V | U | V | vocational |
| `lifo-ending-inventory` | V | U | V | V | V | V | V | vocational |
| `materials-price-variance` | V | U | V | V | V | V | V | vocational |
| `npv-project-evaluation` | V | U | V | V | V | V | V | vocational |
| `make-or-buy-advantage` | V | U | V | U | V | V | V | vocational |
| `absorption-variable-income-difference` | V | U | V | V | V | V | V | vocational |
| `current-ratio` | V | U | V | V | V | V | V | vocational |
| `bank-adjusted-balance` | V | U | V | U | V | V | V | vocational |
| `capitalized-cost-bundle` | V | U | V | U | V | V | V | vocational |
| `employer-payroll-taxes` | V | U | V | V | V | V | V | vocational |
| `current-portion-reclass` | V | U | V | V | V | V | V | vocational |
| `periodic-purchase-with-freight` | V | V | V | V | V | V | V | vocational |
| `bad-debt-percent-of-sales` | V | U | V | V | V | U | V | vocational |
| `cash-discount-receipt` | V | U | V | V | V | V | V | vocational |
| `abc-overhead-assigned` | V | U | V | U | V | V | V | vocational |
| `high-low-variable-cost` | V | U | V | V | V | V | V | vocational |
| `cash-collections-budget` | V | U | V | V | V | V | V | vocational |
| `gross-profit-from-trial-balance` | V | U | V | U | V | V | V | vocational |
| `ending-retained-earnings` | V | U | V | U | V | V | V | vocational |
| `present-value-lump-sum` | V | U | V | V | V | V | V | vocational |
| `flexible-budget-total-cost` | V | U | V | V | V | V | V | vocational |

No task reaches professional yet; that needs P on problem
identification, evidence, or judgement (see above).

`level` and `skill` are independent axes: `skill` is the cognitive
operation the task demands (e.g. analysis), `level` is how much of the
problem the task hands over. An analysis task can be vocational.

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
| `receivable-allowance-trueup` | receivables | journal-entry | core | application | — | Expense the full required allowance |
| `accrual-deferral-reversal` | accruals-deferrals | journal-entry | core | application | — | Skip the accrual reversal |
| `payables-statement-recon` | payables-reconciliation | journal-entry | core | analysis | — | Book timing items as errors |
| `ppe-disposal` | fixed-assets | journal-entry | core | application | — | Skip disposal-month depreciation |
| `inventory-costing-nrv` | inventory | journal-entry | core | application | — | Average cost; no NRV write-down |
| `revenue-bundle-allocation` | revenue-recognition | journal-entry | core | application | `asc:606`, `ifrs:15` | Allocate on invoice lines |
| `suspense-clearance` | ledger-integrity-reporting | journal-entry | core | analysis | — | Clear suspense to one account |
| `loan-effective-interest` | borrowings | journal-entry | core | application | `asc:835-30`, `ifrs:9` | Coupon-rate interest |
| `perpetual-sale-with-cost` | inventory | journal-entry | core | application | — | Revenue only, no COGS |
| `sales-return-restock` | inventory | journal-entry | core | application | — | Restock at selling price |
| `supplies-adjustment` | adjustments-corrections | journal-entry | core | application | — | Expense the counted remainder |
| `accrued-wages-adjustment` | accruals-deferrals | journal-entry | core | application | — | Accrue the full week |
| `straight-line-depreciation` | fixed-assets | journal-entry | core | application | — | Ignore residual value |
| `note-interest-accrual` | receivables | journal-entry | core | application | — | Accrue the full 90 days |
| `payroll-withholdings` | payroll | journal-entry | core | application | — | Expense net pay |
| `bond-discount-amortization` | borrowings | journal-entry | core | application | `asc:835-30`, `ifrs:9` | Coupon-only interest |
| `cvp-target-profit-units` | cost-volume-profit | numeric | core | application | — | Answer break-even units |
| `process-costing-equivalent-units` | process-costing | numeric | core | application | — | FIFO equivalent units |
| `operating-cash-flow-indirect` | cash-flow-statement | numeric | core | application | `asc:230`, `ias:7` | Add back the disposal gain |
| `inventory-days-on-hand` | financial-analysis | numeric | core | application | — | Use ending inventory |
| `equity-issue-above-par` | equity | journal-entry | core | application | — | Credit full proceeds to stock |
| `cash-dividend-declaration` | equity | journal-entry | core | application | — | Pay on declaration date |
| `treasury-stock-repurchase` | equity | journal-entry | core | application | — | Retire at repurchase cost |
| `closing-entries-income-summary` | ledger-integrity-reporting | journal-entry | core | application | — | Close revenue only |
| `job-overhead-applied` | job-order-costing | journal-entry | core | application | — | Apply actual overhead |
| `note-dishonored` | receivables | journal-entry | core | application | — | Principal only to AR |
| `lifo-ending-inventory` | inventory | numeric | core | application | — | FIFO ending value |
| `materials-price-variance` | standard-costing | numeric | core | application | — | Use quantity used |
| `npv-project-evaluation` | capital-budgeting | numeric | core | application | — | Undiscounted inflows |
| `make-or-buy-advantage` | relevant-costing | numeric | core | application | — | Count unavoidable fixed cost |
| `absorption-variable-income-difference` | absorption-variable-costing | numeric | core | application | — | Rate x units sold |
| `current-ratio` | financial-analysis | numeric | core | application | — | Quick ratio |
| `bank-adjusted-balance` | bank-reconciliation | numeric | core | application | — | Unadjusted book balance |
| `capitalized-cost-bundle` | fixed-assets | journal-entry | core | application | — | Capitalize the whole invoice |
| `employer-payroll-taxes` | payroll | journal-entry | core | application | — | Deduct from employee wages |
| `current-portion-reclass` | borrowings | journal-entry | core | application | — | Reclassify the whole balance |
| `periodic-purchase-with-freight` | inventory | journal-entry | core | application | — | Freight buried in purchases |
| `bad-debt-percent-of-sales` | receivables | journal-entry | core | application | — | Aging-style true-up |
| `cash-discount-receipt` | receivables | journal-entry | core | application | — | Discount left in receivables |
| `abc-overhead-assigned` | activity-based-costing | numeric | core | application | — | Plantwide DLH rate |
| `high-low-variable-cost` | cost-behavior | numeric | core | application | — | Average cost at high volume |
| `cash-collections-budget` | budgeting | numeric | core | application | — | Current month only |
| `gross-profit-from-trial-balance` | financial-reporting | numeric | core | application | — | Gross sales minus COGS |
| `ending-retained-earnings` | equity | numeric | core | application | — | Add share-issue proceeds |
| `present-value-lump-sum` | time-value-of-money | numeric | core | application | — | Undiscounted face amount |
| `flexible-budget-total-cost` | budgeting | numeric | core | application | — | Static-budget volume |

Stable seeds: 101–153 (`STABLE_SEEDS` in `src/oab/families.py`).

## Coverage matrix (category × framework)

Cell values: number of Stable tasks; `planned` cells are roadmap
placeholders tracked as issues, not directories.

| Category | core | ifrs | us-gaap | jurisdiction pack |
|---|---:|---:|---:|---|
| financial-accounting | 40 | 1 | planned | planned |
| management-accounting | 12 | planned | planned | planned |
| tax | planned | — | — | planned |
| audit-assurance | planned | — | planned | — |

Format coverage: journal-entry ×33, multiple-choice ×1, numeric ×19;
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

`[[out_of_scope]]` records (`target_id`, `target_item`, OAB-written
`reason`, `status`, `reviewer`) mark items OAB judges not agent-gradable;
they are allowed only in sections listed in `framework.triaged` and
never on an item a mapping covers. They define the gradable
denominator in [metrics.md](metrics.md#framework-coverage).

Rules:

- One file per framework **edition**. A new blueprint or syllabus year
  is a new file; old files are never edited, so historical coverage
  claims stay reproducible. Carry mappings forward by comparing
  `target_text_sha256`.
- IDs, digests, and OAB-written summaries only — never the external
  text (AICPA and ACCA copyright; see [PROVENANCE.md](../PROVENANCE.md)).
- A crosswalk is a view of the dataset, not task metadata: editing one
  never regenerates tasks or changes scores.
- New mappings start `proposed` and are listed in [TO_REVIEW.md](../TO_REVIEW.md); they count toward cited coverage only once reviewed.

`oab crosswalk` (CI) validates every file and prints coverage; counting
rules are in [metrics.md](metrics.md#framework-coverage). As of
2026-10-25 (all links reviewed): ACCA FA has 3 covered items of 85
gradable (FA.D3(b), FA.D8(e), FA.F3(d)); FAR and BAR have none
covered — their links are `subset-of` or `intersects-with`.

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
