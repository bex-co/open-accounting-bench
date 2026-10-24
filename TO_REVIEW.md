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

- [ ] **Level relabel (w1/010)** — `prepaid-insurance-adjustment`, `correct-misclassification`, `mgmt-break-even-units` university → vocational; `ifrs-capitalize-borrowing-costs` professional → university (the four mismatches confirmed in the 2026-10-23 review; relabelled, not hardened). Still open: lenient vs strict reading for `bank-recon-missing-fee`, `mc-capitalization-treatment` (university, borderline) and whether `ifrs-capitalize-borrowing-costs` is vocational under the strict reading.
- [ ] **`loan-effective-interest`** — new family (w1/m8, merged from `family/loan-effective-interest`). Check: scenario, policy wording (effective interest on opening carrying amount, rounded to the cent; coupon accrued), oracle, traps, level university (sketch said professional), standards tags. Proposed mappings: FAR.II.H.1#3 subset-of 8; FAR.II.H.1#4 subset-of 7; FA.D10(j) subset-of 7.
- [ ] **`suspense-clearance`** — new family (w1/m7, merged from `family/suspense-clearance`). Check: scenario, policy wording (clearing account must be zero; counter takings are cash sales), oracle, trap, level university, skill analysis; FA.F3(d) superset-of would count as covered. Proposed mappings: FAR.III.A#1 intersects-with 3; FA.F3(d) superset-of 8; FA.F3(c) intersects-with 4; FA.F2(c) subset-of 7.
- [ ] **`revenue-bundle-allocation`** — new family (w1/m6, merged from `family/revenue-bundle-allocation`). Check: scenario, policy wording (relative standalone selling prices; point-in-time vs monthly), oracle, traps, level university (sketch said professional), standards tags. Proposed mappings: FAR.III.C#4 subset-of 7; FR.B10(a) subset-of 6; FR.B10(b) subset-of 6.
- [ ] **`inventory-costing-nrv`** — new family (w1/m5, merged from `family/inventory-costing-nrv`). Check: scenario, policy wording (perpetual FIFO; lower of cost and NRV item by item), oracle, traps, level university, FIFO-only choice; FA.D3(b) superset-of would count as covered. Proposed mappings: FAR.II.C#1 subset-of 7; FAR.II.C#2 subset-of 8; FA.D3(b) superset-of 8; FA.D3(f) subset-of 7; FA.D3(c) subset-of 6.
- [ ] **`ppe-disposal`** — new family (w1/m4, merged from `family/ppe-disposal`). Check: scenario, policy wording (full month in acquisition and disposal months), oracle, traps, level university, task id changed from the note; FAR.II.D#2 superset-of would count as covered. Proposed mappings: FAR.II.D#2 superset-of 8; FAR.II.D#1 intersects-with 5; FA.D4(f) subset-of 7; FA.D4(e) subset-of 7; FA.D5(d) subset-of 6.
- [ ] **`payables-statement-recon`** — new family (w1/m3, merged from `family/payables-statement-recon`). Check: scenario, policy wording (correct errors only; timing items stay), oracle, traps, level university, skill analysis; FA.E2(d) superset-of would count as covered. Proposed mappings: FAR.II.G#4 intersects-with 5; FA.E2(d) superset-of 8; FA.E2(c) intersects-with 4.
- [ ] **`accrual-deferral-reversal`** — new family (w1/m2, merged from `family/accrual-deferral-reversal`). Check: scenario (opening balances stand in for December), policy wording (reverse on day 1; revenue per session), oracle, traps, level university. Proposed mappings: FAR.II.G#2 intersects-with 4; FA.D7(d) subset-of 7; FA.D7(a) subset-of 6.
- [ ] **`receivable-allowance-trueup`** — new family (w1/m1, merged from `family/receivable-allowance-trueup`). Check: policy wording (write-off, then true-up; either write-off method accepted), aging rates and oracle, traps, level university (borderline). Proposed mappings: FAR.II.B#1 subset-of 7; FA.D8(e) superset-of 8; FA.D8(h) subset-of 8.

## Reviewed

- 2026-10-23 — Tian Pan (maintainer): all crosswalk mappings for the
  original seven generators (strengths adjusted in b3a517f, status in
  8cd5187); gradability triage behind the `[[out_of_scope]]` records
  (dcb7565); the level rubric (48e7527).
