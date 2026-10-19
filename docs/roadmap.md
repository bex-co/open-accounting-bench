# 90-day roadmap (from memo §12)

## Days 1–30 — Verification foundation (done in this initialization)

- [x] Harbor integration: task format, separate verifier, artifacts.
- [x] Five-layer deterministic verifier; balanced-but-wrong entries fail.
- [x] First 4 task families (one per v0.1 category) + oracles.
- [x] Seed-deterministic generation; Stable instances committed.
- [ ] Run first agents end-to-end via Harbor; record baseline job.
- [ ] Optional `bean-check` cross-validation of the ledger subset.

## Days 31–60 — Dynamic evaluation pipeline

- [ ] 8–10 validated generators; generated source documents (CSV/PDF).
- [ ] Multi-seed reliability runs; verifier false-accept/reject audit.
- [ ] Publish dataset to Harbor Hub; versioned leaderboard schema.
- [ ] Multi-step tasks (e.g. record → reconcile → report).

## Days 61–90 — Public alpha

- [ ] 12–15 reviewed generators + adversarial set.
- [ ] Baseline results for several models/agents, fully reproducible.
- [ ] Technical methodology paper/post; external contributor call.
- [ ] First standards pack scoping (IFRS vs US GAAP deltas).

Success criterion for the alpha is not task count: it is that a third
party can generate, execute, verify, and extend evaluations without
beancount.io infrastructure.
