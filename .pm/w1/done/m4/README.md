# w1 · m4 — PP&E disposal family

**Worker:** worker1 **Goal:** Ship the `ppe-disposal` task family with trap, oracle, Stable task, docs, and crosswalk mappings, accounting-reviewed. **Status:** done

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

`ppe-disposal` is on `main`: registered generator with a Stable seed, regenerated task passing `oab validate` (oracle 1, nop 0), a trap test failing a non-structural layer, docs and crosswalk updated, and a TO_REVIEW.md entry (review deferred per 55f8abe).

## Sketch (from w1/005)

- **Crosswalk:** FAR.II.D#2, FAR.II.D#1, FA.D4(e–f), FA.D5(b), FA.D5(d). **Framework:** core. **Level/skill:** university / application.
- **Scenario:** Ledger holds an asset at cost with accumulated depreciation to last year-end. Policy: straight-line, monthly, residual value stated. Sale document: sold on a mid-year date for cash.
- **Oracle:** depreciation to disposal date, then derecognize cost and accumulated depreciation, record cash and gain/loss. Final balances: asset cost 0, accumulated depreciation 0, gain/loss amount.
- **Trap:** compute gain/loss on last year-end carrying amount (skip current-year depreciation). Balanced; fails depreciation/gain deltas.

## Source + Goal linkage

- **Source:** inbox note w1/005 (crosswalk gap analysis).
- **Goal linkage:** B2 — a reviewed family covering a measured coverage gap.
- **Expected outcome:** evaluators can measure agents on this accounting task; crosswalk coverage gains a linked item.
- **Why now:** top of the gap-ranked candidate list; independent of other open work. Adoption surface included (new task in README/docs); Accounting review included (new family).

## Blocked

- t007 was blocked on accounting review; cleared 2026-10-23 when review became deferred (55f8abe): the family is listed in TO_REVIEW.md.
