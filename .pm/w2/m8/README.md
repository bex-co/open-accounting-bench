# w2 · m8 — "Insufficient evidence" determinations

**Worker:** worker2 **Goal:** Some issues lack decisive evidence by construction; the correct answer is to flag them and post nothing. **Status:** todo (t001, t002 done)

## Tasks (in order)

| id   | title | est | depends_on |
| ---- | ----- | --- | ---------- |
| t001 | Disclose an insufficient-evidence disposition — **DONE** | 30m | — |
| t002 | Generate items with missing decisive evidence — **DONE** | 60m | t001 |
| t003 | Version bump and regeneration | 20m | t002 |
| t004 | Adoption surface | 20m | t003 |
| t005 | Simplify | 15m | t004 |
| t006 | Test coverage | 20m | t004 |
| t007 | Accounting review | 15m | t006 |
| t008 | Closeout | 10m | t007 |

## Definition of done

Seeds with withheld evidence exist; their oracle flags the items and posts nothing for them; estimating from partial evidence fails a non-structural layer.

## Source + Goal linkage

- **Source:** difficulty study 2026-11-06 (lessons from APEX-Accounting, FinancialAuditBench, Crypto Accounting Bench, BigFinanceBench, AgenticFinBench, and an open reconciliation-agent harness, as catalogued by benchmark-radar); FinancialAuditBench failure analysis (reluctance to leave items open 22%)
- **Goal linkage:** B2 — measures professional restraint (not completing work the evidence does not support); B1 — graded by disposition plus forbidden deltas, no judgement call by the grader.
- **Expected outcome:** Agent builders see whether an agent fabricates closure when evidence is missing.
- **Why now:** Builds on m6's neutral evidence; complements the clean-month control (nothing to do) with "cannot do".
- **Closing tasks:** Adoption surface included (the pilot's documented contract changes). Accounting review included (determination semantics and expectations change).
