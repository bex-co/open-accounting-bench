# w1 · m7 — Suspense (clearing) account clearance family

**Worker:** worker1 **Goal:** Ship the `suspense-clearance` task family with trap, oracle, Stable task, docs, and crosswalk mappings, accounting-reviewed. **Status:** todo

## Tasks (in order)

| id   | title | est | depends_on |
| ---- | ----- | --- | ---------- |
| t001 | Implement the generator | 45m | — |
| t002 | Trap, equivalence, and oracle tests | 30m | t001 |
| t003 | Regenerate, document, crosswalk | 30m | t002 |
| t004 | Adoption surface | 15m | t003 |
| t005 | Simplify | 15m | t004 |
| t006 | Test coverage | 15m | t004 |
| t007 | Accounting review | 30m | t006 |
| t008 | Closeout | 10m | t007 |

## Definition of done

`suspense-clearance` is on `main`: registered generator with a Stable seed, regenerated task passing `oab validate` (oracle 1, nop 0), a trap test failing a non-structural layer, docs and crosswalk updated, and an accounting review on record.

## Sketch (from w1/008)

- **Crosswalk:** FA.F3(c–d), FA.F2(c), FAR.III.A#1. **Framework:** core. **Level/skill:** vocational / analysis.
- **Scenario:** A suspense balance from an unbalanced import; controller memo lists two findings (a one-sided posting and a transposed amount). Append-only policy.
- **Oracle:** correcting entries that clear suspense to zero and fix the affected accounts.
- **Trap:** clear suspense to a plausible but wrong account (e.g. sundry expense). Balanced; fails semantic accuracy.
- **Note:** "suspense account" is UK/IFRS-teaching vocabulary; phrase instruction neutrally ("clearing account").

## Source + Goal linkage

- **Source:** inbox note w1/008 (crosswalk gap analysis).
- **Goal linkage:** B2 — a reviewed family covering a measured coverage gap.
- **Expected outcome:** evaluators can measure agents on this accounting task; crosswalk coverage gains a linked item.
- **Why now:** top of the gap-ranked candidate list; independent of other open work. Adoption surface included (new task in README/docs); Accounting review included (new family).
