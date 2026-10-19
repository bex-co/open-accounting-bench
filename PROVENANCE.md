# Provenance

All Open Accounting Bench scenarios, ledgers, and source documents are
original synthetic data created for this project (fictional companies
such as "Acme Widgets LLC", generated amounts/dates from recorded
seeds). No real financial records, examination papers, or third-party
datasets are included or derived from.

**Scope of the license.** The Apache-2.0 license in this repository
covers the project's own contributions: task generators, task
specifications, verifiers, documentation, and curation. It does not
relicense third-party software referenced at runtime:

| Component | Role | License |
|---|---|---|
| [Harbor](https://docs.harborframework.com/) | Task format & execution harness | See Harbor project |
| [Beancount](https://beancount.github.io/) | Reference ledger syntax/engine | GPL-2.0 (not bundled; ledgers here are plain text data) |
| [DeepSWE](https://github.com/datacurve-ai/deep-swe) | Repository-layout precedent (no code copied; layout conventions adapted) | Apache-2.0 |
| Python 3.12 slim images | Task/verifier containers | PSF + image terms |

If a future task family builds on external material, add a row here
with its source and license before merging.
