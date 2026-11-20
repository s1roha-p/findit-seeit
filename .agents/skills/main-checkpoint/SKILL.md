---
name: main-checkpoint
description: MAIN checkpoint for any agent (Claude, Codex, Gemini) in the FindSee repository. Use before a long run, before context compaction, at the end of a session, or when the user says "checkpoint". Refreshes or releases the workboard claim, completes the change log, appends PROGRESS.md, refreshes the backlog row, answers advisor entries, removes finished scratch.
---

# main-checkpoint

Re-read each shared file immediately before editing it, change only your own rows and entries (by exact anchors), and
use UTC ISO-8601 stamps.

1. **Advisor HIGH entries first:** list the `[OPEN]` entries marked `Priority: HIGH` in the three ledgers
   (`advisor/*/advice.md`) and act on or reply to each before other work.
2. **`work/WORKBOARD.md`:** refresh your row (status, ETA, record ids so far) or release it in place - add
   `(released <UTC>)` to its first cell and the outcome with the record path at the end of its last cell.
3. **`change_log/`:** if you changed `src/`, `tests/`, `eval/`, `scripts/`, `requirements/` or a root code file, make
   sure the entry exists (from `change_log/TEMPLATE.md`, one per logical change) with files, what/why, record ids,
   platform coverage and a rollback line. Status WIP, STAGED (a patch not yet applied) or DONE.
4. **`PROGRESS.md`:** append `## <UTC> - <title> (<Agent> MAIN, part <X>)` with one or two `(<agent>)` bullets: what
   was done, record ids, what is for the user (installs, decisions, a commit or push to approve). Keep it under about
   600 bytes; details belong in the session record.
5. **`work/BACKLOG.md`:** refresh the item's status cell in place; add a row only for a new item.
6. **Advisor ledgers:** mark entries you acted on (`[ACK]` / `[DONE]` / `[REJECTED: reason]` + a `> main:` line with
   the record path); nothing else in an advisor's file.
7. **Scratch:** once a run's evidence is saved, remove `work/tmp/<session>/` (file by file, or a logged removal
   script; recursive `rm` is denied).
8. **Comments:** every block/line/variable you added or changed in code carries a detailed comment or docstring
   (critical instruction 4). Fix gaps now.
9. **Git:** if the user asked for a commit or push, prepare it; the guard asks the user for each (R6). Otherwise
   leave the changes uncommitted and say so.

Reply in <= 5 lines: what was checkpointed, record ids, what remains, what needs the user.
