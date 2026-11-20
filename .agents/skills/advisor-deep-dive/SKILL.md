---
name: advisor-deep-dive
description: Focused advisory report for the ADVISOR role on ONE named topic of the FindSee project - evaluation design, Mode 1 detection and memory, voice pipeline, Mode 2 enhancement, integration, privacy, or demo readiness. Use when the user asks for a deep dive or types /advisor-deep-dive <topic>. Writes one report to advisor/<agent>/reports/ plus one ledger entry.
---

# advisor-deep-dive — one topic, one report

Writes ONLY `advisor/<agent>/reports/YYYY-MM-DD_<topic>.md` and one entry in `advisor/<agent>/advice.md`. No app runs,
tests or evaluations; cheap read-only checks on saved records only (CPU, ≤ ~60 s, output to `tmp/`, project
environment named).

1. Pin the topic to one checklist below (or the user's narrower phrasing); read in the `AGENT_ADVISOR.md` order,
   scoped to it.
2. Gather evidence from records, tests, change logs and source (numbers, tiers, splits, n, commits).
3. Write the report with the template; every claim cites a file / key / record id; every recommendation has predicted
   outcomes, cost and the decision it changes.
4. Add ONE ledger entry whose Advice is the report's headline and whose Evidence is the report path; log it.

```markdown
# <Topic> — advisor deep dive (<agent>, YYYY-MM-DD)
Scope: <what was read; records / files; commit>.
## 1. Question and why it matters now
## 2. What the evidence shows (numbers with file + key; tier, split, n)
## 3. Assumptions the current plan rests on - and which survive
## 4. Alternatives not yet excluded
## 5. Recommendations - check or change; predicted outcome per hypothesis; cost; decision changed
## 6. What would falsify this report
## 7. For the user (not the main agents)
```
Length 50-120 lines.

## Topic checklists

**evaluation** — session-level split, test set opened once per frozen configuration, simulation parameters and
version, OCR engine and language, CER computation (normalization, punctuation), size bands, n per arm, legibility test
design (order, readers, viewing distance). Deliverable: the change that most raises the trustworthiness of the slide
numbers.

**mode1** — detector choice and its class list, recall per item, score threshold, IoU rule, snapshot cadence,
memory-store tie and staleness rules, retention. Deliverable: the three cheapest improvements to last-seen accuracy.

**voice** — ASR model and size, CER on the team's recordings, noise conditions, intent synonyms, VLM prompt and output
checks, TTS clarity, latency budget by stage, cloud vs local and what is uploaded. Deliverable: the latency/accuracy
plan for the demo questions.

**mode2** — pipeline order, filter choices on thin strokes, CLAHE color space, upscale factor, sharpening halos,
binarization vs color pre-compensation per condition, fps on the demo machine. Deliverable: preset recommendations with
the evidence that would confirm them.

**integration** — interfaces vs code, stubs left, error paths, the handoff, start-up time, a clean-clone run.
Deliverable: the integration risks ranked with the test that exposes each.

**privacy** — consent records, redaction, what leaves the machine, retention, keys handling, disclaimer text.
Deliverable: gaps against `DATA_POLICY.md`.

**demo** — script, fallbacks (recorded video, offline TTS, cached VLM answers), freeze discipline, timing per part.
Deliverable: PASS / NOT YET per demo step with what is missing.
