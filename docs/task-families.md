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
| Judgement | One admissible treatment; a single stated fact triggers the classification | Choose among defined methods, weigh indicators that point different ways, or apply a qualitative threshold the policy does not settle | Estimates, materiality, substance over form; the task fixes one defensible answer by construction |
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
Record all seven scores in the family PR. Mark a level
**borderline** only when a university label rests on the minimum
two U-or-higher scores, so removing one would drop it to
vocational; do not flag vocational tasks merely because one more
U would raise them.

**Score at the strict reading** (adopted 2026-10-25, applied to every
task): a dimension is U or P only if the task as delivered actually
demands it. Dependent steps count only when an intermediate value must
be derived — amounts readable off a document, or a target balance the
instruction states, do not count. A document counts as a distractor
only if a plausible mistake uses it; combining several clean documents
is not enough. Judgement is V when one stated fact mechanically
triggers a classification; it is U only when the solver must weigh
indicators pointing different ways or apply a qualitative threshold
(such as "substantially all" or "significant") that the policy does
not settle. Scope is U only for genuinely multi-period work or
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
| `perpetual-sale-with-cost` | V | V | V | V | V | V | V | vocational |
| `sales-return-restock` | V | V | V | V | V | V | V | vocational |
| `supplies-adjustment` | V | V | V | V | V | V | V | vocational |
| `accrued-wages-adjustment` | V | V | V | V | V | V | V | vocational |
| `straight-line-depreciation` | V | V | V | V | V | V | V | vocational |
| `note-interest-accrual` | V | V | V | V | V | V | V | vocational |
| `payroll-withholdings` | V | V | V | V | V | V | V | vocational |
| `bond-discount-amortization` | V | U | V | V | V | V | U | university (borderline) |
| `cvp-target-profit-units` | V | V | V | V | V | V | V | vocational |
| `process-costing-equivalent-units` | V | U | V | V | V | V | V | vocational |
| `operating-cash-flow-indirect` | V | V | V | V | V | V | U | vocational |
| `inventory-days-on-hand` | V | V | V | V | V | V | V | vocational |
| `equity-issue-above-par` | V | V | V | V | V | V | V | vocational |
| `cash-dividend-declaration` | V | V | V | V | V | V | V | vocational |
| `treasury-stock-repurchase` | V | V | V | V | V | V | U | vocational |
| `closing-entries-income-summary` | V | V | V | V | V | V | V | vocational |
| `job-overhead-applied` | V | V | V | U | V | V | V | vocational |
| `note-dishonored` | V | V | V | V | V | V | V | vocational |
| `lifo-ending-inventory` | V | U | V | V | V | V | V | vocational |
| `materials-price-variance` | V | V | V | V | V | V | V | vocational |
| `npv-project-evaluation` | V | V | V | V | V | V | V | vocational |
| `make-or-buy-advantage` | V | U | V | U | V | V | V | university (borderline) |
| `absorption-variable-income-difference` | V | V | V | V | V | V | V | vocational |
| `current-ratio` | V | V | V | V | V | V | V | vocational |
| `bank-adjusted-balance` | V | V | V | U | V | V | V | vocational |
| `capitalized-cost-bundle` | V | V | V | U | V | V | V | vocational |
| `employer-payroll-taxes` | V | V | V | V | V | V | V | vocational |
| `current-portion-reclass` | V | V | V | V | V | V | V | vocational |
| `periodic-purchase-with-freight` | V | V | V | V | V | V | V | vocational |
| `bad-debt-percent-of-sales` | V | V | V | U | V | V | V | vocational |
| `cash-discount-receipt` | V | V | V | V | V | V | V | vocational |
| `abc-overhead-assigned` | V | V | V | U | V | V | V | vocational |
| `high-low-variable-cost` | V | V | V | V | V | V | V | vocational |
| `cash-collections-budget` | V | V | V | V | V | V | V | vocational |
| `gross-profit-from-trial-balance` | V | U | V | U | V | V | V | university (borderline) |
| `ending-retained-earnings` | V | V | V | U | V | V | V | vocational |
| `present-value-lump-sum` | V | V | V | V | V | V | V | vocational |
| `flexible-budget-total-cost` | V | V | V | V | V | V | V | vocational |
| `narrative-multi-transactions` | V | V | V | V | V | V | V | vocational |
| `units-of-production-depreciation` | V | V | V | V | V | V | V | vocational |
| `warranty-provision-and-claims` | V | V | V | V | V | U | V | vocational |
| `sales-tax-collection` | V | V | V | V | V | V | V | vocational |
| `petty-cash-replenishment` | V | V | V | U | V | V | V | vocational |
| `small-stock-dividend` | V | U | V | V | V | V | U | university (borderline) |
| `accounting-equation-missing-equity` | V | V | V | V | V | V | V | vocational |
| `current-income-tax-expense` | V | V | V | V | V | V | U | vocational |
| `lease-liability-present-value` | V | V | V | V | V | V | U | vocational |
| `equity-method-carrying-amount` | V | U | V | V | V | V | U | university (borderline) |
| `bond-issue-price` | V | U | V | V | V | V | U | university (borderline) |
| `partnership-income-allocation` | V | U | V | V | V | V | V | vocational |
| `mc-normal-balances` | V | V | V | V | V | V | V | vocational |
| `sc-special-journal-routing` | V | V | V | V | V | V | V | vocational |
| `short-term-note-payment` | V | V | V | V | V | V | V | vocational |
| `credit-card-sale-fee` | V | V | V | V | V | V | V | vocational |
| `patent-amortization` | V | V | V | V | V | V | U | vocational |
| `loss-contingency-accrual` | V | V | V | U | U | V | U | university |
| `bond-issued-at-premium` | V | V | V | V | V | V | U | vocational |
| `closing-drawing-account` | V | V | V | V | V | V | V | vocational |
| `trading-securities-fair-value` | V | V | V | V | V | V | U | vocational |
| `materials-quantity-variance` | V | V | V | V | V | V | V | vocational |
| `cost-of-goods-manufactured` | V | V | V | V | V | V | V | vocational |
| `payback-period-years` | V | V | V | U | V | V | V | vocational |
| `multiproduct-breakeven-units` | V | U | V | V | V | V | V | vocational |
| `total-current-liabilities` | V | V | V | U | V | V | V | vocational |
| `sc-cash-flow-classification` | V | V | V | V | V | V | U | vocational |
| `inventory-shrinkage-adjustment` | V | V | V | V | V | V | V | vocational |
| `purchase-return-perpetual` | V | V | V | V | V | V | V | vocational |
| `overhead-variance-disposition` | V | V | V | V | V | V | V | vocational |
| `unearned-revenue-release` | V | V | V | V | V | V | V | vocational |
| `bond-early-retirement` | V | V | V | V | V | V | U | vocational |
| `fvoci-fair-value-adjustment` | V | V | V | V | V | V | U | vocational |
| `basket-purchase-allocation` | V | V | V | U | V | V | V | vocational |
| `labor-efficiency-variance` | V | V | V | V | V | V | V | vocational |
| `diluted-eps` | V | U | V | V | V | V | U | university (borderline) |
| `asset-turnover-ratio` | V | V | V | V | V | V | V | vocational |
| `breakeven-sales-dollars` | V | V | V | V | V | V | V | vocational |
| `direct-materials-used` | V | V | V | V | V | V | V | vocational |
| `sc-subsequent-event-classification` | V | V | V | V | V | V | U | vocational |
| `treasury-stock-reissuance` | V | U | V | V | V | V | U | university (borderline) |
| `lease-initial-recognition` | V | V | V | V | V | V | U | vocational |
| `fx-payable-remeasurement` | V | V | V | V | V | V | U | vocational |
| `development-cost-capitalization` | V | V | V | V | U | V | U | university (borderline) |
| `inventory-error-correction` | V | V | V | V | V | U | U | university (borderline) |
| `long-lived-asset-impairment` | V | V | V | U | V | V | U | university (borderline) |
| `production-budget-units` | V | V | V | V | V | V | V | vocational |
| `predetermined-overhead-applied` | V | V | V | U | V | V | V | vocational |
| `interim-income-tax-expense` | V | U | V | V | V | U | U | university |
| `segment-margin` | V | V | V | U | V | V | V | vocational |
| `residual-income` | V | V | V | V | V | V | V | vocational |
| `cash-collected-from-customers` | V | V | V | V | V | V | U | vocational |
| `free-cash-flow` | V | V | V | V | V | V | U | vocational |
| `sc-transaction-statement-impact` | V | V | V | V | V | V | V | vocational |
| `business-combination-acquisition` | V | U | V | U | V | V | U | university |
| `consolidation-intercompany-elimination` | V | U | V | V | V | U | U | university |
| `held-for-sale-measurement` | V | U | V | V | V | V | U | university (borderline) |
| `share-based-compensation-monthly` | V | V | V | V | V | V | U | vocational |
| `asset-revaluation-surplus` | V | V | V | V | V | V | U | vocational |
| `written-off-receivable-recovery` | V | V | V | V | V | V | V | vocational |
| `nfp-conditional-vs-unconditional` | V | V | V | V | U | V | U | university (borderline) |
| `adjusted-receivable-balance` | V | V | V | V | V | V | V | vocational |
| `ppe-additions-inferred` | V | V | V | V | V | V | V | vocational |
| `fixed-overhead-volume-variance` | V | V | V | U | V | V | V | vocational |
| `cumulative-preferred-dividend` | V | U | V | V | V | V | V | vocational |
| `weighted-average-cost-of-capital` | V | U | V | V | V | V | V | vocational |
| `standard-cost-per-unit` | V | U | V | U | V | V | V | university (borderline) |
| `sc-job-vs-process-costing` | V | V | V | V | V | V | V | vocational |
| `government-grant-release` | V | V | V | V | V | V | U | vocational |
| `investment-property-fair-value` | V | V | V | V | V | V | U | vocational |
| `goodwill-impairment` | V | V | V | V | V | V | U | vocational |
| `fx-translation-adjustment` | V | V | V | V | V | V | U | vocational |
| `sale-and-leaseback-entry` | V | V | V | V | V | V | U | vocational |
| `debt-security-credit-loss` | V | V | V | U | V | V | U | university (borderline) |
| `trial-balance-debit-total` | V | V | V | U | V | V | V | vocational |
| `post-closing-debit-total` | V | V | V | U | V | V | V | vocational |
| `adjusted-wage-expense` | V | V | V | V | V | V | V | vocational |
| `inventory-method-profit-difference` | V | U | V | V | V | V | V | vocational |
| `minimum-transfer-price` | V | V | V | V | V | V | V | vocational |
| `debt-modification-percent-change` | V | V | V | U | V | V | U | university (borderline) |
| `mc-temporary-accounts` | V | V | V | V | V | V | V | vocational |
| `sc-fair-value-hierarchy` | V | V | V | V | V | V | U | vocational |
| `deferred-tax-asset-warranty` | V | U | V | V | V | V | U | university (borderline) |
| `consignment-sale-recognition` | V | U | V | V | V | V | U | university (borderline) |
| `natural-resource-depletion` | V | U | V | V | V | V | V | vocational |
| `internal-use-software-costs` | V | V | V | V | U | V | U | university (borderline) |
| `lessor-sales-type-lease` | V | V | V | V | V | V | U | vocational |
| `factoring-secured-borrowing` | V | V | V | V | V | V | U | vocational |
| `pension-expense-and-contribution` | V | U | V | V | V | V | U | university (borderline) |
| `irr-from-annuity-factor` | V | V | V | V | V | V | V | vocational |
| `c-corporation-taxable-income` | V | V | V | V | U | V | V | vocational |
| `s-corporation-aaa-ending` | V | V | V | V | U | V | V | vocational |
| `partnership-outside-basis` | V | V | V | V | U | V | V | vocational |
| `performance-materiality` | V | V | V | V | V | V | V | vocational |
| `cash-and-equivalents-total` | V | V | V | U | V | V | V | vocational |
| `sc-investment-classification` | V | V | V | V | V | V | U | vocational |
| `mc-reportable-segments` | V | V | V | V | V | V | U | vocational |
| `cash-flow-hedge-fair-value` | V | V | V | V | V | V | U | vocational |
| `provision-rollforward-topup` | V | U | V | V | V | U | U | university |
| `partnership-admission-bonus` | V | U | V | V | V | U | V | university (borderline) |
| `governmental-encumbrance-entry` | V | V | V | V | V | V | V | vocational |
| `contract-acquisition-cost` | V | V | V | V | V | V | U | vocational |
| `aro-accretion` | V | V | V | V | V | V | U | vocational |
| `tax-return-crossfoot-difference` | V | V | V | U | V | V | V | vocational |
| `tax-cost-recovery-deduction` | V | V | V | V | V | V | V | vocational |
| `passthrough-loss-limitation` | V | V | V | V | V | V | V | vocational |
| `partnership-distribution-gain` | V | V | V | V | V | V | V | vocational |
| `sample-misstatement-projection` | V | V | V | V | V | V | V | vocational |
| `capm-expected-return` | V | V | V | V | V | V | V | vocational |
| `duplicate-payments-total` | V | V | U | U | V | V | V | university (borderline) |
| `sc-audit-procedure-selection` | V | V | V | V | V | V | V | vocational |
| `sc-control-design-gap` | V | V | V | V | V | V | V | vocational |
| `inventory-error-income-effect` | V | V | V | V | V | U | V | vocational |
| `inventory-lcm-value` | V | U | V | V | V | V | U | university (borderline) |
| `sc-fraud-triangle-classification` | V | V | V | V | V | V | V | vocational |
| `expected-profit-choice` | V | U | V | V | V | V | V | vocational |
| `receivables-control-balance` | V | V | V | U | V | V | V | vocational |
| `partnership-formation-capital` | V | V | V | U | V | V | V | vocational |
| `partnership-liquidation-distribution` | V | U | V | V | V | V | V | vocational |
| `partnership-retirement-settlement` | V | U | V | V | V | V | V | vocational |
| `biological-asset-fair-value` | V | V | V | V | V | V | U | vocational |
| `sc-debt-equity-classification` | V | V | V | V | V | V | U | vocational |
| `sc-control-assessment` | V | V | V | V | U | V | U | university (borderline) |
| `profit-from-capital-movements` | V | V | V | V | V | V | V | vocational |
| `sales-from-markup-reconstruction` | V | U | V | V | V | V | V | vocational |
| `inventory-cost-inclusions` | V | V | V | U | V | V | U | university (borderline) |
| `disposal-of-subsidiary-gain` | V | V | V | V | V | V | U | vocational |
| `step-acquisition-remeasurement-gain` | V | V | V | V | V | V | U | vocational |
| `weighted-average-ending-inventory` | V | U | V | V | V | V | U | university (borderline) |
| `ledger-account-balance-carried-down` | V | V | V | V | V | V | V | vocational |
| `allowance-movement-expense` | V | U | V | V | V | V | V | vocational |
| `receivables-payables-contra` | V | V | V | V | V | V | V | vocational |
| `sc-measurement-basis` | V | V | V | V | V | V | V | vocational |
| `agent-commission-revenue` | V | V | V | V | V | V | U | vocational |
| `gift-card-breakage-revenue` | V | V | V | V | V | V | U | vocational |
| `adjusted-profit-from-draft` | V | V | V | V | V | V | V | vocational |
| `payables-control-balance` | V | V | V | U | V | V | V | vocational |
| `restructuring-provision-amount` | V | V | V | U | V | V | U | university (borderline) |
| `sc-suspense-account-cause` | V | V | V | V | V | V | V | vocational |
| `sc-business-vs-asset-acquisition` | V | V | V | V | V | V | U | vocational |
| `contract-modification-revenue` | V | V | V | V | V | V | U | vocational |
| `sc-derecognition-assessment` | V | V | V | V | U | V | U | university (borderline) |
| `lease-component-allocation` | V | V | V | V | V | V | U | vocational |
| `sc-offsetting-assessment` | V | V | V | V | V | V | U | vocational |
| `sc-related-party-identification` | V | V | V | V | V | V | U | vocational |
| `separate-statements-investment` | V | V | V | V | V | V | U | vocational |
| `sc-backup-recovery-selection` | V | V | V | V | V | V | V | vocational |
| `change-control-deviation-count` | V | V | V | U | V | V | V | vocational |
| `sc-database-integrity-gap` | V | V | V | V | V | V | V | vocational |
| `incident-response-deviation-count` | V | V | V | U | V | V | V | vocational |
| `sc-soc-opinion-modification` | V | V | V | V | V | V | V | vocational |
| `sql-join-excluded-count` | V | V | V | U | V | V | V | vocational |
| `sc-system-description-gap` | V | V | V | V | V | V | V | vocational |
| `budget-vs-actual-net-variance` | V | V | V | V | V | V | V | vocational |
| `cash-to-accrual-profit` | V | V | V | V | V | V | V | vocational |
| `debt-covenant-ratio` | V | V | V | U | V | V | V | vocational |
| `exit-obligation-january-amount` | V | V | V | V | V | V | U | vocational |
| `sc-governmental-fund-assignment` | V | V | V | V | V | V | V | vocational |
| `htm-premium-amortization` | V | U | V | V | V | V | U | university (borderline) |
| `nfp-program-expense-allocation` | V | V | V | U | V | V | V | vocational |
| `nfp-operating-cash-flow` | V | U | V | V | V | V | U | university (borderline) |
| `nfp-restricted-net-assets` | V | V | V | U | V | V | V | vocational |
| `notes-figures-difference` | V | V | V | U | V | V | V | vocational |
| `tax-basis-net-income` | V | V | V | U | V | V | V | vocational |
| `benefit-plan-net-assets` | V | V | V | U | V | V | V | vocational |
| `sc-component-unit-presentation` | V | V | V | V | V | V | V | vocational |
| `sc-fund-balance-classification` | V | V | V | V | V | V | V | vocational |
| `govt-conversion-net-position` | V | V | V | V | V | V | V | vocational |
| `govt-capitalized-costs-total` | V | V | V | U | V | V | V | vocational |
| `govt-expenditures-december` | V | V | V | U | V | V | V | vocational |
| `govt-long-term-debt-total` | V | V | V | U | V | V | V | vocational |
| `govt-net-investment-capital` | V | V | V | U | V | V | V | vocational |
| `sc-interfund-activity-type` | V | V | V | V | V | V | V | vocational |
| `nonexchange-revenue-recognized` | V | V | V | V | V | V | V | vocational |
| `adjusted-ebitda-computation` | V | V | V | U | V | V | V | vocational |
| `sc-option-value-sensitivity` | V | V | V | V | V | V | V | vocational |
| `percent-of-sales-afn` | V | U | V | U | V | V | V | university (borderline) |
| `sales-mix-variance` | V | U | V | V | V | V | V | vocational |
| `state-apportionment-income` | V | U | V | V | V | V | V | vocational |
| `tax-penalty-combined` | V | V | V | V | V | V | V | vocational |
| `capital-loss-carryforward` | V | U | V | V | V | V | V | vocational |
| `sc-capital-gain-classification` | V | V | V | V | V | V | V | vocational |
| `disallowed-loss-amount` | V | V | V | U | V | V | V | vocational |
| `sc-s-corp-eligibility` | V | V | V | V | V | V | V | vocational |
| `individual-tax-with-niit` | V | V | V | U | V | V | V | vocational |
| `sc-tax-authority-disclosure` | V | V | V | V | V | V | V | vocational |
| `sc-filing-status` | V | V | V | V | V | V | V | vocational |
| `individual-gross-income-total` | V | V | V | V | U | V | V | vocational |
| `agi-above-line-adjustments` | V | V | V | V | U | V | V | vocational |
| `sc-tax-practice-ethics` | V | V | V | V | V | V | V | vocational |
| `qbi-deduction-amount` | V | V | V | U | V | V | V | vocational |
| `passthrough-ordinary-income` | V | V | V | U | V | V | V | vocational |
| `owner-ordinary-from-k1` | V | V | V | U | V | V | V | vocational |
| `section1231-capital-amount` | V | U | V | V | V | V | V | vocational |
| `depreciation-recapture-ordinary` | V | V | V | V | V | V | V | vocational |
| `estimated-tax-installment` | V | V | V | V | V | V | V | vocational |
| `installment-sale-gain-year` | V | V | V | U | V | V | V | vocational |
| `likekind-exchange-gain` | V | V | V | V | V | V | V | vocational |
| `below-market-imputed-interest` | V | V | V | V | V | V | V | vocational |
| `tax-equivalent-yield` | V | V | V | V | V | V | V | vocational |
| `taxable-gifts-total` | V | V | V | U | V | V | V | vocational |
| `charitable-noncash-deduction` | V | V | V | V | U | V | V | vocational |
| `corporate-distribution-dividend` | V | V | V | V | V | V | V | vocational |
| `liquidation-shareholder-gain` | V | V | V | U | V | V | V | vocational |
| `corporate-formation-gain` | V | V | V | V | V | V | V | vocational |
| `partnership-contribution-gain` | V | V | V | V | V | V | V | vocational |
| `trust-accounting-income` | V | V | V | U | V | V | V | vocational |
| `trust-dni-computation` | V | V | V | U | V | V | V | vocational |
| `section704c-contributor-gain` | V | V | V | V | V | V | V | vocational |
| `constructive-ownership-percent` | V | V | V | V | V | V | V | vocational |
| `related-party-resale-gain` | V | V | V | V | V | V | V | vocational |
| `basis-adjustment-754-allocation` | V | V | V | V | V | V | V | vocational |
| `income-shifting-pv-saving` | V | V | V | U | V | V | V | vocational |
| `sc-income-sourcing` | V | V | V | V | V | V | V | vocational |
| `fsa-tax-saving` | V | V | V | U | V | V | V | vocational |
| `builtin-gains-tax-base` | V | V | V | U | V | V | V | vocational |
| `varying-interest-allocation` | V | V | V | V | V | V | V | vocational |
| `sc-audit-opinion-type` | V | V | V | V | V | V | V | vocational |
| `control-deviation-rate` | V | V | V | V | V | V | V | vocational |
| `uncorrected-misstatement-total` | V | V | V | U | V | V | V | vocational |
| `sc-control-deficiency-severity` | V | V | V | V | U | V | V | vocational |
| `sc-confirmation-response-classification` | V | V | V | V | V | V | V | vocational |
| `compliance-violations-count` | V | V | V | U | V | V | V | vocational |
| `inventory-count-adjusted-balance` | V | V | V | V | V | V | V | vocational |
| `sc-evidence-reliability-choice` | V | V | V | V | V | V | V | vocational |
| `three-way-match-exceptions` | V | V | V | U | V | V | V | vocational |
| `schedule-recalculation-difference` | V | V | V | U | V | V | V | vocational |
| `sc-ethics-threat-classification` | V | V | V | V | V | V | V | vocational |
| `sc-independence-prohibited-service` | V | V | V | V | V | V | V | vocational |
| `sc-engagement-acceptance` | V | V | V | V | V | V | V | vocational |
| `sc-service-organization-reliance` | V | V | V | V | V | V | V | vocational |
| `sc-professional-conduct` | V | V | V | V | V | V | V | vocational |
| `substantive-analytic-difference` | V | V | V | V | V | V | V | vocational |
| `securities-revaluation-misstatement` | V | V | V | U | V | V | V | vocational |
| `allowance-estimate-reperformance` | V | V | V | U | V | V | V | vocational |
| `single-audit-type-a-count` | V | V | V | U | V | V | V | vocational |
| `known-misstatement-from-sample` | V | V | V | U | V | V | V | vocational |
| `audit-data-missing-entries` | V | V | V | U | V | V | V | vocational |

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
| `periodic-purchase-with-freight` | inventory | journal-entry | core | application | — | Inventory debited (perpetual habit) |
| `bad-debt-percent-of-sales` | receivables | journal-entry | core | application | — | Aging-style true-up |
| `cash-discount-receipt` | receivables | journal-entry | core | application | — | Discount left in receivables |
| `abc-overhead-assigned` | activity-based-costing | numeric | core | application | — | Plantwide DLH rate |
| `high-low-variable-cost` | cost-behavior | numeric | core | application | — | Average cost at high volume |
| `cash-collections-budget` | budgeting | numeric | core | application | — | Current month only |
| `gross-profit-from-trial-balance` | financial-reporting | numeric | core | application | — | Gross sales minus COGS |
| `ending-retained-earnings` | equity | numeric | core | application | — | Add share-issue proceeds |
| `present-value-lump-sum` | time-value-of-money | numeric | core | application | — | Undiscounted face amount |
| `flexible-budget-total-cost` | budgeting | numeric | core | application | — | Static-budget volume |
| `narrative-multi-transactions` | transaction-classification | journal-entry | core | application | — | Expense the equipment |
| `units-of-production-depreciation` | fixed-assets | journal-entry | core | application | — | Ignore residual in unit rate |
| `warranty-provision-and-claims` | provisions-contingencies | journal-entry | core | application | — | Expense claims paid (cash basis) |
| `sales-tax-collection` | transaction-classification | journal-entry | core | application | — | Tax-inclusive revenue |
| `petty-cash-replenishment` | cash-controls | journal-entry | core | application | — | Replenish receipts only |
| `small-stock-dividend` | equity | journal-entry | core | application | — | Capitalize at par only |
| `accounting-equation-missing-equity` | financial-reporting | numeric | core | application | — | Beginning equity |
| `current-income-tax-expense` | income-taxes | numeric | core | application | `asc:740`, `ias:12` | Book income x rate |
| `lease-liability-present-value` | leases | numeric | core | application | `asc:842`, `ifrs:16` | Undiscounted payment sum |
| `equity-method-carrying-amount` | investments | numeric | core | application | `asc:323`, `ias:28` | Forget dividends reduce carrying amount |
| `bond-issue-price` | borrowings | numeric | core | application | `asc:835-30`, `ifrs:9` | Answer face value (par) |
| `partnership-income-allocation` | partnerships | numeric | core | application | — | Ratio on whole income |
| `mc-normal-balances` | transaction-classification | multiple-choice | core | remembering-understanding | — | Contra-assets as debit-normal |
| `sc-special-journal-routing` | ledger-integrity-reporting | single-choice | core | remembering-understanding | — | Return routed to sales journal |
| `short-term-note-payment` | borrowings | journal-entry | core | application | — | Pay principal only |
| `credit-card-sale-fee` | transaction-classification | journal-entry | core | application | — | Net deposit as sales |
| `patent-amortization` | intangible-assets | journal-entry | core | application | `asc:350`, `ias:38` | Amortize over legal life |
| `loss-contingency-accrual` | provisions-contingencies | journal-entry | core | application | `asc:450`, `ias:37` | Accrue the remote claim too |
| `bond-issued-at-premium` | borrowings | journal-entry | core | application | `asc:835-30`, `ifrs:9` | Liability at proceeds |
| `closing-drawing-account` | equity | journal-entry | core | application | — | Close drawings to income summary |
| `trading-securities-fair-value` | investments | journal-entry | core | application | `asc:321`, `ifrs:9` | Leave at cost / gain to sales |
| `materials-quantity-variance` | standard-costing | numeric | core | application | — | Use quantity purchased |
| `cost-of-goods-manufactured` | job-order-costing | numeric | core | application | — | Skip WIP adjustment |
| `payback-period-years` | capital-budgeting | numeric | core | application | — | Divide by net income |
| `multiproduct-breakeven-units` | cost-volume-profit | numeric | core | application | — | Simple-average margin |
| `total-current-liabilities` | financial-reporting | numeric | core | application | — | Include long-term note |
| `sc-cash-flow-classification` | cash-flow-statement | single-choice | core | remembering-understanding | `asc:230`, `ias:7` | Dividends paid as operating |
| `inventory-shrinkage-adjustment` | inventory | journal-entry | core | application | — | Shrinkage at selling price |
| `purchase-return-perpetual` | inventory | journal-entry | core | application | — | Return at selling price |
| `overhead-variance-disposition` | job-order-costing | journal-entry | core | application | — | Reversed (overapplied) entry |
| `unearned-revenue-release` | accruals-deferrals | journal-entry | core | application | — | Release the whole advance |
| `bond-early-retirement` | borrowings | journal-entry | core | application | `asc:405-20`, `ifrs:9` | Loss measured against face |
| `fvoci-fair-value-adjustment` | investments | journal-entry | ifrs | application | `ifrs:9` | Gain credited to income |
| `basket-purchase-allocation` | fixed-assets | journal-entry | core | application | — | Split the lump sum evenly |
| `labor-efficiency-variance` | standard-costing | numeric | core | application | — | Rate-variance formula |
| `diluted-eps` | financial-analysis | numeric | core | application | `asc:260`, `ias:33` | Basic EPS |
| `asset-turnover-ratio` | financial-analysis | numeric | core | application | — | Ending assets |
| `breakeven-sales-dollars` | cost-volume-profit | numeric | core | application | — | Answer break-even units |
| `direct-materials-used` | job-order-costing | numeric | core | application | — | Purchases only |
| `sc-subsequent-event-classification` | financial-reporting | single-choice | core | remembering-understanding | `asc:855`, `ias:10` | Later fire treated as adjusting |
| `treasury-stock-reissuance` | equity | journal-entry | core | application | — | Excess credited to income |
| `lease-initial-recognition` | leases | journal-entry | core | application | `asc:842`, `ifrs:16` | Undiscounted payments recognized |
| `fx-payable-remeasurement` | foreign-currency | journal-entry | core | application | `asc:830`, `ias:21` | Remeasure inventory too |
| `development-cost-capitalization` | intangible-assets | journal-entry | ifrs | application | `ias:38` | Capitalize all project spend |
| `inventory-error-correction` | accounting-changes-errors | journal-entry | core | application | `asc:250`, `ias:8` | Correction through current COGS |
| `long-lived-asset-impairment` | fixed-assets | journal-entry | ifrs | application | `ias:36` | Use lower recoverable measure |
| `production-budget-units` | budgeting | numeric | core | application | — | Answer budgeted sales units |
| `predetermined-overhead-applied` | job-order-costing | numeric | core | application | — | Answer actual overhead |
| `interim-income-tax-expense` | income-taxes | numeric | core | application | `asc:740`, `ias:34` | Q2-only income x rate |
| `segment-margin` | responsibility-accounting | numeric | core | application | — | Subtract common fixed costs |
| `residual-income` | responsibility-accounting | numeric | core | application | — | Answer ROI percentage |
| `cash-collected-from-customers` | cash-flow-statement | numeric | core | application | `asc:230`, `ias:7` | Answer accrual sales |
| `free-cash-flow` | cash-flow-statement | numeric | core | application | `asc:230`, `ias:7` | Omit dividends from definition |
| `sc-transaction-statement-impact` | transaction-classification | single-choice | core | application | — | Treat asset exchange as asset increase |
| `business-combination-acquisition` | business-combinations | journal-entry | core | analysis | `asc:805`, `ifrs:3` | Push excess into equipment |
| `consolidation-intercompany-elimination` | consolidations | journal-entry | core | analysis | `asc:810`, `ifrs:10` | Eliminate only 80% |
| `held-for-sale-measurement` | fixed-assets | journal-entry | ifrs | application | `ifrs:5` | Reclassify without write-down |
| `share-based-compensation-monthly` | share-based-payment | journal-entry | core | application | `asc:718`, `ifrs:2` | Expense whole grant at once |
| `asset-revaluation-surplus` | fixed-assets | journal-entry | ifrs | application | `ias:16` | Credit uplift to income |
| `written-off-receivable-recovery` | receivables | journal-entry | core | application | — | Credit recovery to revenue |
| `nfp-conditional-vs-unconditional` | not-for-profit | journal-entry | us-gaap | analysis | `asc:958` | Conditional cash as revenue |
| `adjusted-receivable-balance` | receivables | numeric | core | application | — | Forget write-offs |
| `ppe-additions-inferred` | fixed-assets | numeric | core | application | — | Answer net PPE increase |
| `fixed-overhead-volume-variance` | standard-costing | numeric | core | application | — | Answer spending variance |
| `cumulative-preferred-dividend` | equity | numeric | core | application | — | Ignore preferred arrears |
| `weighted-average-cost-of-capital` | cost-of-capital | numeric | core | application | — | Use pre-tax debt cost |
| `standard-cost-per-unit` | standard-costing | numeric | core | application | — | Use actual materials price |
| `sc-job-vs-process-costing` | product-costing | single-choice | core | remembering-understanding | — | Mismatch production pattern |
| `government-grant-release` | government-grants | journal-entry | ifrs | application | `ias:20` | Recognize whole grant at once |
| `investment-property-fair-value` | investment-property | journal-entry | ifrs | application | `ias:40` | Route gain to OCI |
| `goodwill-impairment` | business-combinations | journal-entry | ifrs | application | `ias:36` | Write equipment down first |
| `fx-translation-adjustment` | foreign-currency | journal-entry | core | application | `asc:830`, `ias:21` | Translation gain to income |
| `sale-and-leaseback-entry` | leases | journal-entry | us-gaap | analysis | `asc:842` | Defer qualifying sale gain |
| `debt-security-credit-loss` | investments | journal-entry | us-gaap | application | `asc:326` | Provide for full FV decline |
| `trial-balance-debit-total` | ledger-integrity-reporting | numeric | core | application | — | Contra-assets as debits |
| `post-closing-debit-total` | ledger-integrity-reporting | numeric | core | application | — | Pre-closing debit total |
| `adjusted-wage-expense` | adjustments-corrections | numeric | core | application | — | Answer cash paid |
| `inventory-method-profit-difference` | inventory | numeric | core | application | — | Profit gap direction reversed |
| `minimum-transfer-price` | responsibility-accounting | numeric | core | application | — | Variable production cost only |
| `debt-modification-percent-change` | borrowings | numeric | core | application | `asc:470-50`, `ifrs:9` | Compare face amounts |
| `mc-temporary-accounts` | ledger-integrity-reporting | multiple-choice | core | remembering-understanding | — | Permanent contra-assets as temporary |
| `sc-fair-value-hierarchy` | fair-value-measurement | single-choice | core | remembering-understanding | `asc:820`, `ifrs:13` | Observable inputs as Level 3 |
| `deferred-tax-asset-warranty` | income-taxes | journal-entry | core | application | `asc:740`, `ias:12` | Current tax only |
| `consignment-sale-recognition` | revenue-recognition | journal-entry | core | analysis | `asc:606`, `ifrs:15` | Net remittance as revenue |
| `natural-resource-depletion` | fixed-assets | journal-entry | core | application | — | Deplete only tons sold |
| `internal-use-software-costs` | intangible-assets | journal-entry | us-gaap | application | `asc:350-40` | Capitalize all project costs |
| `lessor-sales-type-lease` | leases | journal-entry | core | analysis | `asc:842`, `ifrs:16` | Record lease at cost |
| `factoring-secured-borrowing` | receivables | journal-entry | core | analysis | `asc:860`, `ifrs:9` | Derecognize receivables |
| `pension-expense-and-contribution` | employee-benefits | journal-entry | us-gaap | analysis | `asc:715` | Amortization through the liability |
| `irr-from-annuity-factor` | capital-budgeting | numeric | core | application | — | Answer payback factor |
| `c-corporation-taxable-income` | income-taxes | numeric | core | application | — | Answer book income |
| `s-corporation-aaa-ending` | passthrough-taxation | numeric | core | application | — | Tax-exempt income into AAA |
| `partnership-outside-basis` | passthrough-taxation | numeric | core | application | — | Forget liability share |
| `performance-materiality` | audit-planning | numeric | core | application | — | Answer overall materiality |
| `cash-and-equivalents-total` | cash-controls | numeric | core | application | — | Include restricted cash and net overdraft |
| `sc-investment-classification` | investments | single-choice | us-gaap | remembering-understanding | `asc:320` | Mismatch management intent |
| `mc-reportable-segments` | segment-reporting | multiple-choice | core | application | `asc:280`, `ifrs:8` | Require all three 10% tests |
| `cash-flow-hedge-fair-value` | derivatives-hedging | journal-entry | ifrs | analysis | `ifrs:9` | Whole gain to OCI |
| `provision-rollforward-topup` | provisions-contingencies | journal-entry | core | application | `asc:420`, `ias:37` | Expense required ending balance |
| `partnership-admission-bonus` | partnerships | journal-entry | core | analysis | — | Credit new partner full contribution |
| `governmental-encumbrance-entry` | governmental-accounting | journal-entry | us-gaap | application | — | Expenditure at PO estimate |
| `contract-acquisition-cost` | revenue-recognition | journal-entry | core | application | `asc:340-40`, `ifrs:15` | Expense incremental commission |
| `aro-accretion` | provisions-contingencies | journal-entry | us-gaap | application | `asc:410` | Accrete undiscounted amount |
| `tax-return-crossfoot-difference` | income-taxes | numeric | core | application | — | Subtract below-total adjustment |
| `tax-cost-recovery-deduction` | income-taxes | numeric | core | application | — | Use book depreciation |
| `passthrough-loss-limitation` | passthrough-taxation | numeric | core | application | — | Stop at basis limit |
| `partnership-distribution-gain` | passthrough-taxation | numeric | core | application | — | Tax whole distribution |
| `sample-misstatement-projection` | audit-sampling | numeric | core | application | — | Known sample error only |
| `capm-expected-return` | cost-of-capital | numeric | core | application | — | Beta times market return |
| `duplicate-payments-total` | audit-analytics | numeric | core | application | — | Include first legitimate payment |
| `sc-audit-procedure-selection` | audit-evidence | single-choice | core | application | — | Mismatch assertion and procedure |
| `sc-control-design-gap` | internal-control | single-choice | core | application | — | Generic control not matching gap |
| `inventory-error-income-effect` | inventory | numeric | core | application | `asc:330`, `ias:2` | Self-correcting so Year 2 unaffected |
| `inventory-lcm-value` | inventory | numeric | core | application | `asc:330` | Replacement cost as market, unbounded |
| `sc-fraud-triangle-classification` | audit-planning | single-choice | core | application | — | Pressure read as opportunity |
| `expected-profit-choice` | decision-analysis | numeric | core | application | — | Weaker alternative's expected profit |
| `receivables-control-balance` | receivables | numeric | core | application | — | Cash sales swept into control account |
| `partnership-formation-capital` | partnerships | journal-entry | core | application | — | Record contributed asset at old book value |
| `partnership-liquidation-distribution` | partnerships | numeric | core | application | — | Allocate gain by capital ratio |
| `partnership-retirement-settlement` | partnerships | journal-entry | core | application | — | Excess debited to goodwill |
| `biological-asset-fair-value` | agriculture | journal-entry | ifrs | application | `ias:41` | Gain routed to OCI |
| `sc-debt-equity-classification` | financial-instruments | single-choice | ifrs | application | `ias:32` | Follow legal label over substance |
| `sc-control-assessment` | consolidation | single-choice | ifrs | application | `ifrs:10` | Treat 50% of votes as a bright line |
| `profit-from-capital-movements` | ledger-integrity-reporting | numeric | core | application | — | Raw capital increase taken as profit |
| `sales-from-markup-reconstruction` | ledger-integrity-reporting | numeric | core | application | — | Markup treated as margin on sales |
| `inventory-cost-inclusions` | inventory | numeric | core | application | `asc:330`, `ias:2` | Capitalize abnormal waste and storage |
| `disposal-of-subsidiary-gain` | consolidation | numeric | core | application | `asc:810`, `ifrs:10` | Gain on parent's share only |
| `step-acquisition-remeasurement-gain` | business-combinations | numeric | core | application | `asc:805`, `ifrs:3` | Gain measured from original cost |
| `weighted-average-ending-inventory` | inventory | numeric | core | application | `asc:330`, `ias:2` | Ending units at latest (FIFO) prices |
| `ledger-account-balance-carried-down` | ledger-integrity-reporting | numeric | core | application | — | Netting entries the wrong way round |
| `allowance-movement-expense` | receivables | numeric | core | application | — | Expense whole required allowance |
| `receivables-payables-contra` | receivables | journal-entry | core | application | — | Clearing the larger balance in full |
| `sc-measurement-basis` | financial-reporting | single-choice | core | remembering-understanding | — | Matching basis to account name |
| `agent-commission-revenue` | revenue-recognition | numeric | core | application | `asc:606`, `ifrs:15` | Gross collections as revenue |
| `gift-card-breakage-revenue` | revenue-recognition | numeric | core | application | `asc:606`, `ifrs:15` | Only amounts redeemed so far |
| `adjusted-profit-from-draft` | financial-reporting | numeric | core | application | — | Subtracting the prepayment too |
| `payables-control-balance` | payables | numeric | core | application | — | Cash purchases swept into control account |
| `restructuring-provision-amount` | provisions-contingencies | numeric | core | application | `asc:420`, `ias:37` | Providing for retraining/relocation |
| `sc-suspense-account-cause` | ledger-integrity-reporting | single-choice | core | application | — | Every error routed through suspense |
| `sc-business-vs-asset-acquisition` | business-combinations | single-choice | ifrs | application | `asc:805`, `ifrs:3` | Assets without a process called a business |
| `contract-modification-revenue` | revenue-recognition | numeric | core | application | `asc:606`, `ifrs:15` | Blended cumulative catch-up pricing |
| `sc-derecognition-assessment` | financial-instruments | single-choice | ifrs | application | `ifrs:9` | Legal sale followed despite retained risk |
| `lease-component-allocation` | leases | numeric | core | application | `asc:842`, `ifrs:16` | Whole bundled payment capitalized |
| `sc-offsetting-assessment` | financial-instruments | single-choice | ifrs | application | `ias:32` | Netting on same counterparty alone |
| `sc-related-party-identification` | financial-reporting | single-choice | ifrs | application | `ias:24` | Only named group companies recognized |
| `separate-statements-investment` | financial-reporting | numeric | core | application | `ias:27` | Dividends netted off the investment |
| `sc-backup-recovery-selection` | it-controls | single-choice | core | application | — | Newest incremental alone / recover past broken link |
| `change-control-deviation-count` | it-controls | numeric | core | application | — | Flagging retro-approved emergency changes |
| `sc-database-integrity-gap` | it-controls | single-choice | core | application | — | Nullable optional column called a gap |
| `incident-response-deviation-count` | it-controls | numeric | core | application | — | Counting only late notifications |
| `sc-soc-opinion-modification` | audit-planning | single-choice | core | application | — | Modifying for isolated immaterial deviations |
| `sql-join-excluded-count` | audit-analytics | numeric | core | application | — | Answering rows returned by the query |
| `sc-system-description-gap` | audit-planning | single-choice | core | application | — | Rating a boundary-less description complete |
| `budget-vs-actual-net-variance` | budgeting | numeric | core | application | — | Same sign for revenue/expense variances |
| `cash-to-accrual-profit` | financial-reporting | numeric | core | application | — | Payables increase subtracted |
| `debt-covenant-ratio` | financial-analysis | numeric | core | application | — | Statement totals over covenant definitions |
| `exit-obligation-january-amount` | provisions-contingencies | numeric | core | application | `asc:420` | Full recognition despite service condition |
| `sc-governmental-fund-assignment` | governmental-accounting | single-choice | us-gaap | application | — | Restricted resources in the general fund |
| `htm-premium-amortization` | investments | journal-entry | us-gaap | application | `asc:320` | Straight-line premium amortization |
| `nfp-program-expense-allocation` | not-for-profit | numeric | core | application | `asc:958` | Management salary spread to programs |
| `nfp-operating-cash-flow` | not-for-profit | numeric | core | application | `asc:230`, `asc:958` | Restricted gifts left in operating |
| `nfp-restricted-net-assets` | not-for-profit | numeric | core | application | `asc:958` | Board designation counted as restricted |
| `notes-figures-difference` | financial-reporting | numeric | core | application | — | Gross note total vs net statement line |
| `tax-basis-net-income` | income-taxes | numeric | core | application | — | GAAP depreciation in tax-basis statements |
| `benefit-plan-net-assets` | employee-benefits | numeric | core | application | `asc:962` | Deducting a DC-plan benefit obligation |
| `sc-component-unit-presentation` | governmental-accounting | single-choice | us-gaap | application | — | Fiscal dependency alone blended |
| `sc-fund-balance-classification` | governmental-accounting | single-choice | us-gaap | application | — | Management intent called committed |
| `govt-conversion-net-position` | governmental-accounting | numeric | core | application | — | Unavailable revenue subtracted again |
| `govt-capitalized-costs-total` | governmental-accounting | numeric | core | application | — | Below-threshold outlays capitalized |
| `govt-expenditures-december` | governmental-accounting | numeric | core | application | — | Unmatured principal expensed early |
| `govt-long-term-debt-total` | governmental-accounting | numeric | core | application | — | Current portion excluded |
| `govt-net-investment-capital` | governmental-accounting | numeric | core | application | — | Unrelated debt deducted |
| `sc-interfund-activity-type` | governmental-accounting | single-choice | us-gaap | application | — | Repayable advance called a transfer |
| `nonexchange-revenue-recognized` | governmental-accounting | numeric | core | application | — | Whole advance taken as revenue |
| `adjusted-ebitda-computation` | financial-analysis | numeric | core | application | — | One-off loss left inside EBITDA |
| `sc-option-value-sensitivity` | financial-analysis | single-choice | core | application | — | Volatility/dividend directions reversed |
| `percent-of-sales-afn` | budgeting | numeric | core | application | — | Non-spontaneous items grown with sales |
| `sales-mix-variance` | standard-costing | numeric | core | application | — | Quantity variance reported as mix |
| `state-apportionment-income` | income-taxes | numeric | core | application | — | Three-factor split divided by 3 |
| `tax-penalty-combined` | income-taxes | numeric | core | application | — | Both rates stacked at 5.5%/month |
| `capital-loss-carryforward` | income-taxes | numeric | core | application | — | Whole carryforward called short-term |
| `sc-capital-gain-classification` | income-taxes | single-choice | core | application | — | Gift holding period not tacked |
| `disallowed-loss-amount` | income-taxes | numeric | core | application | — | Good investment loss also disallowed |
| `sc-s-corp-eligibility` | income-taxes | single-choice | core | application | — | Voting differences called second class |
| `individual-tax-with-niit` | income-taxes | numeric | core | application | — | NIIT on all investment income |
| `sc-tax-authority-disclosure` | income-taxes | single-choice | core | application | — | Reasonable basis upgraded to skip disclosure |
| `sc-filing-status` | income-taxes | single-choice | core | application | — | Head of household without half-year presence |
| `individual-gross-income-total` | income-taxes | numeric | core | application | — | Municipal interest included |
| `agi-above-line-adjustments` | income-taxes | numeric | core | application | — | Itemized deductions netted in AGI |
| `sc-tax-practice-ethics` | income-taxes | single-choice | core | application | — | Contingent fee for original return |
| `qbi-deduction-amount` | income-taxes | numeric | core | application | — | Capital gain left in limit base |
| `passthrough-ordinary-income` | passthrough-taxation | numeric | core | application | — | Portfolio interest in ordinary income |
| `owner-ordinary-from-k1` | passthrough-taxation | numeric | core | application | — | Separately stated items in ordinary income |
| `section1231-capital-amount` | income-taxes | numeric | core | application | — | Full net gain as capital |
| `depreciation-recapture-ordinary` | income-taxes | numeric | core | application | — | Larger of gain/depreciation as ordinary |
| `estimated-tax-installment` | income-taxes | numeric | core | application | — | Paying the higher safe harbor |
| `installment-sale-gain-year` | income-taxes | numeric | core | application | — | Percentage applied to cash incl. interest |
| `likekind-exchange-gain` | income-taxes | numeric | core | application | — | Whole realized gain recognized |
| `below-market-imputed-interest` | income-taxes | numeric | core | application | — | No credit for interest actually paid |
| `tax-equivalent-yield` | income-taxes | numeric | core | application | — | Grossing up by (1 + rate) |
| `taxable-gifts-total` | income-taxes | numeric | core | application | — | Exclusion granted to future interests |
| `charitable-noncash-deduction` | income-taxes | numeric | core | application | — | FMV deducted for ordinary property |
| `corporate-distribution-dividend` | corporate-taxation | numeric | core | application | — | Whole distribution as dividend |
| `liquidation-shareholder-gain` | corporate-taxation | numeric | core | application | — | Assumed liabilities ignored |
| `corporate-formation-gain` | corporate-taxation | numeric | core | application | — | Complete nonrecognition assumed |
| `partnership-contribution-gain` | passthrough-taxation | numeric | core | application | — | Contributions assumed always tax-free |
| `trust-accounting-income` | income-taxes | numeric | core | application | — | Corpus sale proceeds as income |
| `trust-dni-computation` | income-taxes | numeric | core | application | — | Corpus capital gain inside DNI |
| `section704c-contributor-gain` | passthrough-taxation | numeric | core | application | — | Built-in gain shared by ratio |
| `constructive-ownership-percent` | income-taxes | numeric | core | application | — | Partnership holding counted in full |
| `related-party-resale-gain` | income-taxes | numeric | core | application | — | Full resale gain taxed |
| `basis-adjustment-754-allocation` | passthrough-taxation | numeric | core | application | — | Adjustment spread by fair value |
| `income-shifting-pv-saving` | income-taxes | numeric | core | application | — | Nominal comparison, no present value |
| `sc-income-sourcing` | income-taxes | single-choice | core | application | — | Services sourced where paid |
| `fsa-tax-saving` | income-taxes | numeric | core | application | — | Forfeiture ignored in net benefit |
| `builtin-gains-tax-base` | corporate-taxation | numeric | core | application | — | Post-conversion gains in the base |
| `varying-interest-allocation` | passthrough-taxation | numeric | core | application | — | Year-end percentage all year |
| `sc-audit-opinion-type` | audit-planning | single-choice | core | application | — | Adverse for confined departures |
| `control-deviation-rate` | audit-planning | numeric | core | application | — | Deviation count reported as the rate |
| `uncorrected-misstatement-total` | audit-planning | numeric | core | application | — | Projected/prior-year effects omitted |
| `sc-control-deficiency-severity` | internal-control | single-choice | core | application | — | Small actual misstatement rules out weakness |
| `sc-confirmation-response-classification` | audit-evidence | single-choice | core | application | — | Non-response treated as agreement |
| `compliance-violations-count` | audit-planning | numeric | core | application | — | At-cap purchase flagged as violation |
| `inventory-count-adjusted-balance` | audit-evidence | numeric | core | application | — | Raw count without cutoff roll-forward |
| `sc-evidence-reliability-choice` | audit-evidence | single-choice | core | application | — | Client copies over external originals |
| `three-way-match-exceptions` | audit-evidence | numeric | core | application | — | Client 'matched' stamps trusted |
| `schedule-recalculation-difference` | audit-evidence | numeric | core | application | — | Stated extensions merely footed |
| `sc-ethics-threat-classification` | audit-planning | single-choice | core | application | — | Classify by appearance, not mechanism |
| `sc-independence-prohibited-service` | audit-planning | single-choice | core | application | — | Prohibited and preapprovable services conflated |
| `sc-engagement-acceptance` | audit-planning | single-choice | core | application | — | Scope-driven downgrade accepted |
| `sc-service-organization-reliance` | audit-planning | single-choice | core | application | — | Type 1 report used for operating effectiveness |
| `sc-professional-conduct` | audit-planning | single-choice | core | application | — | Wrong confidentiality exception invoked |
| `substantive-analytic-difference` | audit-evidence | numeric | core | application | — | Expectation built from recorded amount |
| `securities-revaluation-misstatement` | audit-evidence | numeric | core | application | — | Client price accepted for unquoted holding |
| `allowance-estimate-reperformance` | audit-evidence | numeric | core | application | — | Flat rate used instead of bucket rates |
| `single-audit-type-a-count` | audit-planning | numeric | core | application | — | Superseded USD 750k threshold applied |
| `known-misstatement-from-sample` | audit-evidence | numeric | core | application | — | Absolute differences accumulated |
| `audit-data-missing-entries` | audit-analytics | numeric | core | application | — | Extract accepted as complete |

Stable seeds: 101–391 (`STABLE_SEEDS` in `src/oab/families.py`).

## Coverage matrix (category × framework)

Cell values: number of Stable tasks; `planned` cells are roadmap
placeholders tracked as issues, not directories.

| Category | core | ifrs | us-gaap | jurisdiction pack |
|---|---:|---:|---:|---|
| financial-accounting | 139 | 17 | 13 | planned |
| management-accounting | 37 | planned | planned | planned |
| tax | 51 | — | — | planned |
| audit-assurance | 34 | — | planned | — |

Format coverage: journal-entry ×90, multiple-choice ×4, single-choice ×42,
numeric ×155; open-text is
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
