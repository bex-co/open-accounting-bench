# w1 · m1 — Receivable allowance true-up family

**Worker:** worker1 **Goal:** Ship the `receivable-allowance-trueup` task family with trap, oracle, Stable task, docs, and crosswalk mappings, accounting-reviewed. **Status:** done

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

`receivable-allowance-trueup` is on `main`: registered generator with a Stable seed, regenerated task passing `oab validate` (oracle 1, nop 0), a trap test failing a non-structural layer, docs and crosswalk updated, and a TO_REVIEW.md entry (review deferred per 55f8abe).

## Sketch (from w1/002)

- **Crosswalk:** FAR.II.B#1, FA.D8(h), FA.D8(e). **Framework:** core. **Level/skill:** university / application.
- **Scenario:** Month-end. Ledger has receivables by customer and an existing allowance balance. `documents/aging.md` buckets open invoices; `policy.md` gives loss rates per bucket and says one named customer's invoice is uncollectible and must be written off first.
- **Oracle:** write-off (Dr Allowance, Cr Receivables for the named invoice), then adjust allowance to rate × buckets on the remaining balances: Dr Bad-debt expense / Cr Allowance by the *difference* from the post-write-off balance. Required final balances: receivables, allowance.
- **Trap:** book the full required allowance as expense (ignore the existing balance), or expense the write-off directly. Balanced; fails semantic accuracy (expense delta) and the allowance final balance.

## Source + Goal linkage

- **Source:** inbox note w1/002 (crosswalk gap analysis).
- **Goal linkage:** B2 — a reviewed family covering a measured coverage gap.
- **Expected outcome:** evaluators can measure agents on this accounting task; crosswalk coverage gains a linked item.
- **Why now:** top of the gap-ranked candidate list; independent of other open work. Adoption surface included (new task in README/docs); Accounting review included (new family).

## Blocked

- t007 was blocked on accounting review; cleared 2026-10-23 when review became deferred (55f8abe): the family is listed in TO_REVIEW.md.
