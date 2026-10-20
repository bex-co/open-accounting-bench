---
name: loopx
description: Autonomously drain a `.pm` workstream item by item — triage every pending milestone, task, and inbox note, then implement and ship it, close it as already done, block it with an unblock condition, or delete it as invalid, and keep going until nothing actionable remains (do not stop early to ask the user to resume). Use when the user explicitly invokes $loopx or asks to loop, drain, or work through a whole workstream's backlog (e.g. `$loopx w1`). Sequential, not interval-based; do not use for a timed poll, a single task, or ordinary code edits.
metadata: {"internal": true}
---

# Task: Drain a `.pm` workstream item by item

Usage: `/loopx <wN>`

`/loopx <wN>` — repeatedly pick the next **actionable pending item** in workstream `<wN>`, **triage** it, act on the outcome, `/ship` it, and continue until nothing actionable remains. An item is a pending **milestone**, a pending **task** inside a live milestone, or an open **inbox note**. Every item ends in exactly one of four places: implemented and shipped, closed as already done, moved to `blocked/` with the condition that would clear it, or deleted as invalid. Blocked items and their dependents are skipped automatically, without waiting for user input. This is a long-running autonomous loop over the `.pm` board; it composes `/pm` (the only writer to `.pm/`), your own implementation work, and `/ship`. It is sequential, not interval-based — for a timed poll use `/loop`. If you can name the next pick, keep looping — do not pause for a checkpoint or tell the user to re-run `/loopx`.

A pending item is a claim that the work is still wanted and still undone. Boards go stale: work lands through another item or a direct commit, a decision or a `DO_NOT_DO.md` rule retires the idea, the family or surface it targets gets removed or renamed. Never start implementing on the strength of a checkbox alone — every item earns its implementation by passing triage first.

Parse the target workstream from `$ARGUMENTS` (e.g. `w1`). If `$ARGUMENTS` is empty, **STOP** and ask which workstream to drain — never guess.

## Preconditions (verify once, up front)

1. `git branch --show-current` is `master`. If not, STOP and ask (same rule as `/ship`).
2. `git status` — note pre-existing uncommitted changes. Do not sweep unrelated changes into an item's ship; if the tree is dirty with work you didn't do, surface it and ask before starting.
3. The workstream `.pm/<wN>/README.md` exists. If not, STOP and report.
4. Read `.pm/DO_NOT_DO.md` once. Every item you pick must respect it, and a conflict with it is a delete reason in triage.
5. **Claude Code only:** arm the loop guard with `python3 scripts/loopx-guard.py start <wN>`. It is a `Stop` hook (`.claude/settings.json`) that refuses to let the turn end while `<wN>` still holds an actionable item, and it names the next pick when it does. Only a genuine **Exit** clears it, so this is the one mechanism that survives your own judgement that you are finished. Codex has no equivalent hook here: under Codex, skip arming (and the matching `end`) — the Exit rules below are the only guard, so hold yourself to them.

## The loop

Repeat until the exit condition below:

### 1. Pick the next pending item

Read `.pm/<wN>/README.md` and list the tree: `.pm/<wN>/m*/`, `.pm/<wN>/*.md`, `.pm/<wN>/done/`, `.pm/<wN>/blocked/`. The checkbox and the on-disk state must agree; if they disagree, trust the task files, flag the drift, and repair it through `/pm` before continuing.

Pick in this order, and announce what you picked:

1. **The lowest-numbered actionable pending milestone** — unchecked (`- [ ] **mN**`), with a live directory (`.pm/<wN>/mN/`, not under `done/` or `blocked/`), not deferred or blocked earlier this run. Inside it, work its **pending tasks** in `depends_on` order; the next actionable task is the first non-done task whose dependencies are all done. Each task is itself an item and gets its own triage.
2. **The lowest-numbered open inbox note** (`.pm/<wN>/NNN.md`), when no milestone is actionable. Notes are sub-hour units — a bug fix, a doc correction, a decision to record. They are work items for this loop, not scenery. Pull one forward out of order when a milestone depends on it.
3. **A blocked item whose unblock condition now holds** (`.pm/<wN>/blocked/`). Re-read the condition and verify it against the repository before reviving anything; `/pm unblock` moves it back, and it then re-enters triage like any other item. Do not retry an unchanged blocker.

