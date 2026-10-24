# w1 · m2 — Accrual and deferred-income reversal family

**Worker:** worker1 **Goal:** Ship the `accrual-deferral-reversal` task family with trap, oracle, Stable task, docs, and crosswalk mappings, accounting-reviewed. **Status:** in progress (t001, t002, t003, t004, t005, t006 done)

## Tasks (in order)

| id   | title | est | depends_on |
| ---- | ----- | --- | ---------- |
| t001 | Implement the generator — **DONE** | 45m | — |
| t002 | Trap, equivalence, and oracle tests — **DONE** | 30m | t001 |
| t003 | Regenerate, document, crosswalk — **DONE** | 30m | t002 |
| t004 | Adoption surface — **DONE** | 15m | t003 |
| t005 | Simplify — **DONE** | 15m | t004 |
| t006 | Test coverage — **DONE** | 15m | t004 |
| t007 | Accounting review — **BLOCKED** | 30m | t006 |
| t008 | Closeout | 10m | t007 |

## Definition of done

`accrual-deferral-reversal` is on `main`: registered generator with a Stable seed, regenerated task passing `oab validate` (oracle 1, nop 0), a trap test failing a non-structural layer, docs and crosswalk updated, and an accounting review on record.

## Sketch (from w1/003)

- **Crosswalk:** FA.D7(a–d), FAR.II.G#2. **Framework:** core. **Level/skill:** university / application.
- **Scenario:** Two-period ledger (prior month closed with an accrued utilities expense and a customer prepayment received). Current month documents: the utility bill arrives (actual differs from accrual); part of the prepaid service is delivered. Policy: reverse prior accruals on day 1; recognize deferred revenue as delivered.
- **Oracle:** reversal entry dated day 1, bill recorded at actual, revenue released for delivered portion only; final balances for accrued liabilities (0), deferred revenue (remaining), utilities expense (actual − reversed accrual effect).
- **Trap:** skip the reversal and book the full bill (double-counts expense), or release all deferred revenue. Fails expense/revenue deltas.

## Source + Goal linkage

- **Source:** inbox note w1/003 (crosswalk gap analysis).
- **Goal linkage:** B2 — a reviewed family covering a measured coverage gap.
- **Expected outcome:** evaluators can measure agents on this accounting task; crosswalk coverage gains a linked item.
- **Why now:** top of the gap-ranked candidate list; independent of other open work. Adoption surface included (new task in README/docs); Accounting review included (new family).

## Blocked

- **t007 Accounting review** (blocked 2026-10-23): the family is complete on branch `family/accrual-deferral-reversal` (6193e0a) but has no accounting sign-off; CONTRIBUTING.md step 6 requires it before merging to main.
  **Unblock:** a reviewer with accounting background checks the scenario (opening balances stand in for December), policy wording (reverse on day 1; revenue per session), oracle, traps, level (university: dependent steps and multi-period scope score U), and the three proposed mappings. Who: a maintainer with accounting background.
  Partial work: t001–t006 done on the branch; nothing merged.
