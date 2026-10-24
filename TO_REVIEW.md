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

- [ ] **`accrual-deferral-reversal`** — new family (w1/m2, merged from `family/accrual-deferral-reversal`). Check: scenario (opening balances stand in for December), policy wording (reverse on day 1; revenue per session), oracle, traps, level university. Proposed mappings: FAR.II.G#2 intersects-with 4; FA.D7(d) subset-of 7; FA.D7(a) subset-of 6.
- [ ] **`receivable-allowance-trueup`** — new family (w1/m1, merged from `family/receivable-allowance-trueup`). Check: policy wording (write-off, then true-up; either write-off method accepted), aging rates and oracle, traps, level university (borderline). Proposed mappings: FAR.II.B#1 subset-of 7; FA.D8(e) superset-of 8; FA.D8(h) subset-of 8.

## Reviewed

- 2026-10-23 — Tian Pan (maintainer): all crosswalk mappings for the
  original seven generators (strengths adjusted in b3a517f, status in
  8cd5187); gradability triage behind the `[[out_of_scope]]` records
  (dcb7565); the level rubric (48e7527).
