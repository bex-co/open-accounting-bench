# w1 · m6 — Bundle revenue allocation family

**Worker:** worker1 **Goal:** Ship the `revenue-bundle-allocation` task family with trap, oracle, Stable task, docs, and crosswalk mappings, accounting-reviewed. **Status:** todo

## Tasks (in order)

| id   | title | est | depends_on |
| ---- | ----- | --- | ---------- |
| t001 | Implement the generator | 45m | — |
| t002 | Trap, equivalence, and oracle tests | 30m | t001 |
| t003 | Regenerate, document, crosswalk | 30m | t002 |
| t004 | Adoption surface | 15m | t003 |
| t005 | Simplify | 15m | t004 |
| t006 | Test coverage | 15m | t004 |
| t007 | Accounting review | 30m | t006 |
| t008 | Closeout | 10m | t007 |

## Definition of done

`revenue-bundle-allocation` is on `main`: registered generator with a Stable seed, regenerated task passing `oab validate` (oracle 1, nop 0), a trap test failing a non-structural layer, docs and crosswalk updated, and an accounting review on record.

## Sketch (from w1/007)

- **Crosswalk:** FAR.III.C#4; converged ASC 606 / IFRS 15 (`asc:606`, `ifrs:15`). **Framework:** core (converged). **Level/skill:** professional / application.
- **Scenario:** A contract sells hardware plus 12 months of support for one price; policy lists standalone selling prices. Hardware delivered at signing; one month of support elapsed at period end. Cash received up front.
- **Oracle:** allocate the price by relative standalone prices; recognize hardware revenue plus one month of support; remainder to contract liability.
- **Trap:** allocate using the invoice line prices (or recognize all at signing). Fails revenue and contract-liability balances.

## Source + Goal linkage

- **Source:** inbox note w1/007 (crosswalk gap analysis).
- **Goal linkage:** B2 — a reviewed family covering a measured coverage gap.
- **Expected outcome:** evaluators can measure agents on this accounting task; crosswalk coverage gains a linked item.
- **Why now:** top of the gap-ranked candidate list; independent of other open work. Adoption surface included (new task in README/docs); Accounting review included (new family).
