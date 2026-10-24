# w1 · m3 — Supplier statement reconciliation family

**Worker:** worker1 **Goal:** Ship the `payables-statement-recon` task family with trap, oracle, Stable task, docs, and crosswalk mappings, accounting-reviewed. **Status:** done

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

`payables-statement-recon` is on `main`: registered generator with a Stable seed, regenerated task passing `oab validate` (oracle 1, nop 0), a trap test failing a non-structural layer, docs and crosswalk updated, and a TO_REVIEW.md entry (review deferred per 55f8abe).

## Sketch (from w1/004)

- **Crosswalk:** FA.E2(c–e), FAR.II.G#4, FA.D8(k). **Framework:** core. **Level/skill:** university / analysis.
- **Scenario:** Supplier statement vs the payables ledger for one vendor. Differences: an invoice in transit (on statement, goods not yet received — timing, no entry), a payment recorded in the ledger not yet on the statement (timing), a credit note on the statement never recorded (error), and a transposition in a recorded invoice (error).
- **Oracle:** entries only for the two errors; final payables balance = statement balance ± timing items (stated in policy).
- **Trap:** post every difference so the ledger equals the statement. Balanced; fails semantic accuracy (timing items booked) and reconciliation.
- **Note:** first natural candidate for `audit-assurance` variants (investigate-before-adjusting).

## Source + Goal linkage

- **Source:** inbox note w1/004 (crosswalk gap analysis).
- **Goal linkage:** B2 — a reviewed family covering a measured coverage gap.
- **Expected outcome:** evaluators can measure agents on this accounting task; crosswalk coverage gains a linked item.
- **Why now:** top of the gap-ranked candidate list; independent of other open work. Adoption surface included (new task in README/docs); Accounting review included (new family).

## Blocked

- t007 was blocked on accounting review; cleared 2026-10-23 when review became deferred (55f8abe): the family is listed in TO_REVIEW.md.
