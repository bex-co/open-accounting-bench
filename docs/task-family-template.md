# Task family template

Copy this structure into your PR description (and keep it in the family
function's docstring). A family is not mergeable until every section is
filled and the checklist passes. Workflow: [CONTRIBUTING.md](../CONTRIBUTING.md).

## 1. Scenario

- Business event in one paragraph: who did what, when, for how much.
- Evidence given to the agent (files under `/app`, e.g. receipt,
  statement, statute excerpt). Every fact the oracle needs must appear
  in evidence or in `/app/policy.md` — nothing may hinge on unstated
  assumptions.
- Taxonomy: `category`, `framework`, `level` (scored with the
  [level rubric](task-families.md#assigning-level); list the seven
  dimension scores and flag borderline), `format`, `skill` (closed
  vocabularies in `oab.families.TAXONOMY`; extend the vocabulary in
  the same PR if a new value is genuinely needed), plus `standards`
  references (`asc:606`, `ias:23`, …) when a standard governs the
  answer.
- Crosswalk: proposed `[[mapping]]` records in `crosswalks/` for the
  blueprint/syllabus items the generator touches (or a note that none
  apply).

## 2. Oracle derivation

- How the expected outcome is computed from the generated facts
  (journal entries: account deltas; choice: gold option ids; numeric:
  formula and tolerances). The oracle must be derivable by a second
  accountant from the evidence alone.
- What varies with the seed (amounts, dates, names, option order...)
  and what stays fixed. Same seed must reproduce the task byte-for-byte.

## 3. Trap

- The most plausible wrong attempt (balanced-but-misclassified entry,
  duplicate recording, attractive distractor, off-by-one period...).
- Which verifier layer/dimension catches it, and the test that proves
  it. A family whose only failure mode is a syntax error is too easy.

## 4. Equivalent representations

- Other correct ways to reach the graded state (elided postings,
  combined vs split entries, option order) and why grading accepts
  them. If a representation is intentionally rejected, say why.

## 5. Review sign-off

- Accounting reviewer (name/role) confirmed: scenario realistic,
  policy wording unambiguous, oracle correct, trap genuinely plausible.
- Provenance: all names/amounts synthetic; any adapted material added
  to `PROVENANCE.md`.

## Checklist (machine gates run by `oab validate` + CI)

- [ ] Registered in `FAMILIES` with a Stable seed in `STABLE_SEEDS`
- [ ] Oracle scores reward 1; untouched initial state scores 0
- [ ] Trap test added under `tests/` and fails the intended layer
- [ ] `uv run oab generate --all` leaves no uncommitted diff
- [ ] `harbor run -p tasks/<task-id> -a oracle` passes; `-a nop` fails
- [ ] Coverage matrix row updated in `docs/task-families.md`
- [ ] `uv run oab crosswalk` passes with the new mappings
