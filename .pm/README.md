# `.pm` — roadmap board

Public TPM board for making Open Accounting Bench the trusted, neutral standard for evaluating AI accounting agents — a benchmark a third party can generate, execute, verify, and extend without beancount.io infrastructure.

- Conventions — mission pillars (B1 verification integrity, B2 task coverage, B3 reproducible adoption), hierarchy, sizing rule, quality gate, templates — live canonically in [`.agents/skills/pm/SKILL.md`](../.agents/skills/pm/SKILL.md).
- `/pm-brainstorm <topic>` proposes work (text only); `/pm` is the **only** command that writes here; `/loopx <wN>` drains a workstream.
- Hard constraints: [`DO_NOT_DO.md`](./DO_NOT_DO.md). The 90-day plan this board executes against: [`docs/roadmap.md`](../docs/roadmap.md).
- Layout: `wN/` general-purpose worker queues → `wN/NNN.md` inbox notes (≤ ~1h) and `wN/mN/` milestones (> ~1h) → `wN/mN/tNNN.md` tasks. Topic focus belongs to milestones and tasks; workers can take work across families, the verifier, tooling, and pillars. Completed work moves under `done/`, stuck work under `blocked/`.

This board is public — write everything in it for community consumption, and never put holdout material here.
