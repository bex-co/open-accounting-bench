# Open Accounting Bench — agent guide

Instructions for coding agents (Codex, Claude Code) working in this repository. [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/governance.md](docs/governance.md) carry the same rules with their reasoning; if this file ever disagrees with them, they win and this file is the bug.

Scoped guides:

- `.agents/AGENTS.md` — internal development skills (`/pm`, `/pm-brainstorm`, `/loopx`, `/ship`, `/dont-code-but-answer`)

## Codex and Claude Code compatibility

- `AGENTS.md` is the single instruction file at every scope — a real file, never a symlink. There is no `CLAUDE.md` anywhere in this repo; never add one, and never keep a parallel copy of a scope's instructions under another name.
- Claude Code reads `AGENTS.md` through its built-in `agents-md` plugin. The repo commits that setting in `.claude/settings.json` (`pluginConfigs["agents-md@builtin"].options.instructionFiles = "claude-md-or-agents-md"`), so a fresh clone picks up the guidance without local configuration. Codex reads `AGENTS.md` natively.
- Development skills live in the real directory `.agents/skills/` (Codex). `.claude/skills` must be a relative symlink to `../.agents/skills` so Claude Code reads the same implementations. Edit `.agents/skills/` only; do not create platform-specific copies.
- Slash commands are skills. Every `/name` workflow lives at `.agents/skills/<name>/SKILL.md`; there is no `.claude/commands/`. A command there would be invisible to Codex.
- Write instructions and skills using behavior supported by both Claude Code and Codex. If platform-specific configuration is unavoidable, label it clearly and give the other agent equivalent behavior (the `/loopx` Stop-hook guard is the one current example).
- After changing instruction files, skills, or the skills symlink, run `python3 scripts/check-agent-guidance.py`.

## Layout

| Path | Contents |
| --- | --- |
| `src/oab/` | Generator + verifier package, stdlib only: `families.py` (seed → instance), `generate.py` (instance → Harbor task), `_verifier_core.py` (five-layer grader), `cli.py` |
| `tasks/` | Stable-track Harbor dataset — **generated**, never hand-edited |
| `tests/` | Verifier layers, generator determinism, task health |
| `docs/` | Methodology, verification, metrics, governance, roadmap |
| `scripts/` | Agent tooling: `check-agent-guidance.py`, `loopx-guard.py` |
| `.agents/skills/` | Development skills (see `.agents/AGENTS.md`) |
| `.pm/` | Public roadmap board |

## Rules

- **Generated output is never hand-edited.** `tasks/<task-id>/` comes from `oab generate`, and every `tasks/*/tests/grader.py` is a verbatim copy of `src/oab/_verifier_core.py`. Edit the source, run `make generate`, and commit the regenerated `tasks/` with the change.
- **The verifier core stays stdlib-only and single-file** — it runs hermetically inside verifier containers. The `oab` package has no runtime dependencies.
- **Verifier changes start with a failing test**, keep the full suite green, and regenerate tasks in the same commit. They change every score ever reported.
- **Changing a family's accounting semantics or expectations** means deciding on a `GENERATOR_VERSION` bump ([docs/governance.md](docs/governance.md)) and regenerating Stable tasks in the same commit.
- **Expectations are accounting state, never exact ledger text.** Every family carries a trap: at least one balanced-but-wrong attempt fails a non-structural layer, with a test in `tests/test_verifier.py`.
- **New families need accounting review** by a reviewer with accounting background. An agent cannot self-certify it.
- **Synthetic data only** ([PROVENANCE.md](PROVENANCE.md)). Never publish Holdout-track families, seeds, or expectations anywhere in this public repo.

## Checks

From the repository root:

```zsh
make lint        # ruff check + ruff format --check over src and tests
make test        # pytest
make validate    # oab validate: structure, grader sync, oracle vs nop
make generate    # regenerate tasks/; any diff belongs in the same commit as its source change
make oracle      # needs Harbor + Docker: every Stable task scores reward 1
python3 scripts/check-agent-guidance.py   # after instruction, skill, or symlink changes
```

CI (`.github/workflows/ci.yml`) runs lint, tests, validation, the agent-guidance check, a generated-tasks drift check (`make check-generated` on the committed tree), and a Docker smoke test of one task.

## Roadmap board and shipping

`.pm/` is the public roadmap board for making OAB the trusted, neutral standard for evaluating AI accounting agents (workstreams → milestones → tasks). Conventions live canonically in `.agents/skills/pm/SKILL.md`; `/pm` is the **only** skill that writes to `.pm/`, `/pm-brainstorm` proposes work as text, and `/loopx <wN>` drains a workstream item by item — triaging each item, then shipping it, closing it as already done, blocking it with an unblock condition, or dropping it as invalid, one `/ship` per outcome. Read `.pm/DO_NOT_DO.md` before proposing roadmap work. The board is public — no secrets, no private-repo references, no holdout material.

Work lands on `master`. `/ship` rebases onto and pushes to `origin/master`; it has no test gate of its own, so run the checks above first.
