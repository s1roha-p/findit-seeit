---
name: main-check-advice
description: MAIN review of the three advisor ledgers for any agent (Claude, Codex, Gemini) in the FindSee repository. Use when the user says "check advice" or at session start / checkpoint. Acts on, schedules or rejects open advisor entries and replies with "> main:" lines; never deletes advisor entries.
---

# main-check-advice

Read `advisor/gemini/advice.md`, `advisor/codex/advice.md` and `advisor/claude/advice.md` (the live ledgers; the
`advice_archive_*.md` files are history). For every `[OPEN]` entry (optionally filtered by the caller, e.g. "gemini
HIGH"), decide:

- **Act now:** mark `[ACK]`, do it, then `[DONE]` with a `> main:` line citing the record, test or change log.
- **Schedule:** mark `[ACK]` and add it to `work/BACKLOG.md` (or the workboard) with a note.
- **Reject:** mark `[REJECTED: <specific reason with evidence>]`.
- **Decision: USER** entries: do not apply; present them to the user with a recommendation and record the answer in
  the entry.

Rules: re-read a ledger immediately before editing it (its advisor may be mid-pass) and edit by exact anchors; edit
ONLY the status tag and add `> main:` lines (UTC stamp, agent, part); never delete or reword advisor text or another
MAIN's replies; never touch `analysis.md`, `reports/`, `memory/`. Verify a claimed number yourself before accepting or
rejecting on its basis.

Reply with one line per entry touched (ID, new tag, why).
