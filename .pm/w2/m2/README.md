# w2 · m2 — Clean-month negative controls

**Worker:** worker2 **Goal:** The month-end close workflow can generate a month with nothing to fix, where the correct answer is to leave the ledger unchanged, and reports an over-action rate. **Status:** todo (t001–t005 done)

## Tasks (in order)

| id   | title | est | depends_on |
| ---- | ----- | --- | ---------- |
| t001 | Allow zero-anomaly evidence packs — **DONE** | 45m | — |
| t002 | Add a clean-month variant to the month-end close workflow — **DONE** | 75m | t001 |
| t003 | Over-action trap — **DONE** | 45m | t002 |
| t004 | Report the over-action rate — **DONE** | 30m | t002 |
| t005 | Adoption surface — **DONE** | 20m | t003, t004 |
| t006 | Simplify | 15m | t005 |
| t007 | Test coverage | 20m | t005 |
| t008 | Accounting review | 15m | t007 |
| t009 | Closeout | 10m | t008 |

## Definition of done

Dynamic seeds can generate a clean-month variant; the no-op oracle scores reward 1; an over-action attempt fails a non-structural layer; `oab report` shows an over-action rate.

## Source + Goal linkage

- **Source:** brainstorm 2026-11-04 (`/pm-brainstorm for w2`, lessons from accounting benchmarks catalogued by benchmark-radar); clean-month assurance tasks in the open beancount-ledger environment.
- **Goal linkage:** B1 — adds negative controls so the grade distinguishes doing nothing correctly from doing something unnecessary.
- **Expected outcome:** Agent builders can measure how often an agent changes a ledger that needed no change, a deployment risk that no current task measures.
- **Why now:** The month-end close pilot is being calibrated now; negative controls should be in the calibration panel before any promote decision. Depends on the in-flight recalibration being committed first, since it touches the same file.
- **Closing tasks:** Adoption surface included (new variant and report metric). Accounting review included (new determination semantics).
