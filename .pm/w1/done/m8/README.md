# w1 · m8 — Effective-interest loan family

**Worker:** worker1 **Goal:** Ship the `loan-effective-interest` task family with trap, oracle, Stable task, docs, and crosswalk mappings, accounting-reviewed. **Status:** done

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

`loan-effective-interest` is on `main`: registered generator with a Stable seed, regenerated task passing `oab validate` (oracle 1, nop 0), a trap test failing a non-structural layer, docs and crosswalk updated, and a TO_REVIEW.md entry (review deferred per 55f8abe).

## Sketch (from w1/009)

- **Crosswalk:** FAR.II.H.1#3, FAR.II.H.1#4, FA.D10(j). **Framework:** core (amortized cost is shared by US GAAP and IFRS 9). **Level/skill:** professional / application.
- **Scenario:** Loan received net of issuance costs; policy states the effective rate (given, not to be solved) and monthly accrual; first coupon not yet paid at period end.
- **Oracle:** interest expense = carrying amount × effective rate / 12; accrued coupon payable at stated rate; difference adjusts the carrying amount. Final balances: loan carrying amount, interest payable, interest expense.
- **Trap:** accrue at the coupon rate on face value (or expense issuance costs). Fails expense and carrying-amount balances.

## Source + Goal linkage

- **Source:** inbox note w1/009 (crosswalk gap analysis).
- **Goal linkage:** B2 — a reviewed family covering a measured coverage gap.
- **Expected outcome:** evaluators can measure agents on this accounting task; crosswalk coverage gains a linked item.
- **Why now:** top of the gap-ranked candidate list; independent of other open work. Adoption surface included (new task in README/docs); Accounting review included (new family).

## Blocked

- t007 was blocked on accounting review; cleared 2026-10-23 when review became deferred (55f8abe): the family is listed in TO_REVIEW.md.
