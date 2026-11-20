# Orchestration method — how a MAIN session runs larger tasks through sub-agents

Agent-agnostic: Claude uses its Agent tool with
`.claude/agents/stage-runner.md`; Codex and Gemini substitute their own worker mechanism or do the stage themselves.
`CLAUDE.md` and `AGENTS.md` take precedence.

## Roles

- **The orchestrator (the MAIN session)** establishes the facts, writes the stage brief, claims the work, launches one
  worker per stage, verifies the hand-back from files, decides what the worker may not, publishes, cleans up and
  reports to the user. At most two workers at once on a member's machine, at most one of them using the GPU or the
  camera.
- **The worker** does the stage's steps exactly as the brief says, records everything, and ends with the hand-back.
  It does not change scope, interfaces, presets or harness files, install, download, commit or push. When it needs a
  decision, it asks in its report and stops; the orchestrator decides and continues the same worker.
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
