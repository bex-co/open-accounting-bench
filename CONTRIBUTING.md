# Contributing

## Setup

```bash
uv sync --group dev
uv run pytest
uv run oab validate
```

Requires Python ≥ 3.11. The `oab` package has no runtime dependencies.
Docker + [Harbor](https://docs.harborframework.com/getting-started/installation)
are needed only to execute tasks end-to-end.

## Adding a task family

Fill in [docs/task-family-template.md](docs/task-family-template.md)
(scenario, oracle derivation, trap, equivalents, review) as part of
the PR, then:

1. Implement `family_fn(seed) -> TaskInstance` in `src/oab/families.py`
   (copy an existing family). Use `random.Random(seed)` only — same
   seed must give a byte-identical instance. Professional workflow
   pilots instead start in `src/oab/workflow_families.py`.
2. Register a Stable family in `FAMILIES` and pick its seed in
   `STABLE_SEEDS`. Register a workflow pilot in `DYNAMIC_FAMILIES`
   with no Stable seed; promotion to `FAMILIES` is a later explicit
   step after calibration.
3. State expectations as accounting state (`expected_deltas`, final
   balances, reconciliation; workflow determinations and typed checks),
   never as exact ledger text. Allow equivalent decompositions with
   ranges where they exist.
4. Include a trap: at least one balanced-but-wrong attempt must fail a
   non-structural layer. Add it to `tests/test_verifier.py`.
5. Regenerate and verify:

   ```bash
   uv run oab generate --all
   uv run oab validate
   harbor run -p tasks/<task-id> -a oracle   # must score reward 1
   uv run pytest
   ```

   For a Dynamic workflow pilot, also generate representative seeds
   outside `tasks/`, run `oab validate` on that output directory, and
   check oracle, no-op, mutant, and equivalent submissions in tests.

6. Accounting review (deferred): add the family to
   [TO_REVIEW.md](TO_REVIEW.md) with what a reviewer should check.
   Merging does not wait for it; a reviewer with accounting background
   later confirms the scenario, policy wording, and oracle, and the
   entry moves to the file's Reviewed section.

Do not hand-edit anything under `tasks/<task-id>/` — it is generated.
Do not edit `tasks/*/tests/grader.py` — it is a verbatim copy of
`src/oab/_verifier_core.py` (edit the core, then regenerate).

## Changing the verifier

Verifier changes affect every score ever reported. They require:
failing test first, full test suite green, `GENERATOR_VERSION`
consideration (see docs/governance.md), and regenerated tasks in the
same PR.

## Style

`uv run ruff check src tests` and `uv run ruff format --check src tests`
must pass (CI enforces). Keep the verifier core stdlib-only and
single-file — it runs hermetically inside verifier containers.
