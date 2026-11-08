# w2 · m11 — Cross-period schedules and accruals

**Worker:** worker2 **Goal:** Close issues span the three generated periods: unreversed prior accruals, multi-period amortization roll-forwards, and prior-period errors corrected now. **Status:** todo

## Tasks (in order)

| id   | title | est | depends_on |
| ---- | ----- | --- | ---------- |
| t001 | Prior-period issues in the pack | 75m | — |
| t002 | Version bump and regeneration | 20m | t001 |
| t003 | Adoption surface | 20m | t002 |
| t004 | Simplify | 15m | t003 |
| t005 | Test coverage | 20m | t003 |
| t006 | Accounting review | 15m | t005 |
| t007 | Closeout | 10m | t006 |

## Definition of done

At least three cross-period issues are live with prior-period evidence; double-reversal and current-period-only traps fail; gates and the 0-39 sweep pass.

## Source + Goal linkage

- **Source:** difficulty study 2026-11-06 (lessons from APEX-Accounting, FinancialAuditBench, Crypto Accounting Bench, BigFinanceBench, AgenticFinBench, and an open reconciliation-agent harness, as catalogued by benchmark-radar); APEX category analysis (Schedules & Accruals hardest)
- **Goal linkage:** B2 — the schedule-and-accrual work that discriminates most in comparable close benchmarks.
- **Expected outcome:** The pilot tests period roll-forward, not only single-month adjustments.
- **Why now:** Shares the generator; schedule after m6 and m9.
- **Closing tasks:** Adoption surface included (the pilot's documented contract changes). Accounting review included (determination semantics and expectations change).
