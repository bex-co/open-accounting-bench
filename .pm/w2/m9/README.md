# w2 · m9 — Longer downstream dependency chains

**Worker:** worker2 **Goal:** More close issues change a later computation, so dropping or contradicting an intermediate result fails downstream checks. **Status:** todo (t001–t004 done)

## Tasks (in order)

| id   | title | est | depends_on |
| ---- | ----- | --- | ---------- |
| t001 | Design dependency chains — **DONE** | 45m | — |
| t002 | Implement the chains — **DONE** | 75m | t001 |
| t003 | Version bump and regeneration — **DONE** | 20m | t002 |
| t004 | Adoption surface — **DONE** | 20m | t003 |
| t005 | Simplify | 15m | t004 |
| t006 | Test coverage | 20m | t004 |
| t007 | Accounting review | 15m | t006 |
| t008 | Closeout | 10m | t007 |

## Definition of done

At least four dependency chains are live; a mutant that applies only the first link of each fails that chain's downstream determination; gates and the 0-39 sweep pass.

## Source + Goal linkage

- **Source:** difficulty study 2026-11-06 (lessons from APEX-Accounting, FinancialAuditBench, Crypto Accounting Bench, BigFinanceBench, AgenticFinBench, and an open reconciliation-agent harness, as catalogued by benchmark-radar); APEX failure analysis (intermediate results dropped downstream); FinancialAuditBench (effects of changes 17%)
- **Goal linkage:** B2 — multi-step close work where consistency across steps is graded; B1 — downstream errors become visible per cluster.
- **Expected outcome:** Results separate agents that keep intermediate results consistent from those that solve items in isolation.
- **Why now:** Independent of m7/m8 but shares the generator; schedule after m6.
- **Closing tasks:** Adoption surface included (the pilot's documented contract changes). Accounting review included (determination semantics and expectations change).
