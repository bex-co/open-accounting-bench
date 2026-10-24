# w1 · m5 — Inventory costing and NRV write-down family

**Worker:** worker1 **Goal:** Ship the `inventory-costing-nrv` task family with trap, oracle, Stable task, docs, and crosswalk mappings, accounting-reviewed. **Status:** done

## Tasks (in order)

| id   | title | est | depends_on |
| ---- | ----- | --- | ---------- |
| t001 | Implement the generator — **DONE** | 45m | — |
| t002 | Trap, equivalence, and oracle tests — **DONE** | 30m | t001 |
| t003 | Regenerate, document, crosswalk — **DONE** | 30m | t002 |
| t004 | Adoption surface — **DONE** | 15m | t003 |
| t005 | Simplify — **DONE** | 15m | t004 |
| t006 | Test coverage — **DONE** | 15m | t004 |
| t007 | Accounting review — **DONE** | 30m | t006 |
| t008 | Closeout — **DONE** | 10m | t007 |

## Definition of done

`inventory-costing-nrv` is on `main`: registered generator with a Stable seed, regenerated task passing `oab validate` (oracle 1, nop 0), a trap test failing a non-structural layer, docs and crosswalk updated, and a TO_REVIEW.md entry (review deferred per 55f8abe).

## Sketch (from w1/006)

- **Crosswalk:** FAR.II.C#1, FAR.II.C#2, FA.D3(b), FA.D3(c), FA.D3(f). **Framework:** core (FIFO / weighted average only — no LIFO, keeping it framework-neutral). **Level/skill:** university / application.
- **Scenario:** Purchases and sales log for one SKU in a month under a stated perpetual weighted-average (or FIFO) policy; year-end NRV quote below cost for the remaining units.
- **Oracle:** COGS and ending inventory under the stated method, then write-down to NRV. Numeric answer (COGS, ending inventory) or journal-entry variant.
- **Trap:** periodic average when policy says perpetual (or vice versa); skip the write-down. Fails numeric/semantic layers.

## Source + Goal linkage

- **Source:** inbox note w1/006 (crosswalk gap analysis).
- **Goal linkage:** B2 — a reviewed family covering a measured coverage gap.
- **Expected outcome:** evaluators can measure agents on this accounting task; crosswalk coverage gains a linked item.
- **Why now:** top of the gap-ranked candidate list; independent of other open work. Adoption surface included (new task in README/docs); Accounting review included (new family).

## Blocked

- t007 was blocked on accounting review; cleared 2026-10-23 when review became deferred (55f8abe): the family is listed in TO_REVIEW.md.
