# w2 · m6 — De-label the month-end close evidence

**Worker:** worker2 **Goal:** Close sources stop naming the problem: agents must find each issue by comparing raw documents and apply source precedence themselves. **Status:** todo (t001–t005 done)

## Tasks (in order)

| id   | title | est | depends_on |
| ---- | ----- | --- | ---------- |
| t001 | Inventory the answer-leaking fields — **DONE** | 30m | — |
| t002 | Neutral evidence ids and no status columns — **DONE** | 75m | t001 |
| t003 | Derive issues from raw documents — **DONE** | 75m | t002 |
| t004 | Source-reliability precedence without labels — **DONE** | 45m | t003 |
| t005 | Version bump and regeneration — **DONE** | 20m | t004 |
| t006 | Adoption surface | 20m | t005 |
| t007 | Simplify | 15m | t006 |
| t008 | Test coverage | 20m | t006 |
| t009 | Accounting review | 15m | t008 |
| t010 | Closeout | 10m | t009 |

## Definition of done

In every month-end close seed, no app file names an issue or its treatment; each of the 15 issues is derivable from raw sources plus policy; oracle reward 1, no-op 0, and a precedence trap fails on seeds 0-39.

## Source + Goal linkage

- **Source:** difficulty study 2026-11-06 (lessons from APEX-Accounting, FinancialAuditBench, Crypto Accounting Bench, BigFinanceBench, AgenticFinBench, and an open reconciliation-agent harness, as catalogued by benchmark-radar); inspection of `month-end-close-workflow` seed 42 (evidence keys and status columns name the issues)
- **Goal linkage:** B2 — turns the professional pilot from a labelled worksheet into an actual close, which is what makes it discriminate; B1 — keeps every determination deterministic and disclosed.
- **Expected outcome:** Strong models can no longer reach near-full rubric by reading status columns; calibration can measure finding issues, not following labels.
- **Why now:** The 0.8.0 recalibration kept strong tiers at 97-99% mean rubric against a 40-70% target, and inspection shows the evidence names each issue; this is the first tuning lever and the others build on it.
- **Closing tasks:** Adoption surface included (the pilot's documented contract changes). Accounting review included (determination semantics and expectations change).
