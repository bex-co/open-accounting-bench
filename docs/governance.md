# Governance

Open Accounting Bench is a neutral, vendor-independent evaluation
project, founded and initially maintained by beancount.io.
Infrastructure sponsorship confers no scoring advantage: task
definitions, generators, verifiers, and Stable/Dynamic protocols are
public under Apache-2.0, and results must be independently
reproducible from `(family, seed, generator_version)`.

## Versioning

- Benchmark releases are tagged (`v0.1.0`, …); historical results stay
  tied to their generator/scoring versions and are never rewritten.
- Changing a family's accounting semantics or expectations bumps
  `GENERATOR_VERSION` and regenerates Stable tasks in the same PR.
- Taxonomy metadata (new vocabulary values, `skill`, `standards`)
  changes task digests but not accounting semantics or expectations:
  regenerate Stable tasks in the same PR, no `GENERATOR_VERSION`
  bump.
- Crosswalks (`crosswalks/`) are versioned per external edition and
  never rewritten; a new edition is a new file. They do not touch
  tasks or scores.
- Verifier changes require the full oracle/nop/adversarial test suite
  to pass; scoring disputes are settled by failing-test-first PRs.

## Holdout track

A holdout (unpublished families/seeds) may be used to detect
overfitting to public generators. Its purpose, size, family coverage,
and evaluation conditions are documented here before first use;
holdout *results reporting* follows the same metrics as public tracks.
Public replication of Stable/Dynamic tracks never depends on holdout
access.

## Contributions & review

New families need: generator + oracle tests, an adversarial case,
expert accounting review (a maintainer with accounting background or
an external reviewer), and provenance notes confirming original
synthetic data. See [CONTRIBUTING.md](../CONTRIBUTING.md).

## Data policy

No real financial records, no copied examination materials. All
companies, people, and documents are synthetic
([PROVENANCE.md](../PROVENANCE.md)). Canary strings in instructions
support contamination detection; do not train on this benchmark.
