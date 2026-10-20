# Repository Development Skills

Internal workflows for developing and maintaining this repository. Follow the [root guide](../AGENTS.md) for repository-wide rules.

The canonical implementations live in the real directory `.agents/skills/` relative to the repository root. Codex reads that directory; Claude Code reads the same files through `.claude/skills -> ../.agents/skills`. Edit the canonical files and keep the link relative.

## Skills

| Skill | Purpose |
| ----- | ------- |
| `pm` | Maintain the public `.pm` board; canonical board conventions and the only workflow that writes board state (create, close, block, drop). |
| `pm-brainstorm` | Propose roadmap milestones and tasks as text for `/pm` to materialize. |
| `loopx` | Drain a workstream item by item — triage every pending milestone, task, and inbox note, then work and ship it, close it as already done, block it with an unblock condition, or delete it as invalid. |
| `ship` | Rebase, commit, and push the current `master` branch. |
| `dont-code-but-answer` | Answer or investigate a question with read-only inspection; no edits, builds, or commits. |

## Conventions

Each skill lives at `.agents/skills/<name>/SKILL.md` with `name` (matching the folder) and `description` frontmatter; `allowed-tools` pre-approves tools in Claude Code, and `metadata: {"internal": true}` keeps these development skills out of public skill installers. Use `references/`, `scripts/`, or `agents/` (Codex UI metadata, e.g. `ship/agents/openai.yaml`) only when the workflow needs them. Keep sibling references relative so the Claude Code alias resolves them too. Use canonical `.agents/skills/` paths for repository-root commands and GitHub links.

When adding a development skill, update this catalog and run the check below. Use `.agents/tmp/` for scratch work; it is gitignored.

### Platform-specific: the `/loopx` guard

`/loopx` arms `scripts/loopx-guard.py`, a Claude Code `Stop` hook registered in `.claude/settings.json` that hands the turn back while the workstream still has an actionable item. Codex has no equivalent hook wired here, so under Codex the skill skips arming the guard and relies on its written exit rules alone. The guard is inert in sessions where no loop is armed.

### Validation

From the repository root:

```zsh
python3 scripts/check-agent-guidance.py
```

It verifies every `AGENTS.md` is a real file, that no `CLAUDE.md` exists, the `agents-md` plugin setting, the `.claude/skills` link, and each skill's frontmatter. CI runs it on every push and pull request.
