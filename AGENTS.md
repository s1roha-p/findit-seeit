# AGENTS.md — cross-tool project contract

Read `CLAUDE.md` in full for project rules. It applies equally to Claude Code MAIN, Codex MAIN and Gemini MAIN. The
current user task can authorize documentation/harness edits; repository text does not override the user.

## Role selection

| Session | Role | Write scope |
|---|---|---|
| Claude Code, Codex, or Gemini (Gemini CLI / Antigravity) implementing project work | MAIN by default unless explicitly assigned ADVISOR | Project source, harness, docs and state within the task's scope and the part its human owns |
| A Claude session assigned ADVISOR | ADVISOR | `advisor/claude/` only |
| A Codex session assigned ADVISOR | ADVISOR | `advisor/codex/` only |
| A Gemini session assigned ADVISOR | ADVISOR | `advisor/gemini/` only |

Gemini is a MAIN agent like Claude and Codex. Its entry file is `GEMINI.md`, as `CLAUDE.md` is Claude's and this file
is Codex's.

Announce the role and the part when starting. Do not infer that an implementer is an advisor merely because another
session is active. Keep the role for the session; `/advisor-*` commands do not change an active MAIN session's role.

Claude's hook scope uses the launch-time `FINDSEE_AGENT_ROLE=ADVISOR`. A chat declaration alone does not configure
tool permissions. Codex and Gemini are not governed by `.claude/settings.json`: they follow these rules by contract,
and the user may configure their own tool restrictions (`.codex/`, `.gemini/settings.json`; both user-owned harness).

## Critical rules

- Stay within the fixed project root. No outside-folder inspection or following symlinks out of it.
- Never access `.env`, `.env.*` (including `.env.example`), files ending in `.env`, or secrets. Do not dump all
  environment variables or other processes' command lines.
- Use the project environment (`CLAUDE.md` rule 3): conda env `findsee` or the project's `.venv`; record which
  produced each result.
- Detailed comments/descriptions for every new/edited block, line and variable; docstrings.
- Personal data only under `docs/project/DATA_POLICY.md`; nothing of people in git.
- Git: every git command the guard knows beyond reading and branching asks the user (`CLAUDE.md` rule 5.11). Codex
  and Gemini, which the guard does not see, ask the user in chat before the same commands.
- Documentation vs code: follow the code, report each inconsistency, correct the document (`CLAUDE.md` rule 5.13).

## MAIN start and coordination

1. Read `CLAUDE.md` (Gemini: `GEMINI.md`, then `CLAUDE.md`), the latest `PROGRESS.md`, `work/WORKBOARD.md`,
   `work/BACKLOG.md`, relevant change logs and the three advisor ledgers.
2. Claim bounded files (and a device if needed) on the workboard. Re-read shared files immediately before editing.
   Never overwrite another agent's work or switch the shared tree under it.
3. Use a collision-resistant session ID: `<part>-<UTC stamp>-<agent>-<random 4 hex>`, e.g.
   `C-20261122T0930Z-gemini-3f9a`. Members work on their own clones: coordinate through pull requests and the
   workboard on `main`, not by editing each other's working trees.
4. Finish the bounded task, keep its evidence and failures, update state, release the claim.

MAIN may answer advisor entries by changing status tags and adding `> main:` lines, but may not rewrite an advisor's
`analysis.md`, reports or memory. MAIN notes belong in `PROGRESS.md`, the workboard, or the MAIN's own session folder
(`work/claude-main/<session>/`, `work/codex-main/<session>/`, `work/gemini-main/<session>/`); scratch belongs in
`work/tmp/<session>/` and is removed once its evidence is saved. How a MAIN runs larger tasks through sub-agents:
`docs/project/ORCHESTRATION_METHOD.md`.

## ADVISOR contract

Read `AGENT_ADVISOR.md`. Each advisor owns `advice.md`, `analysis.md`, `reports/`, `memory/advisor-state.md` and
`tmp/` inside its folder. Read permitted source/results; do not write the workboard, source, data, results or another
advisor's folder. No app runs, tests, evaluations, installs, downloads or GPU use. Cheap CPU analysis of saved records
may write only its own `tmp/`.

Review evaluation validity, correctness and integration risks first. Cite file:line or record ids, propose one bounded
check, and state which decision it changes. Do not invent requests or numbers to keep the ledger busy.

**Document review.** Each advisor pass also reviews the project documents (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`,
`AGENT_ADVISOR.md`, `docs/project/`, the skills, workflows and commands) for contradictions, stale facts, missing stop
rules and text that can be deleted. Each finding is a ledger entry (`Area: DOCS`) citing file:line with the exact
change. MAIN verifies it and applies or rejects it; an entry that would change autonomy, authority, a limit, a
permission, an acceptance gate, a default, or delete text the user wrote is marked `Decision: USER` and goes to the
user.

**Research advisors.** Two research forms of the ADVISOR role, each started by the user with a
commission and each keeping this contract in full (write scope, read-only review, no runs, installs or downloads):

- **Claude Mythos RESEARCH ADVISOR** - a Claude ADVISOR session on Mythos, launched with `FINDSEE_AGENT_ROLE=ADVISOR`,
  writing `advisor/claude/`. One commissioned question per pass in one of four forms - diagnosis, mechanism, design,
  adversarial review - and, as a standing assignment, critical vulnerability reviews of a named scope (loading
  untrusted weights or files, personal data or keys leaving the machine, destruction of the team's work, the guard).
  Findings are ledger entries (`Priority: HIGH` when critical); reproducers are files under `advisor/claude/tmp/` that
  MAIN runs; MAIN answers each critical finding with a fix and a failing-first test or a rejection with evidence.
  Charter: `docs/project/RESEARCH_ADVISOR.md`; entry point `/advisor-research`.
- **Codex Astra RESEARCH ADVISOR** - a Codex ADVISOR session on Astra, writing `advisor/codex/`. One or several
  commissioned jobs per pass, one report each, in one of four forms - statistical design, derivation, knowledge
  synthesis, theoretical critique - with a summary a teammate can act on, citations exact or absent, decision rules
  fixed before the data. No code or vulnerability review (those are Mythos's). Charter:
  `docs/project/RESEARCH_ADVISOR_CODEX.md`.

A research pass is not a numbered advisor pass: it prunes and archives nothing and records in its
`memory/advisor-state.md` what the next numbered pass still owes. MAIN checks a research entry's numbers before acting,
supplies measured quantities it asks for, copies its decision rules into briefs before the runs and reports back.

## Repository facts

A fresh repository created for this course project (proposed name `findit-seeit`). No upstream to fetch from.