Establish which items can proceed before deciding none can: honor explicit `depends_on` links and prerequisites stated in scope or acceptance criteria, including transitive ones. Numbering alone does not imply a dependency. Scan every later pending item before concluding the workstream is done.

If nothing is actionable, go to **Exit**.

### 2. Triage the item

Read it fully: a milestone's `README.md` plus every open task file, a task's own file, or the note. These define scope, order, and acceptance. Milestones ship **end to end** — a task family is its generator, its trap and oracle tests, the regenerated Stable task, and the docs that list it, not just the generator. Respect the milestone's `## Definition of done` and each task's `## Acceptance criteria`.

Then, **before writing any code**, establish what is actually true on `master` and pick one of four outcomes. Triage runs on evidence, not impression: `git log` the source the item cites and the paths it names, grep for the families, commands, and strings it describes, open every path under `## Files`, run the observable checks in `## Definition of done`, and reproduce a bug note's repro yourself. Announce the outcome and the evidence in a few lines before acting on it.

| Outcome | When | What you do |
| --- | --- | --- |
| **Work on it** | The goal is still wanted and its acceptance does not hold yet. Stale details — moved paths, renamed commands, a family that changed shape — do not change this: follow the intent and note the deviations in the per-item summary. | Give a one-line plan and continue to step 3. Close any sub-item already satisfied by shipped code with `/pm done`, citing the commit, paths, or tests that satisfy it, so the record shows why it closed without work this session. |
| **Close as already done** | The acceptance criteria already hold on `master` — including the standing closing tasks (adoption surfaces checked, meaningful tests exist, accounting review on record) — and the definition of done holds when you actually run its checks. A note's bug no longer reproduces at HEAD. Missing tests or an unchecked adoption surface make this *work on it*, not close. | `/pm done <target>` — tasks in dependency order, Closeout last; a note gets its resolution line and moves to `done/`. Skip to step 4 and ship the board move alone: `chore(pm): close <target> — already satisfied by <SHA>`. No code rides along. |
| **Block it** | The work is still wanted but cannot proceed here: missing credentials or external access (a Harbor Hub account, model API keys for a baseline run), an accounting review only a qualified reviewer can give, an unobservable acceptance criterion, an unresolved failing check, a ship failure, or a scope question only the user can answer. A question you cannot settle from evidence is a blocker, not a reason to skip quietly. | `/pm block <target> <reason>`, writing the exact blocker, an **Unblock:** condition, and who can clear it. Preserve any partial work (see [Handling a block](#handling-a-block)). Skip to step 4 and ship the move alone: `chore(pm): block <target> — <one line>`. |
| **Delete as invalid** | The work should not be done at all: it conflicts with `.pm/DO_NOT_DO.md` or `docs/governance.md`; a decision recorded on the board or in a commit retired it; it is fully superseded by or duplicates other work (shipped or still open — keep the better one); or the family or surface it targets no longer exists. | `/pm drop <target> <reason>`, naming the rule, doc, commit, or item that justifies it. Skip to step 4 and ship the deletion alone: `chore(pm): drop <target> — <reason>`. If the reason generalizes into a rule, propose a `DO_NOT_DO.md` entry in the final summary; do not write one yourself. |

Closing, blocking, and deleting all rewrite a public board, so the bar is evidence you can cite. An item the user explicitly routed or approved (`user routed to`, `user approved`, `user decision`) that you merely *suspect* is unwanted is a **block** with the question as its unblock condition, never a delete. Deleting is for work that is provably invalid; blocking is for work that is still wanted and stuck. Never delete an item to avoid the work in it.

The last tasks of every milestone are the standing closing tasks defined in [`.agents/skills/pm/SKILL.md`](../pm/SKILL.md) (Adoption surface when present, Simplify, Test coverage, Accounting review when present, Closeout). They are real work, not bookkeeping: run `/simplify` for Simplify, write meaningful tests for Test coverage, and walk every surface the Adoption surface task names. You cannot perform an Accounting review yourself: when no reviewer sign-off is on record, block that task in place (**Unblock:** a reviewer with accounting background signs off) and keep draining — the milestone stays open until the review lands.

### 3. Implement it

Do the actual engineering, one item at a time, following `depends_on` order inside a milestone:

- Follow the root `AGENTS.md` and `CONTRIBUTING.md`: never hand-edit `tasks/<task-id>/` or `tasks/*/tests/grader.py` (edit the generator or `src/oab/_verifier_core.py`, then regenerate), keep the verifier core stdlib-only and single-file, state expectations as accounting state rather than ledger text, give every family a trap, use synthetic data only, and never publish holdout material.
- Run the checks the change touches and make them pass before considering the item done:
  - any change → `make lint`, `make test`, `make validate`
  - `src/oab/` (families, generator, verifier) → `make generate`, and ship the regenerated `tasks/` in the same unit — CI's generated-tasks check fails on drift. `git status -- tasks` must show only the drift this item intends. When accounting semantics or expectations change, decide on a `GENERATOR_VERSION` bump per `docs/governance.md` and say which in the commit.
  - `src/oab/_verifier_core.py` → a failing test first, as `CONTRIBUTING.md` requires for verifier changes; the full suite green after.
  - a new or changed task family → `make oracle` (Harbor + Docker) so every Stable task scores reward 1. When Harbor or Docker is unavailable, say so in the item's summary; `make validate` still grades oracle and nop locally.
  - `.agents/`, `.claude/`, `scripts/`, or any `AGENTS.md` → `python3 scripts/check-agent-guidance.py`
  - before every ship → `gitleaks dir . --redact --verbose`

  Never mark an item complete on unverified code.

- A bug note is not fixed until its own repro fails to reproduce and a regression test covers it. Prove the test is real — revert the fix and watch it fail.
- You may delegate independent sub-tasks to subagents to parallelize, but you own correctness.
- Keep the board in sync as you go by invoking **`/pm done <target>`** for each finished task or note — `/pm` is the only skill that writes to `.pm/`, so never edit task frontmatter, milestone `**Status:**` lines, workstream checkboxes, or `done/` and `blocked/` placement by hand. Running `/pm done` on the milestone's Closeout task last is what moves the whole milestone to `.pm/<wN>/done/mN/` and flips its workstream checkbox to `[x]`. Do not close out until the milestone's definition of done actually holds; if it cannot hold here, the milestone is a **block**, not a close.

### 4. Ship it

Invoke **`/ship`** ([`.agents/skills/ship/SKILL.md`](../ship/SKILL.md)) for this item's changes — code and the `.pm/` moves together, or the board move alone when triage ended the item without code. Because you made the changes this session, `/ship` runs session-aware: it stages exactly what you touched and writes the commit message from your knowledge. `/ship` ends at a successful push — it has no test gate of its own and does not watch CI, so the checks in step 3 are the only gate; run them before invoking it.

Ship each outcome before starting the next item. A milestone large enough to span several sessions may ship at task boundaries, provided every ship is green and self-contained. **Proceed after `/ship` reports the shipped HEAD**, or after isolating a block under the handling below.

If `/ship` surfaces a failure it cannot fix (a rebase conflict it can't resolve, a rejected push), that is a block.

### 5. Continue

Loop back to step 1 to pick the next pending item. After every ship (or block isolation), **immediately** re-scan and pick again — do not end the turn, ask the user to resume, or wait for another `/loopx` invocation while step 1 would still find an actionable item. Stopping because the queue is long, the session is long, or you already shipped several items is not an exit.

Between items, write one sentence: what shipped and the id you are picking next. Save tallies and per-item recaps for the Exit report — a mid-run summary tends to become a premature stop.

## Handling a block

A block is anything you cannot resolve autonomously. It can surface at triage or mid-implementation; either way the item leaves the open tree through `/pm block` with its unblock condition, and the loop keeps going.

- Report the item, the exact blocker, and what would unblock it in a progress update; **do not stop or wait for input** while independent work remains. Keep a run-local record of blocked items and the dependency chains they defer.
- Preserve partial code together with its board changes before switching items — an isolated worktree or a named stash. Do not discard work, ship half-work, or let a later ship include blocked changes or unpushed commits. Continue from the shipped baseline. Treat a shared failure (such as unavailable push access) as blocking every item that needs it; isolation does not resolve that failure.
- When only *some* of a milestone's tasks are blocked, block those tasks in place (`status: blocked`, reason in the milestone `README.md`) and keep working the ones that can proceed. When every open task is blocked, block the milestone itself.
- Return to step 1 and pick the lowest-numbered independent actionable item. If `m2` is blocked and `m3` depends on it but `m4` is independent, skip `m2` and `m3` and work `m4` automatically.
- Revisit a blocked item only when new evidence changes its condition — another item shipped, the user supplied the missing input, a reviewer signed off. Do not repeatedly retry an unchanged blocker.

## Exit

Stop the loop and give a final summary **only** when one of these holds:

- **Done:** no pending items remain in `<wN>`. Report every item's outcome: shipped implementations with their HEAD SHAs, items closed as already done with the evidence, blocked items with their unblock conditions and owners, deleted items with their reasons (and any `DO_NOT_DO.md` rule you propose).
- **Blocked:** pending items remain, but every one is blocked or depends directly or transitively on unresolved blocked work. Report items shipped this run (with HEAD SHAs), each blocker and what is needed to proceed, deferred dependents, and where partial work was preserved. A single blocked item is not an exit condition while later independent work can proceed.
- **Hard stop only:** the user explicitly interrupts, or the runtime forces a stop (session/tool limit, killed process, lost push access that blocks every remaining ship). In that case report progress (triaged, shipped, in-flight, blocked, **next actionable pick**) so a later `/loopx <wN>` can resume — but **never** choose this exit yourself while step 1 still has a known next item.

**Not an exit:** "checkpoint", "budget", "long enough", "several items shipped already", or "resume with `/loopx <wN>` to pick up at NNN" while open inbox notes or actionable milestones remain. If you can name the next pick, you must pick it and continue.

When one of the three exits genuinely holds, clear the guard (Claude Code) with `python3 scripts/loopx-guard.py end`, then give the final report. Until you run that, the `Stop` hook will keep handing the turn back with the next pick — which is the intended behaviour, not a fault to work around. Never clear it to end a run that has an actionable item left.

## Guardrails

- **Keep going when the next item is known.** Knowing that the next note or milestone exists is a reason to pick it now, not to stop and tell the user to re-invoke `/loopx`. Drain until Done, Blocked, or a hard stop above.
- **Triage before code.** No item is implemented on the strength of its checkbox. Every pick gets an evidence-backed outcome — work on, close, block, or delete — announced before any code changes.
- **Every item ends somewhere.** Shipped, `done/`, `blocked/`, or deleted. Leaving an item open and untouched because it looked hard is not an outcome; that is a block, and it needs a written unblock condition.
- **One board outcome per ship.** Never batch two items into one commit; an implementation, a triage close, a block, and a deletion each land as their own shipped unit so history and rollback stay clean.
- **Never ship red.** A failing check is a block, not a footnote. `/ship` will not stop you — the step 3 checks are the gate, so run them yourself before every ship. Run the gates as their own command and read the result before you commit: chaining `&& git commit` onto the end of the gate command makes the commit run on a non-zero gate, which is exactly how a red push happens. If a gate fails, decide whether it is your change or a known flake, and say which in the item's record.
- **Scores are history.** Verifier and generator changes alter every score ever reported. Never weaken a verifier layer or loosen an expectation to make a check pass; a grade that now disagrees with the oracle is a bug to understand, not a test to update.
- **`/pm` owns the board.** All `.pm/` writes go through `/pm done`, `/pm block`, `/pm unblock`, and `/pm drop`. An item is done when it sits under `done/`, blocked when it sits under `blocked/` with its condition, and deleted when `/pm drop` has removed it — not when you stop looking at it.
- **Doubt is a block, not a delete.** Delete only on evidence you can cite; when the question is one for the user, block with that question as the unblock condition and repeat it in the summary.
- **The board is public.** Nothing you write into `.pm/` or a commit may contain secrets, user data, holdout material, or references to private repositories — block reasons, delete reasons, and triage-close evidence included.
- **Stay in `<wN>`.** Only pick items from the requested workstream. Workers are general-purpose, but this run is scoped to the queue the user named.
- **Report honestly.** If you skipped a task, mocked something, or a suite was flaky, say so in the per-item summary — don't present partial work as complete, and don't present a close-by-triage as work you did.

## Arguments

$ARGUMENTS
