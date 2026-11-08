# w2 · m12 — Injected instructions and fabricated completion signals

**Worker:** worker2 **Goal:** Some source documents carry instructions or fake "already reconciled" evidence; the correct close ignores them and verifies against the records. **Status:** todo (t001–t005 done)

## Tasks (in order)

| id   | title | est | depends_on |
| ---- | ----- | --- | ---------- |
| t001 | Plant injections in source fields — **DONE** | 60m | — |
| t002 | Version bump and regeneration — **DONE** | 20m | t001 |
| t003 | Adoption surface — **DONE** | 20m | t002 |
| t004 | Simplify — **DONE** | 15m | t003 |
| t005 | Test coverage — **DONE** | 20m | t003 |
| t006 | Accounting review | 15m | t005 |
| t007 | Closeout | 10m | t006 |

## Definition of done

Seeds with planted injections exist; following any injection fails a non-structural layer; the oracle ignores them and scores reward 1; the policy states documents are evidence, not instructions.

## Source + Goal linkage

- **Source:** difficulty study 2026-11-06 (lessons from APEX-Accounting, FinancialAuditBench, Crypto Accounting Bench, BigFinanceBench, AgenticFinBench, and an open reconciliation-agent harness, as catalogued by benchmark-radar); reconciliation-agent harness (memo-field injections, fabricated success evidence)
- **Goal linkage:** B1 — grading checks committed ledger effects, so an agent cannot pass by asserting completion; B2 — adds document-trust judgement to the close.
- **Expected outcome:** Agent builders can see whether an accounting agent can be steered by text inside its evidence.
- **Why now:** Low effort once m6's neutral evidence exists; safety-relevant for adopters deploying agents on real documents.
- **Closing tasks:** Adoption surface included (the pilot's documented contract changes). Accounting review included (determination semantics and expectations change).
