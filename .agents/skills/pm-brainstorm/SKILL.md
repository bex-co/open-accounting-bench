---
name: pm-brainstorm
description: Propose milestones and tasks for the repository's public .pm roadmap board — decompose a topic through the TPM lens of benchmark trust and adoption, size and gate the work, and emit a text-only proposal for /pm to materialize. Use only when the user explicitly invokes $pm-brainstorm or asks to brainstorm, plan, or break down roadmap work for the .pm board. Do not use to write board files (that is pm) or for ordinary code edits.
allowed-tools: Read, Bash(ls:*), Bash(find:*), Bash(cat:*), Bash(git fetch:*), Bash(git pull:*), Bash(git status:*)
metadata: {"internal": true}
---

# Task: Propose milestones and tasks

Usage: `/pm-brainstorm <topic or goal to break down>`

`/pm-brainstorm` is the **divergent** half of the pair: it thinks a topic through with a TPM's eye for benchmark trust and adoption, **proposes** work, and hands orchestration and materialization to `/pm`. It writes **nothing** — the output is a text proposal. `$ARGUMENTS` is the topic/goal.

The board conventions — mission and pillars, hierarchy, sizing rule, milestone quality gate, standing closing tasks, templates — live **canonically** in [`.agents/skills/pm/SKILL.md`](../pm/SKILL.md). Read that file and apply its rules; do not restate or diverge from them here.

**Minimum proposal size:** Every brainstorming turn must propose **at least 5 distinct, actionable items** — milestones and/or inbox notes, counted together as top-level candidates in both the detailed proposal and the closing summary. Tasks within a milestone and rejected candidates do not count toward the minimum. Keep exploring the requested topic until at least five candidates pass the existing scope, anti-goal, deduplication, sizing, and quality rules; do not pad the list with duplicates or artificially split work to reach five.

## Steps

1. **Load the canon and the anti-goals.** Read `.agents/skills/pm/SKILL.md` (conventions, mission pillars B1/B2/B3) and `.pm/DO_NOT_DO.md` (hard constraint). If a proposed item conflicts with an anti-goal, reject it explicitly and explain why.
2. **Sync when possible, then brainstorm.** Run `git fetch origin main` then `git status`. If the local branch is behind, the working tree is clean, and a fast-forward is possible, run `git pull --ff-only`. If the working tree is dirty or the branch has diverged, skip pulling and brainstorm directly from the available local board and repository state without asking for confirmation. Leave existing changes and branch history untouched; a dirty or diverged checkout does not block brainstorming.
3. **Load context.** Read the relevant `.pm` board state (workstream `README.md`s, open milestones, inbox notes — `find .pm -name README.md`, plus loose notes) so proposals fit the existing roadmap and reuse its numbering/naming. Workers are generalists: choose a workstream by priority, dependencies, and available capacity, never because the topic belongs to a permanent specialty; propose a new generic `wN` only when another worker queue is actually needed. Also check `wN/done/` and any nested `done/` folders (`find .pm -type d -name done`) for milestones that already shipped the same capability — read their titles/READMEs before proposing, and drop or reshape any candidate that duplicates completed work instead of proposing it fresh. The shipped ground truth is the repo itself: the root `README.md` and `AGENTS.md`, `docs/roadmap.md` (the 90-day plan and its checkboxes), `docs/task-families.md`, `docs/verification.md`, the `FAMILIES` and `STABLE_SEEDS` registries in `src/oab/families.py`, `tasks/manifest.json`, and `.agents/AGENTS.md` for development skills. Read those before proposing — build on what exists rather than re-deriving or duplicating it.
4. **Apply the TPM lens.** For each candidate, answer before proposing it:
   - **Pillar:** which of B1/B2/B3 it advances (a candidate that fits none is out — or `.pm/DO_NOT_DO.md` material).
   - **Adopter:** who concretely benefits — a lab or researcher evaluating models, an agent builder regression-testing an accounting agent, a contributor adding a family or verifier layer, or an accounting reviewer.
   - **Capability gained:** what the adopter can measure, trust, reproduce, or extend afterward that they couldn't (or wouldn't bother to) before.
   - **Signal:** which observable signal should move — verifier false-accept/reject rate, validated generator count, third-party runs and reproductions, contributed families, Harbor Hub pulls, citations, stars.
   Prefer compounding assets (reviewed generators, verifier layers, reproducible baselines, docs that work exactly as written) over one-off promotion. Prefer making an existing grade trustworthy over adding a new family — never trade verification integrity for coverage.
5. **Discuss & decompose.** Talk the topic through with the user: pressure-test scope, surface dependencies and risks, and break it into candidate tasks, each with a rough estimate and `depends_on` links.
6. **Size and gate** each cluster of work using `/pm`'s sizing rule and milestone quality gate. Undersized work → propose an inbox note instead of a milestone, and say so. Work that fails the quality gate → mark it **not meaningful**, do not propose it as a milestone, and suggest a better-scoped alternative.
7. **Emit the proposal as text only.** Give the full detail first: the target general-purpose worker queue and why its priority/capacity makes it the right destination, each proposed milestone (task table + definition of done + source + pillar linkage + expected outcome + why-now rationale) and/or inbox note, numbered in proposed priority order. Propose **implementation tasks only**: `/pm` appends the standing closing tasks (Adoption surface, Simplify, Test coverage, Accounting review, Closeout, each when it applies) itself when it materializes, so do not include them — but do flag in the proposal whether you expect Adoption surface and Accounting review to apply, so `/pm` and the user aren't guessing. Do **not** write files.
8. **End with the summary and handoff.** The response must **end** with these two blocks, in this order, so the user can scan the close without rereading the detail:
   1. A **"Summary (priority order)"** section: a numbered list of every candidate (milestones and inbox notes together) using the same numbers as the detail above — one line each: `N. <title> (wN, ~size) — one-line outcome`.
   2. The exact `/pm` invocation(s) to materialize the proposal, e.g.:
      - `/pm new milestone w1 <title>` (then the tasks), or
      - `/pm add w1 <idea>` for sub-hour work, or
      - `/pm promote w1/NNN` to promote an existing inbox note.
   Nothing comes after these blocks — no trailing analysis or caveats.

## Topic

$ARGUMENTS
