# Orchestration method — how a MAIN session runs larger tasks through sub-agents

Agent-agnostic: Claude uses its Agent tool with
`.claude/agents/stage-runner.md`; Codex and Gemini substitute their own worker mechanism (in T3 Code, `delegate_task`;
see "Parallel orchestrators" below) or do the stage themselves. `CLAUDE.md` and `AGENTS.md` take precedence.

## Roles

- **The orchestrator (the MAIN session)** establishes the facts, writes the stage brief, claims the work, launches one
  worker per stage, verifies the hand-back from files, decides what the worker may not, publishes, cleans up and
  reports to the user. At most two workers at once on a member's machine, at most one of them using the GPU or the
  camera.
- **The worker** does the stage's steps exactly as the brief says, records everything, and ends with the hand-back.
  It does not change scope, interfaces, presets or harness files, install, download, commit or push. When it needs a
  decision, it asks in its report and stops; the orchestrator decides and continues the same worker.
  The two-worker limit counts every orchestrator on the machine together when workers run compute (tests,
  evaluations, the app, GPU, camera); see "Parallel orchestrators" for edit-only workers.
- **The user (the part owner)** decides installs, downloads, new personal data, interface changes that affect another
  part, git publication, and the pace.

## Stage lifecycle

1. **Facts first:** read the records the stage builds on; check the code anchors (function names, signatures in
   `ARCHITECTURE.md` vs code), inputs (manifests, fixtures, weights present), the device.
2. **Brief** `work/<agent>-main/<session>/subagents/<STAGE>_<slug>.md`: title with the bound; what is settled (cite);
   numbered steps with exact commands and how to read each outcome; the record file and its sections; must-nots; the
   hand-back format.
3. **Claim** on `work/WORKBOARD.md`.
4. **Launch** one worker with the brief path and the standing rules (project environment, no installs or git
   publication, scratch in `work/tmp/<session>/<stage>/`, scripts written to files and run by path).
5. **While it runs:** answer the user; do not predict the result.
6. **Verify the hand-back from files:** rerun named tests, open the record files, check digests. A claim that cannot be
   verified is published as the worker's claim, marked so, or not at all. Read the advisors' open HIGH entries.
7. **Decide** what the worker could not, record the reason, continue the same worker if needed.
8. **Publish:** `PROGRESS.md` entry, backlog row, workboard release, change log.
9. **Clean up** the stage scratch.
10. **Report** to the user: outcome first, evidence with tier, what was not done, what the user must decide.

## Parallel orchestrators (several MAINs on one part)

Two or three MAIN orchestrators (Claude, Gemini, later Codex) may work on one part at the same time, each with its own
workers. First trial: Part C, 2026-11-22, `work/claude-main/C-20261122T1606Z-claude-0984/LANES.md`.

**Lead.** One orchestrator is the lead (the session the user started). It alone establishes the facts, writes the
lanes file, launches the other orchestrators, writes `PROGRESS.md`, the backlog and `docs/`, integrates the lanes and
reports to the user. The other orchestrators run the stage lifecycle above inside their lane and hand back to the lead.

**Lanes file** `work/<lead>-main/<session>/LANES.md`, written before any lane starts:

1. Facts every lane needs (what exists, environment and device status).
2. The frozen interface the lanes build to: signatures, types, value ranges, error behaviour, invariants a test can
   check. Lanes test against this text, not against each other's code, so they can start together; a test lane is
   told not to open the implementation files. End it with an **"Unspecified (do not assert)"** list - e.g. the
   exception type for a wrong argument type, rounding tie-breaks, internal filter parameters - so neither lane spends
   judgment on cases the contract leaves open. A later round appends a new section (2R, 2S ...) instead of editing
   a frozen one.
3. One row per lane: orchestrator, session ID, the **disjoint** set of files it may write, its worker budget. Add a
   reserved row for an orchestrator that may join later; a third orchestrator joins by filling that row, nothing else
   changes.
4. The integration steps.

**Shared files.** Each orchestrator writes only its lane's files, its own `work/<agent>-main/<session>/` folder, its
own `change_log/` file and its own workboard row. The lead adds every lane's row before launching it; a non-lead
orchestrator edits only the **last cell** of its own row (re-read immediately before editing) to record its hand-back,
and the lead releases the rows at integration (an exception to the workboard's own release rule). One
checkout is shared on one machine: nobody switches the branch, commits or runs a git command that asks. If lanes need
separate checkouts, the lead asks the user, and the lanes come back by pull request.

**Worker budget.** Workers that only edit files: at most two per orchestrator. Workers that run compute share the
machine-wide limit of the Roles section (two, at most one on the GPU or camera) across all orchestrators; the lanes
file assigns that budget.

**Launch recipe in T3 Code** (`delegate_task`; the lead calls `orchestrator_capabilities` once first; the task text
must be self-contained because a child has no parent history):

| Orchestrator | Orchestrator target | Its workers |
|---|---|---|
| Claude | the session the user started, or `providerInstanceId: claudeAgent` | Agent tool, `stage-runner` (`.claude/agents/stage-runner.md`) |
| Gemini | `providerInstanceId: antigravity`, model `gemini-pro-orchestrator-neon`, `thought_level: high` | `delegate_task` to `antigravity` / `gemini-4-neon`, `thought_level: medium` |
| Codex | `providerInstanceId: codex`, model and effort from `orchestrator_capabilities` (not yet tried) | its native `spawn_agent`, or `delegate_task` to `codex` |

**Child or own thread.** A non-lead orchestrator runs either as a `delegate_task` child (its completion wakes the
lead) or, when the user wants to watch and steer it directly, as its own top-level T3 thread (`t3_thread_launch` with
`workspaceStrategy: root` for the shared checkout, `modelSelection` = the orchestrator target above). A top-level
thread does not wake the lead: it writes its hand-back to `work/<agent>-main/<session>/HANDBACK.md` as well as its
final message, and the lead waits with `t3_thread_wait` / reads it with `t3_thread_read`. To move a running child to
its own thread, cancel the child (`task_cancel`, which also stops its runners), check what it wrote, and launch the
thread with the same session ID and an instruction to resume from its session folder.

The model names are the ones offered on 2026-11-22; check `orchestrator_capabilities` again before reuse. A child or
thread cannot get a `runtimeMode` above the lead's own (T3 refuses with `runtime_mode_escalation_denied`); for
`full-access` orchestrators the user first switches the lead thread to full access. Antigravity has no `auto` mode: a
Gemini thread launched from an `auto` lead inherits `auto-accept-edits`. A non-Claude orchestrator is not seen by the guard: its task text repeats the
guard's rules it must keep by contract (`docs/project/HOOKS.md`).

**Integration (lead).** First audit without trusting the hand-backs: `git status --short` against the lanes'
write sets (any path outside them is a finding) and a non-ASCII byte scan of the new code. Then read every file of
every lane; check each test assertion against the implementation and the
lanes file; a mismatch is a code bug or a test bug, decided by the frozen interface; the owning lane fixes it (continue
that orchestrator, do not fix its files yourself unless it has finished and the lanes file says so). Then publish as in
steps 8-10 above, with one bullet per orchestrator tagged `(claude)`, `(gemini)`, `(codex)`.
