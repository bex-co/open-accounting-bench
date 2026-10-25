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

(none)

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

