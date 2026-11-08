# w2 · m7 — Deeper evidence and realistic noise volume

**Worker:** worker2 **Goal:** Decisive facts sit in secondary sources among many plausible but irrelevant files, at APEX/FinancialAuditBench-like volume. **Status:** todo (t001–t005 done)

## Tasks (in order)

| id   | title | est | depends_on |
| ---- | ----- | --- | ---------- |
| t001 | Bury decisive facts in secondary sources — **DONE** | 60m | — |
| t002 | Irrelevant-but-plausible files and volume — **DONE** | 60m | t001 |
| t003 | Version bump and regeneration — **DONE** | 20m | t002 |
| t004 | Adoption surface — **DONE** | 20m | t003 |
| t005 | Simplify — **DONE** | 15m | t004 |
| t006 | Test coverage | 20m | t004 |
| t007 | Accounting review | 15m | t006 |
| t008 | Closeout | 10m | t007 |

## Definition of done

At least five issues require a secondary source (primary-only traps fail); packs carry ~70 files within documented budgets; every distractor maps to a disposition or none; gates and the 0-39 sweep pass.

## Source + Goal linkage

- **Source:** difficulty study 2026-11-06 (lessons from APEX-Accounting, FinancialAuditBench, Crypto Accounting Bench, BigFinanceBench, AgenticFinBench, and an open reconciliation-agent harness, as catalogued by benchmark-radar); FinancialAuditBench failure analysis (insufficient retrieval 25%); APEX file statistics
- **Goal linkage:** B2 — exercises retrieval and evidence selection, the dominant failure class in comparable audit and close benchmarks.
- **Expected outcome:** The pilot measures whether an agent finds evidence, not only whether it applies a rule to evidence it was handed.
- **Why now:** Depends on m6 (same generator, neutral ids); the volume lever only matters once labels no longer point at the answer.
- **Closing tasks:** Adoption surface included (the pilot's documented contract changes). Accounting review included (determination semantics and expectations change).
