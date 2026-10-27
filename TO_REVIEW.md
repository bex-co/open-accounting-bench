# To review

Accounting review is deferred, not a merge gate ([docs/governance.md](docs/governance.md#contributions--review)).
Everything that changed accounting content without a reviewer's sign-off
is listed here; a reviewer with accounting background works through it
in batches. Agents add entries; only a reviewer moves one to
**Reviewed** (with name, date, and outcome). Findings are fixed forward
like bugs — bump `GENERATOR_VERSION` when expectations change.

Crosswalk mappings carry their own `status` (`proposed` / `reviewed`);
only reviewed links count toward cited coverage
([docs/metrics.md](docs/metrics.md#framework-coverage)).

For each family, check: scenario realism, `policy.md` wording, oracle
numbers (`tests/expected.json` vs the documents), the trap really is a
plausible mistake, the level scores
([rubric](docs/task-families.md#assigning-level)), and its `proposed`
crosswalk mappings.

## Pending

- 2026-10-26 — twelve new generator families (Stable seeds 116–127):
  `perpetual-sale-with-cost`, `sales-return-restock`,
  `supplies-adjustment`, `accrued-wages-adjustment`,
  `straight-line-depreciation`, `note-interest-accrual`,
  `payroll-withholdings`, `bond-discount-amortization`,
  `cvp-target-profit-units`, `process-costing-equivalent-units`,
  `operating-cash-flow-indirect`, `inventory-days-on-hand`. Check
  scenario realism, policy wording (in particular the stated effective
  monthly rate in `bond-discount-amortization` and the 30/360
  convention in `note-interest-accrual`), oracle numbers against the
  documents, trap plausibility, and the vocational level scores in
  [docs/task-families.md](docs/task-families.md). No crosswalk
  mappings have been proposed for these generators yet.
- 2026-10-26 — thirteen further generator families (Stable seeds
  128–140): `equity-issue-above-par`, `cash-dividend-declaration`,
  `treasury-stock-repurchase`, `closing-entries-income-summary`,
  `job-overhead-applied`, `note-dishonored`, `lifo-ending-inventory`,
  `materials-price-variance`, `npv-project-evaluation`,
  `make-or-buy-advantage`, `absorption-variable-income-difference`,
  `current-ratio`, `bank-adjusted-balance`. Same checks as the
  116–127 batch; note the stated annuity factor in
  `npv-project-evaluation` (4 d.p., used as given). No crosswalk
  mappings proposed yet.

- 2026-10-26 — thirteen further generator families (Stable seeds
  141–153): `capitalized-cost-bundle`, `employer-payroll-taxes`,
  `current-portion-reclass`, `periodic-purchase-with-freight`,
  `bad-debt-percent-of-sales`, `cash-discount-receipt`,
  `abc-overhead-assigned`, `high-low-variable-cost`,
  `cash-collections-budget`, `gross-profit-from-trial-balance`,
  `ending-retained-earnings`, `present-value-lump-sum`,
  `flexible-budget-total-cost`. Same checks as the earlier batches.
  No crosswalk mappings proposed yet.
- 2026-10-26 — fourteen further generator families (Stable seeds
  154–167), including the first committed single-choice family and the
  first two `tax`-category tasks: `narrative-multi-transactions`,
  `units-of-production-depreciation`, `warranty-provision-and-claims`,
  `sales-tax-collection`, `petty-cash-replenishment`,
  `small-stock-dividend`, `accounting-equation-missing-equity`,
  `current-income-tax-expense`, `lease-liability-present-value`,
  `equity-method-carrying-amount`, `bond-issue-price`,
  `partnership-income-allocation`, `mc-normal-balances`,
  `sc-special-journal-routing`. Same checks as the earlier batches
  (in particular: stated annuity/PV factors used as given; the
  small-vs-large stock-dividend threshold wording). No crosswalk
  mappings proposed yet.
- 2026-10-26 — fifteen further generator families (Stable seeds
  251–265): `cash-flow-hedge-fair-value`, `provision-rollforward-topup`,
  `partnership-admission-bonus`, `governmental-encumbrance-entry`,
  `contract-acquisition-cost`, `aro-accretion`,
  `tax-return-crossfoot-difference`, `tax-cost-recovery-deduction`,
  `passthrough-loss-limitation`, `partnership-distribution-gain`,
  `sample-misstatement-projection`, `capm-expected-return`,
  `duplicate-payments-total`, `sc-audit-procedure-selection`,
  `sc-control-design-gap`. Same checks as earlier batches (in
  particular: simplified stated tax and audit rules used exactly as
  given). No crosswalk mappings proposed yet.
- 2026-10-26 — five further generator families (Stable seeds
  266–270): `inventory-error-income-effect`, `inventory-lcm-value`,
  `sc-fraud-triangle-classification`, `expected-profit-choice`,
  `receivables-control-balance`. Same checks as earlier batches (in
  particular: the LCM ceiling/floor construction and stated
  conventions used exactly as given). No crosswalk mappings proposed
  yet.
- 2026-10-26 — fifteen further generator families (Stable seeds
  236–250): `deferred-tax-asset-warranty`, `consignment-sale-recognition`,
  `natural-resource-depletion`, `internal-use-software-costs`,
  `lessor-sales-type-lease`, `factoring-secured-borrowing`,
  `pension-expense-and-contribution`, `irr-from-annuity-factor`,
  `c-corporation-taxable-income`, `s-corporation-aaa-ending`,
  `partnership-outside-basis`, `performance-materiality`,
  `cash-and-equivalents-total`, `sc-investment-classification`,
  `mc-reportable-segments`. Same checks as earlier batches (in
  particular: simplified stated tax rules for AAA/outside basis and the
  single-benchmark materiality setup). No crosswalk mappings proposed yet.
- 2026-10-26 — fourteen further generator families (Stable seeds
  222–235): `government-grant-release`, `investment-property-fair-value`,
  `goodwill-impairment`, `fx-translation-adjustment`,
  `sale-and-leaseback-entry`, `debt-security-credit-loss`,
  `trial-balance-debit-total`, `post-closing-debit-total`,
  `adjusted-wage-expense`, `inventory-method-profit-difference`,
  `minimum-transfer-price`, `debt-modification-percent-change`,
  `mc-temporary-accounts`, `sc-fair-value-hierarchy`. Same checks as
  earlier batches (in particular: no-transaction simplification in
  the translation task and sale qualification stated as a fact in the
  sale-and-leaseback task). No crosswalk mappings proposed yet.
- 2026-10-26 — fourteen further generator families (Stable seeds
  208–221): `business-combination-acquisition`,
  `consolidation-intercompany-elimination`, `held-for-sale-measurement`,
  `share-based-compensation-monthly`, `asset-revaluation-surplus`,
  `written-off-receivable-recovery`, `nfp-conditional-vs-unconditional`,
  `adjusted-receivable-balance`, `ppe-additions-inferred`,
  `fixed-overhead-volume-variance`, `cumulative-preferred-dividend`,
  `weighted-average-cost-of-capital`, `standard-cost-per-unit`,
  `sc-job-vs-process-costing`. Same checks as earlier batches (in
  particular: combined-opening-balance construction in the
  consolidation task; the elimination method stated for revaluation;
  five university-level scores). No crosswalk mappings proposed yet.
- 2026-10-26 — fourteen further generator families (Stable seeds
  194–207): `treasury-stock-reissuance`, `lease-initial-recognition`,
  `fx-payable-remeasurement`, `development-cost-capitalization`,
  `inventory-error-correction`, `long-lived-asset-impairment`,
  `production-budget-units`, `predetermined-overhead-applied`,
  `interim-income-tax-expense`, `segment-margin`, `residual-income`,
  `cash-collected-from-customers`, `free-cash-flow`,
  `sc-transaction-statement-impact`. Same checks as the earlier batches
  (in particular: stated annuity factor and free-cash-flow definition
  used exactly as given; prior-period inventory correction is stated
  gross of tax). No crosswalk mappings proposed yet.
- 2026-10-26 — thirteen further generator families (Stable seeds
  181–193): `inventory-shrinkage-adjustment`, `purchase-return-perpetual`,
  `overhead-variance-disposition`, `unearned-revenue-release`,
  `bond-early-retirement`, `fvoci-fair-value-adjustment`,
  `basket-purchase-allocation`, `labor-efficiency-variance`,
  `diluted-eps`, `asset-turnover-ratio`, `breakeven-sales-dollars`,
  `direct-materials-used`, `sc-subsequent-event-classification`.
  Same checks as the earlier batches (in particular: diluted-EPS answers
  grade within one cent of the exact treasury-method value). No
  crosswalk mappings proposed yet.
- 2026-10-26 — thirteen further generator families (Stable seeds
  168–180): `short-term-note-payment`, `credit-card-sale-fee`,
  `patent-amortization`, `loss-contingency-accrual`,
  `bond-issued-at-premium`, `closing-drawing-account`,
  `trading-securities-fair-value`, `materials-quantity-variance`,
  `cost-of-goods-manufactured`, `payback-period-years`,
  `multiproduct-breakeven-units`, `total-current-liabilities`,
  `sc-cash-flow-classification`. Same checks as the earlier batches
  (in particular: the probable/remote wording in
  `loss-contingency-accrual`; dividends-paid-as-financing is the
  US-GAAP/IFRS policy choice stated in `sc-cash-flow-classification`).
  No crosswalk mappings proposed yet.
- 2026-10-26 — review-response changes under GENERATOR_VERSION 0.4.0
  (commits 612a706, d9f843b, accb483), for reviewer confirmation:
  - `pension-expense-and-contribution` remodelled to US GAAP (ASC 715)
    only: amortization of prior losses now reclassified out of AOCI
    (opening debit balance seeded at 3-6x the month's amortization);
    the liability falls by contribution - (service + interest -
    expected return). Check the AOCI mechanics and that dropping the
    IAS 19 tag is right (IAS 19 has no amortization or expected
    return).
  - `cash-flow-hedge-fair-value` retagged IFRS 9 only; the document
    now gives the hedged item's cumulative change so the IFRS 9
    lower-of test is what solvers apply.
  - `governmental-encumbrance-entry` redesigned around a partial
    receipt so the encumbrance balance is graded at month-end.
  - `factoring-secured-borrowing` accepts 1-3 transactions;
    `passthrough-loss-limitation` states non-participation;
    `inventory-error-correction` states materiality;
    `capitalized-cost-bundle` expenses post-in-service routine
    maintenance (was a prepaid service plan);
    `sc-subsequent-event-classification` drops the stock-split case.
  - Bond/ARO generators now price from their stated rates
    (`bond-discount-amortization`, `bond-issued-at-premium`,
    `aro-accretion`); several generators' ranges were constrained so
    the documented trap can never equal gold and scenarios stay
    sensible on every seed (permanent 1,000-seed sweep tests).
  - Level re-score of seeds 116-270 at the strict reading (30
    university, 25 of them borderline; 125 vocational), with a new
    consistency test tying docs scores, labels, and generator
    levels together. The re-scores are themselves judgement;
    spot-check in particular the borderline rows and
    `predetermined-overhead-applied` (scored vocational here: the
    rate derivation is a single two-input intermediate).
  - Decisions recorded for confirmation (same form as the
    2026-10-25 "Accepted equivalences"): stated factors must be used
    as given and not recomputed (`npv-project-evaluation`,
    `present-value-lump-sum`, `lease-initial-recognition` and peers);
    answers recomputing exact factors may miss by up to USD 1.88 and
    score 0. Accepted as a stated-instruction convention, pending
    reviewer sign-off.
- 2026-10-26 — twelve further generator families (Stable seeds
  271–282): `partnership-formation-capital`,
  `partnership-liquidation-distribution`,
  `partnership-retirement-settlement`, `biological-asset-fair-value`,
  `sc-debt-equity-classification`, `sc-control-assessment`,
  `profit-from-capital-movements`, `sales-from-markup-reconstruction`,
  `inventory-cost-inclusions`, `disposal-of-subsidiary-gain`,
  `step-acquisition-remeasurement-gain`,
  `weighted-average-ending-inventory`. Same checks as earlier batches
  (in particular: the loss-of-control gain formula as stated, the
  de-facto-control cases, and the IAS 32 compound-instrument case).
  Level scores were assigned under the strict reading from the start.
  No crosswalk mappings proposed yet.
- 2026-10-26 — ten further generator families (Stable seeds 283–292):
  `ledger-account-balance-carried-down`, `allowance-movement-expense`,
  `receivables-payables-contra`, `sc-measurement-basis`,
  `agent-commission-revenue`, `gift-card-breakage-revenue`,
  `adjusted-profit-from-draft`, `payables-control-balance`,
  `restructuring-provision-amount`, `sc-suspense-account-cause`. Same
  checks as earlier batches (in particular: the proportional-breakage
  formula and the measurement-basis case wordings). Level scores
  assigned under the strict reading. No crosswalk mappings proposed
  yet.
- 2026-10-26 — seven further generator families (Stable seeds
  293–299): `sc-business-vs-asset-acquisition`,
  `contract-modification-revenue`, `sc-derecognition-assessment`,
  `lease-component-allocation`, `sc-offsetting-assessment`,
  `sc-related-party-identification`, `separate-statements-investment`.
  Same checks as earlier batches (in particular: the derecognition,
  control-adjacent, and offsetting case outcomes — several are
  simplified stated-convention versions of IFRS 9/10 and IAS 32).
  Level scores assigned under the strict reading. No crosswalk
  mappings proposed yet.
- 2026-10-26 — seven further generator families (Stable seeds
  300–306, ISC/IT-controls slice): `sc-backup-recovery-selection`,
  `change-control-deviation-count`, `sc-database-integrity-gap`,
  `incident-response-deviation-count`, `sc-soc-opinion-modification`,
  `sql-join-excluded-count`, `sc-system-description-gap`. Same checks
  as earlier batches (in particular: the stated SOC opinion matrix
  and backup-chain conventions are simplified versions of AT-C
  practice, stated in full in each policy). Level scores assigned
  under the strict reading. No crosswalk mappings proposed yet.
- 2026-10-26 — eleven further generator families (Stable seeds
  307–317): `budget-vs-actual-net-variance`, `cash-to-accrual-profit`,
  `debt-covenant-ratio`, `exit-obligation-january-amount`,
  `sc-governmental-fund-assignment`, `htm-premium-amortization`,
  `nfp-program-expense-allocation`, `nfp-operating-cash-flow`,
  `nfp-restricted-net-assets`, `notes-figures-difference`,
  `tax-basis-net-income`. Same checks as earlier batches (in
  particular: the ASC 420 ratable-accrual slice and the NFP
  financing classification of restricted contributions). Level
  scores assigned under the strict reading. No crosswalk mappings
  proposed yet.
- 2026-10-26 — fourteen further generator families (Stable seeds
  318–331): `benefit-plan-net-assets`,
  `sc-component-unit-presentation`,
  `sc-fund-balance-classification`,
  `govt-conversion-net-position`,
  `govt-capitalized-costs-total`,
  `govt-expenditures-december`,
  `govt-long-term-debt-total`,
  `govt-net-investment-capital`,
  `sc-interfund-activity-type`,
  `nonexchange-revenue-recognized`,
  `adjusted-ebitda-computation`,
  `sc-option-value-sensitivity`,
  `percent-of-sales-afn`,
  `sales-mix-variance`. Same
  checks as earlier batches (in particular: the stated GASB
  conventions for component units, fund balance, modified-accrual
  exceptions, and net-position components are simplified versions
  stated in each policy). Level scores assigned under the strict
  reading. No crosswalk mappings proposed yet.
- 2026-10-26 — fifteen further generator families (Stable seeds
  332–346): `state-apportionment-income`, `tax-penalty-combined`,
  `capital-loss-carryforward`, `sc-capital-gain-classification`,
  `disallowed-loss-amount`, `sc-s-corp-eligibility`,
  `individual-tax-with-niit`, `sc-tax-authority-disclosure`,
  `sc-filing-status`, `individual-gross-income-total`,
  `agi-above-line-adjustments`, `sc-tax-practice-ethics`,
  `qbi-deduction-amount`, `passthrough-ordinary-income`,
  `owner-ordinary-from-k1`. All tax rules are simplified stated
  conventions given in full in each task policy (brackets, penalty
  rates, eligibility tests) — reviewer should confirm the
  simplifications are acceptable stand-ins and the stated-rule
  outcomes. Level scores assigned under the strict reading. No
  crosswalk mappings proposed yet.
- 2026-10-26 — thirteen further generator families (Stable seeds
  347–359): `section1231-capital-amount`,
  `depreciation-recapture-ordinary`, `estimated-tax-installment`,
  `installment-sale-gain-year`, `likekind-exchange-gain`,
  `below-market-imputed-interest`, `tax-equivalent-yield`,
  `taxable-gifts-total`, `charitable-noncash-deduction`,
  `corporate-distribution-dividend`, `liquidation-shareholder-gain`,
  `corporate-formation-gain`, `partnership-contribution-gain`. All
  tax rules are simplified stated conventions in each policy (the
  1231 lookback, 1245 recapture cap, penalty caps, and Section 351 /
  partnership debt-relief slices in particular). Level scores
  assigned under the strict reading. No crosswalk mappings proposed
  yet.


## Reviewed

- 2026-10-23 — Tian Pan (maintainer): all crosswalk mappings for the
  original seven generators (strengths adjusted in b3a517f, status in
  8cd5187); gradability triage behind the `[[out_of_scope]]` records
  (dcb7565); the level rubric (48e7527).
- 2026-10-25 — Tian Pan (maintainer): all nine pending items.
  - Eight new families accepted (oracles re-derived; 15 families x 400
    seeds all reward 1). Accepted equivalences: direct write-off to
    expense then true-up (receivable-allowance-trueup); settling the bill
    against the accrual without reversal (accrual-deferral-reversal).
  - Fixed forward in 5b804f1 (GENERATOR_VERSION 0.3.0): ppe-disposal
    negative proceeds; suspense memo sign; loan policy states the given
    effective rate is to be used (tolerance unchanged).
  - Mappings in 2096969: FA.E2(d) and FAR.II.D#2 superset-of ->
    subset-of; FA.D3(f) 7 -> 6; all others reviewed as proposed.
  - Level: strict reading adopted for every task and written into the
    rubric; bank-recon-missing-fee, mc-capitalization-treatment,
    ifrs-capitalize-borrowing-costs, ppe-disposal, inventory-costing-nrv
    -> vocational; per-task scores published in docs/task-families.md.

