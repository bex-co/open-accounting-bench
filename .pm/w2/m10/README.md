# w2 · m10 — Larger chart of accounts with near-miss accounts

**Worker:** worker2 **Goal:** The close chart includes plausible near-miss accounts with stated purposes, so choosing the right account becomes a measured skill. **Status:** todo (t001–t005 done)

## Tasks (in order)

| id   | title | est | depends_on |
| ---- | ----- | --- | ---------- |
| t001 | Add near-miss accounts and their policy — **DONE** | 45m | — |
| t002 | Near-miss traps — **DONE** | 45m | t001 |
| t003 | Version bump and regeneration — **DONE** | 20m | t002 |
| t004 | Adoption surface — **DONE** | 20m | t003 |
| t005 | Simplify — **DONE** | 15m | t004 |
| t006 | Test coverage | 20m | t004 |
| t007 | Accounting review | 15m | t006 |
| t008 | Closeout | 10m | t007 |

## Definition of done

The close chart carries near-miss accounts with stated purposes; near-miss traps fail and are diagnosed `wrong-account`; every oracle posting is uniquely determined by policy.

## Source + Goal linkage

- **Source:** difficulty study 2026-11-06 (lessons from APEX-Accounting, FinancialAuditBench, Crypto Accounting Bench, BigFinanceBench, AgenticFinBench, and an open reconciliation-agent harness, as catalogued by benchmark-radar); Crypto Accounting Bench diagnostics (account selection 56.3%)
- **Goal linkage:** B2 — account selection, the main gap in a comparable journal-entry benchmark; B1 — remains deterministic because policy fixes each account's purpose.
- **Expected outcome:** Reports can show account-choice errors separately from amount errors on the pilot.
- **Why now:** m4 diagnostics shipped, so the effect is measurable immediately.
- **Closing tasks:** Adoption surface included (the pilot's documented contract changes). Accounting review included (determination semantics and expectations change).
