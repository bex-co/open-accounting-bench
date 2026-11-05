# w2 · m5 — Machine-readable review registry and reviewed-only reporting

**Worker:** worker2 **Goal:** Each Stable task carries its accounting-review status, review lapses automatically when a generator's semantics change, and reports can be restricted to reviewed tasks. **Status:** done

## Tasks (in order)

| id   | title | est | depends_on |
| ---- | ----- | --- | ---------- |
| t001 | Review registry with CI validation — **DONE** | 60m | — |
| t002 | Carry review status into the manifest — **DONE** | 45m | t001 |
| t003 | `oab report --reviewed-only` — **DONE** | 45m | t002 |
| t004 | Adoption surface — **DONE** | 20m | t003 |
| t005 | Simplify — **DONE** | 15m | t004 |
| t006 | Test coverage — **DONE** | 20m | t004 |
| t007 | Closeout — **DONE** | 10m | t006 |

## Definition of done

Every Stable task in `tasks/manifest.json` has a review status; CI rejects registry drift; `oab report` prints the reviewed share and supports `--reviewed-only`.

## Source + Goal linkage

- **Source:** brainstorm 2026-11-04 (`/pm-brainstorm for w2`, lessons from accounting benchmarks catalogued by benchmark-radar); the open beancount-ledger environment states plainly that its accounting carries an AI plausibility review, not a practising accountant's sign-off.
- **Goal linkage:** B1/B3 — turns deferred review from a convention into data, so anyone citing OAB can state how much of a score rests on professionally reviewed tasks.
- **Expected outcome:** Report consumers can separate reviewed from pending tasks; reviewers see exactly which families lapsed after a generator change.
- **Why now:** The pending backlog is large and earlier reviews found committed answers that were wrong; without a status field, outside users cannot tell which scores to trust.
- **Closing tasks:** Adoption surface included (manifest field and report flag). Accounting review omitted: no accounting semantics change.
