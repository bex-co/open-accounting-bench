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

