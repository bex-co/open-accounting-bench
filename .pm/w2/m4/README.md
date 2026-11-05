# w2 · m4 — Account-vs-amount failure diagnostics

**Worker:** worker2 **Goal:** Every journal-entry grade classifies each expected change as correct, right amount in the wrong account, right account with the wrong amount, missing, or extra, without changing the reward. **Status:** todo (t001–t006 done)

## Tasks (in order)

| id   | title | est | depends_on |
| ---- | ----- | --- | ---------- |
| t001 | Failing tests for the diagnostic classes — **DONE** | 45m | — |
| t002 | Implement the diagnostic in the verifier core — **DONE** | 75m | t001 |
| t003 | Regenerate tasks — **DONE** | 15m | t002 |
| t004 | Aggregate diagnostics in `oab report` — **DONE** | 45m | t002 |
| t005 | Adoption surface — **DONE** | 20m | t003, t004 |
| t006 | Simplify — **DONE** | 15m | t005 |
| t007 | Test coverage | 20m | t005 |
| t008 | Closeout | 10m | t007 |

## Definition of done

The grader emits a per-change diagnostic class; rewards are byte-identical to before on the full suite; `oab report` shows class shares per family.

## Source + Goal linkage

- **Source:** brainstorm 2026-11-04 (`/pm-brainstorm for w2`, lessons from accounting benchmarks catalogued by benchmark-radar); Crypto Accounting Bench found 97.8% base-amount agreement but 56.3% deciding-account accuracy.
- **Goal linkage:** B1 — makes grades explainable: separates choosing the wrong account from computing the wrong amount, and shows which error each family's trap actually catches.
- **Expected outcome:** Researchers can say why a model fails; family authors can see whether their trap discriminates on account choice or arithmetic.
- **Why now:** Lands best before the first baseline runs so published baselines carry diagnostics from day one.
- **Closing tasks:** Adoption surface included (new grader output and report table). Accounting review omitted: reward and expectations are unchanged; the diagnostic is informational. If implementation would change any reward, stop and add an Accounting review task.
