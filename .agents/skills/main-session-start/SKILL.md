---
name: main-session-start
description: MAIN session start for any agent (Claude, Codex, Gemini) in the FindSee final-project repository. Use at the start of every implementation session or when the user says "session start". Reads the current state, announces the role and the part, checks the environment and claims bounded work.
---

# main-session-start

`<agent>` = `claude`, `codex` or `gemini` (the caller says which).

1. **Read** (the entry file is already in context for Claude; Gemini reads `GEMINI.md`, Codex `AGENTS.md`):
   `AGENTS.md`, `CLAUDE.md`, `docs/project/HOOKS.md` (what the guard denies and asks; Codex and Gemini keep the same
   rules by contract), the newest 3-5 `PROGRESS.md` entries, `work/WORKBOARD.md` (rows without a "released" stamp),
   `work/BACKLOG.md`, the newest `change_log/` entries, and the `[OPEN]` entries of `advisor/*/advice.md` (HIGH first).
2. **Announce** `<Agent> MAIN` (unless the user assigned ADVISOR) and the part (A-D, `docs/project/WORK_SPLIT.md`) the
   user wants worked on; if the part is unclear, ask once.
3. **Environment:** confirm the project environment (conda `findsee` or the project's `.venv`) is active or pin it per
   command; record its Python and key package versions in the session folder. If it is missing, say so and do
   source/document work only.
4. **Claim:** add a row to `work/WORKBOARD.md` (UTC start; session id `<part>-<UTC stamp>-<agent>-<4 hex>`; item and
   why; the files it may write; device/compute; ETA; where results go). Create `work/<agent>-main/<session>/` for notes
   and `work/tmp/<session>/` for scratch.
5. **Check interfaces:** if the work touches another part, read that part's section of `docs/project/ARCHITECTURE.md`
   and the current code of the interface; do not change it without that owner's agreement.
6. Do not assume a planned script or module exists; verify the tree. After a context compaction or resume, re-read the
   workboard before touching shared files.

Reply in <= 6 lines: role, part, environment status, the claimed item, open HIGH advice, anything the user must decide.
