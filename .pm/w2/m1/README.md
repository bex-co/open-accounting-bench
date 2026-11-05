# w2 · m1 — Verifier false-accept/reject audit and adversarial suite

**Worker:** worker2 **Goal:** Every Stable task carries a measured false-accept and false-reject count from a reproducible mutation audit, and CI guards against regressions. **Status:** todo (t001, t002 done)

## Tasks (in order)

| id   | title | est | depends_on |
| ---- | ----- | --- | ---------- |
| t001 | Define mutation operators per answer format — **DONE** | 60m | — |
| t002 | Implement `oab audit` — **DONE** | 75m | t001 |
| t003 | Run the full audit and resolve every finding | 90m | t002 |
| t004 | Add a sampled audit to CI | 30m | t002 |
| t005 | Publish audit results | 30m | t003 |
| t006 | Adoption surface | 20m | t004, t005 |
| t007 | Simplify | 15m | t006 |
| t008 | Test coverage | 20m | t006 |
| t009 | Accounting review | 15m | t008 |
| t010 | Closeout | 10m | t009 |

## Definition of done

`oab audit` reports false-accept and false-reject counts for every Stable task; all misjudgements are fixed or documented as known limits; a sampled audit runs in CI; `docs/verification.md` publishes the measured rates.

## Source + Goal linkage

- **Source:** brainstorm 2026-11-04 (`/pm-brainstorm for w2`, lessons from accounting benchmarks catalogued by benchmark-radar); `docs/roadmap.md` Days 31–60 (verifier false-accept/reject audit) and Days 61–90 (adversarial set); exploit-oracle practice in the open beancount-ledger environment.
- **Goal linkage:** B1 — measures directly whether balanced-but-wrong answers fail and equivalent correct ones pass, across the whole Stable set rather than one trap per family.
- **Expected outcome:** Labs citing OAB scores can cite a public, reproducible misjudgement rate; contributors get a regression gate for verifier changes.
- **Why now:** Close to 300 Stable families exist and no systematic audit has run; baseline runs (roadmap Days 1–30) should not be published on an unaudited grader.
- **Closing tasks:** Adoption surface included (new `oab audit` command and published rates). Accounting review included because t003 may change verifier scoring; if it does not, the task records that and closes.
