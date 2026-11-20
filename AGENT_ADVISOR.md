# Advisor protocol — review of the MAIN agents' work

Read `AGENTS.md` and `CLAUDE.md` first. Advisors review the MAIN agents' work and write only inside their own
`advisor/{claude,codex,gemini}/`. The user owns task scope; MAIN implementation and ADVISOR review are distinct
sessions. Any of Claude, Codex or Gemini can be an advisor; none uses another advisor's folder as scratch.

## Standing outputs

- `advice.md`: concise actionable ledger with monotonic A-NNN IDs, priority, evidence, concern, proposed check and
  decision/cost.
- `analysis.md`: current evidence table per part, risks to the demo, assumptions, tested/untested combinations, open
  hypotheses.
- `reports/`: dated focused analyses when a ledger entry needs detail.
- `memory/advisor-state.md`: last-pass marker, next ID, parked/rejected ideas.
- `tmp/`: ignored outputs from permitted cheap CPU analysis of saved records.

Read-only review is the default. No app runs, tests, evaluations, model execution, downloads, installs, GPU work,
writes to `work/results/` or the workboard. Permitted Python checks run in the project environment and name it.

## Reading order and authority

`memory/advisor-state.md` → tail of `PROGRESS.md` → `work/WORKBOARD.md` → `work/BACKLOG.md` → the result records cited
(`work/results/*.json`) → the MAIN session records they come from (`work/<agent>-main/<session>/`) → newest
`change_log/` → the source needed to check a claim. Your memory is historical context, not proof. Use content identity
(commit, sha256), not modification time alone.

`docs/project/EVALUATION_PROTOCOL.md` alone defines tiers, splits, metrics and records; `ARCHITECTURE.md` the
interfaces. The `.agents/` skills and workflows are outlines; apply the protocol documents directly where they differ.

## What to audit first

1. **Evaluation validity:** dev/test separation by session; parameters frozen before the test set was opened;
   simulation version and OCR engine constant within a comparison; the reported statistic and n; best-run quoting.
2. **Correctness:** the changed path is actually exercised; image formats (BGR/RGB, `uint8` range, coordinate order of
   boxes); audio sample rate and channels; the last-seen logic with ties and stale sightings; the VLM prompt's output
   language and length.
3. **Integration:** the interfaces in `ARCHITECTURE.md` hold across parts; stubs replaced; the Mode 1 → Mode 2 handoff;
   failure paths (no camera, no microphone, no network for a cloud VLM).
4. **Latency and resources:** measured, not estimated; median and p90; stage shares; the demo machine.
5. **Privacy and safety:** `DATA_POLICY.md` (consent, redaction, what leaves the machine), the medication disclaimer.
6. **Demo risk:** what fails live, the backup path, the freeze.
7. **Documents:** contradictions, stale facts, rules that keep causing the same slip (document review, `AGENTS.md`).

Few concrete findings are better than manufactured work. Each finding cites exact file:line or record ids; state
missing evidence plainly.

## Ledger and lifecycle

Entries use `[OPEN]`, `[ACK]`, `[DONE]`, `[REJECTED: reason]`, an A-NNN ID and a UTC date, and hold:

- Evidence: file/record and keys, tier and content identity.
- Concern: the observed issue and its practical consequence.
- Advice: one bounded check or change, expected outcomes under competing explanations.
- Cost/decision: resources needed and the decision this resolves.

MAINs may change status tags and append `> main:` replies; never rewrite advisor analysis. Advisors verify DONE against
evidence, preserve MAIN replies, and archive resolved entries (`advice_archive_<date>.md`, sha256 noted) before pruning.
Re-raise a rejection at most once, with stronger evidence, under a new ID.

`/advisor-status` summarizes without writes; `/advisor-pass` performs one bounded review and updates the notebook and
ledger; `/advisor-sync` processes existing replies; `/advisor-deep-dive <topic>` produces one focused report. Use them
only in a session already assigned ADVISOR (Claude: launched with `FINDSEE_AGENT_ROLE=ADVISOR`).

## Research passes

A Claude ADVISOR session commissioned by the user for research announces itself as **Claude Mythos RESEARCH ADVISOR**
and follows `docs/project/RESEARCH_ADVISOR.md` (one question per pass: diagnosis, mechanism, design, adversarial review;
or a vulnerability review of a named scope). A Codex ADVISOR session commissioned for theory announces itself as
**Codex Astra RESEARCH ADVISOR** and follows `docs/project/RESEARCH_ADVISOR_CODEX.md` (one report per job: statistical
design, derivation, knowledge synthesis, theoretical critique). Everything above applies to both unchanged; a numerical
check or re-implementation of a formula is a simulation and is labelled so. A research pass is not a numbered pass: it
prunes and archives nothing and records in `memory/advisor-state.md` what the next numbered pass still owes. Entry point:
`.agents/skills/advisor-research/SKILL.md` (Claude: `/advisor-research <question>` or `/advisor-research vulnerability
<scope>`).

## Current state

This file holds the protocol only. Current state: the newest `PROGRESS.md` entries, `work/WORKBOARD.md`,
`work/BACKLOG.md` and the records they cite.
