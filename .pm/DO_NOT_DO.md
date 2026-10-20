# `.pm` anti-goals — do not do

Hard constraints for the roadmap board. `/pm-brainstorm` and `/pm` read this before proposing or materializing work, and must reject conflicting items explicitly. Each rule restates a commitment already made in the repository's public docs; the source is cited so the rule can be checked against it.

- **No holdout leakage.** Never put Holdout-track families, seeds, expectations, or anything that reconstructs them on the board, in commits, or anywhere else in this public repo. Public replication of Stable/Dynamic tracks never depends on holdout access. ([docs/governance.md](../docs/governance.md))
- **No real or copied data.** No real financial records, no copied examination materials, no third-party datasets. Every company, person, and document is synthetic; external material needs a provenance row before it merges. ([PROVENANCE.md](../PROVENANCE.md), [docs/governance.md](../docs/governance.md))
- **No LLM judge in grading.** Grading is deterministic and state-based. Do not propose scoring that depends on a model's opinion of a ledger. ([README.md](../README.md), [docs/verification.md](../docs/verification.md))
- **No exact-text expectations.** Expectations are accounting state — deltas, balances, reconciliation — never exact ledger text. Equivalent decompositions must pass. ([CONTRIBUTING.md](../CONTRIBUTING.md))
- **No family without a trap, an oracle, and review.** A family whose balanced-but-wrong attempt passes, or that ships without accounting review, does not count toward coverage. ([CONTRIBUTING.md](../CONTRIBUTING.md), [docs/governance.md](../docs/governance.md))
- **No rewriting results.** Historical results stay tied to their generator and scoring versions and are never rewritten. ([docs/governance.md](../docs/governance.md))
- **No dependence on beancount.io infrastructure.** Generating, executing, verifying, and extending evaluations must work for a third party without it, and sponsorship confers no scoring advantage. ([docs/roadmap.md](../docs/roadmap.md), [docs/governance.md](../docs/governance.md))
- **No dependencies in the verifier core.** `_verifier_core.py` stays stdlib-only and single-file; it runs hermetically in verifier containers. ([CONTRIBUTING.md](../CONTRIBUTING.md))
- **No secrets on the board.** No credentials, tokens, API keys, internal URLs, or references to private repositories in any `.pm/` file.
- **No task-count theater.** The alpha's success criterion is not task count. Don't add families or milestones to make the numbers or the board look busy; if it isn't >1h of real work with an observable outcome, it's an inbox note or nothing. ([docs/roadmap.md](../docs/roadmap.md))
