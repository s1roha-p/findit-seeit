# GEMINI.md — Gemini (Gemini CLI / Antigravity) entry

**Your role is MAIN by default**, exactly as for Claude Code and Codex. If the user explicitly
assigns you ADVISOR for this session, follow the ADVISOR paragraph at the end instead.

## Before anything else

1. Read `AGENTS.md` and `CLAUDE.md` in full. Every rule there applies to you as it does to Claude and Codex: the
   project root only, never any `.env` file, the project environment (conda `findsee` or the project's `.venv`),
   detailed comments on every block/line/variable you write, the data policy, the evidence standard, the acceptance
   gates and the session protocol.
2. Announce `Gemini MAIN` and the part you work on (`docs/project/WORK_SPLIT.md`).
3. Run the session-start workflow (`.agents/workflows/session-start.md`).

## What differs for you

- **No hooks run for you.** Claude's guard (`.claude/hooks/guard.py`) only sees Claude Code's tool calls. You keep its
  rules by contract (`docs/project/HOOKS.md` lists them): what it denies you do not do; what it asks (every git
  command beyond reading and branching, edits of `CLAUDE.md` / `AGENTS.md` / `GEMINI.md`, writes under `data/`,
  process kills, downloads) you ask the user about in chat first and wait for the answer.
- **Your workflows** are in `.agents/workflows/` (`session-start`, `checkpoint`, `check-advice`, and the `advisor-*`
  ones for an ADVISOR session); each points at the shared skill in `.agents/skills/`.
- **Your session folder** is `work/gemini-main/<session>/` for notes, briefs and stage records; scratch goes to
  `work/tmp/<session>/`. Keep tool-generated task, plan and walkthrough files inside the project (in your session
  folder), not in an outside artifact store.
- **Your settings folder** `.gemini/` is user-owned harness: propose changes as a patch; do not edit it unless the user
  asks in this session.
- Tag your bullets in shared documents `(gemini)`, as Claude and Codex tag theirs.

## ADVISOR (only when explicitly assigned)

Write only `advisor/gemini/` (`advice.md`, `analysis.md`, `reports/`, `memory/`, `tmp/`). Read `AGENT_ADVISOR.md` and
follow `.agents/workflows/advisor-*.md`. No app runs, tests, evaluations, installs, downloads or GPU use; any cheap CPU
check runs in the project environment, is named in the entry, and writes only your `tmp/`.
