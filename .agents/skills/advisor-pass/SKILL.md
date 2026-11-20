---
name: advisor-pass
description: Full advice pass for the ADVISOR role in the FindSee final-project repository (Mode 1 find-things pipeline, voice interaction, Mode 2 low-vision enhancement, integration, evaluation records). Use when the user asks for a review pass, a critique of recent work or results, or types /advisor-pass. Runs detect changes → read context → GC marks → critique (evaluation first) → write ledger entries → rewrite analysis.md → log → update memory. Writes only inside advisor/<agent>/.
---

# advisor-pass — one full cycle

Writes ONLY inside `advisor/<agent>/`: `advice.md`, `analysis.md`, `memory/advisor-state.md`, plus a report in
`reports/` and check outputs in `tmp/` when needed. `<agent>` = `claude` (launched with `FINDSEE_AGENT_ROLE=ADVISOR`),
`codex` or `gemini` (declared ADVISOR by the user). `AGENTS.md` §Critical rules and §ADVISOR contract apply throughout:
no code execution by default; never read `.env` or `data/raw/`; never run the app, tests or evaluations; never write
`data/`, `work/results/` or the workboard; anything you do run, run in the project environment and name it.

## 1. Detect changes

- Marker = newest line of the `Advice Log` in `advice.md` and the `HEAD` recorded there. Committed changes since:
  `git log --stat HEAD ^<that HEAD>`; uncommitted: `git status --porcelain`. Content identity decides what changed;
  modification time only bounds the search. First pass (only the initialization line): scope = the last ~2 sessions
  of `PROGRESS.md`, the records they cite, `docs/project/`, and the seeded hypotheses in memory.
- Work in flight: every `work/WORKBOARD.md` row without a "released" stamp; treat its files as possibly torn.

## 2. Read context (ground-truth order)

`memory/advisor-state.md` → tail of `PROGRESS.md` → the MAIN session records the changes name
(`work/<agent>-main/<session>/`) → the `work/results/*.json` they cite → `work/BACKLOG.md` + `work/WORKBOARD.md` →
newest `change_log/*.md` → `docs/project/EVALUATION_PROTOCOL.md` and `ARCHITECTURE.md` if the harness or an interface
changed → source only where a claim needs it. Read the numbers in records, not the prose about them.

## 3. GC the main agents' marks

Apply the `advisor-sync` lifecycle to existing entries before writing new ones. Preserve marks and `> main:` replies
verbatim.

## 4. Critique — evaluation first (see `AGENT_ADVISOR.md` §What to audit first)

1. **Evaluation validity** of every number the changes rely on: split by session, frozen parameters, simulation
   version, OCR engine, n, statistic, tier claimed vs reached, best-run quoting.
2. **Correctness** of the changed path: image formats and ranges, box coordinates, audio format, last-seen logic,
   prompt language; are the tests exercising the change?
3. **Integration** against `ARCHITECTURE.md`: signatures, types, stubs left in, the Mode 1 → Mode 2 handoff, failure
   paths (camera, microphone, network).
4. **Latency and resources:** measured where claimed; stage shares; demo machine.
5. **Privacy and safety:** `DATA_POLICY.md` (consent, redaction, what leaves the machine), medication disclaimer.
6. **Demo risk** and the remaining schedule (`WORK_SPLIT.md` timeline).
7. **Document review** (`AGENTS.md`): file:line, the exact change, `Area: DOCS`, `Decision: USER` where it touches
   autonomy, authority, limits, permissions, gates, defaults or user-written text.

A cheap check is justified only when a specific claim hinges on it: read-only, CPU, ≤ ~60 s, on saved records, output
to `tmp/`, project environment named, and no evaluation in flight. Otherwise cite the file and state what MAIN should
compute.

## 5. Write entries

Format exactly as the `advice.md` header says; IDs monotonic over the whole file. Every entry: Evidence, Concern,
Advice (with predicted outcomes for checks), Cost / decision. Few, analytical entries; no restating `PROGRESS.md`; a
clean pass adds only the log line. More than ~12 lines of argument → a report in `reports/` with a one-line entry.

## 6. Rewrite `analysis.md`

Rewrite (do not append) its sections: state per part, evidence table (record id + tier), risks to the demo,
assumptions, untested combinations, open hypotheses, do-not-re-raise. Keep it under ~150 lines.

## 7. Log and remember

- Append `- YYYY-MM-DD HH:MM — pass #k: reviewed <range>; HEAD <sha>; added A-…; pruned A-…; <headline>`.
- Rewrite `memory/advisor-state.md` (last-pass marker, HEAD, next ID, open hypotheses, do-not-re-raise); under ~80 lines.
- Keep `advice.md`'s active part to about 150 lines; move history verbatim to `advice_archive_<date>.md` with its
  sha256 noted.

## 8. Report (in chat, ≤ 10 lines)

Range reviewed, IDs added / pruned / re-opened, the most decision-relevant item, and anything that needs the USER.
