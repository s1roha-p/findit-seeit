# FindSee — 幫長輩找得到也看得清

Final project of *Introduction to Multimedia Technology* (多媒體技術概論). A dual-mode home assistant for elders:

- **Mode 1 · 找東西 (find things):** periodic snapshots of the places things are usually left, an open-vocabulary
  detector and a "last-seen" memory. The elder asks by voice ("我的老花眼鏡在哪裡？"); the system answers by voice
  ("在客廳茶几上，遙控器左邊") and shows the photo with the item boxed.
- **Mode 2 · 看得清 (see clearly):** a smart magnifier that pre-compensates the image for cataract and macular
  degeneration - crop and zoom, denoise, CLAHE, sharpening, and a high-contrast or color pre-compensated display - for
  drug bags, appointment slips and menus.

Team: 賴聲愷 · 潘仲奇 · 廖彥翔 · 邱廷軒 (parts in `docs/project/WORK_SPLIT.md`, owners to be confirmed).

> Status (2026-11-20): documents and agent harness only; no product code yet. Start with
> `docs/project/PROPOSAL_REVIEW.md` and the decisions in `work/BACKLOG.md`.

## Repository map

| Path | What |
|---|---|
| `docs/project/PROPOSAL_REVIEW.md` | review of the midterm proposal, issues ranked, decisions to take |
| `docs/project/WORK_SPLIT.md` | the four parts (A-D), deliverables, timeline |
| `docs/project/ARCHITECTURE.md` | package layout and the interfaces between parts |
| `docs/project/EVALUATION_PROTOCOL.md` | evidence tiers, splits, metrics, result records |
| `docs/project/DATA_POLICY.md` | consent, redaction, what may leave the machine |
| `docs/project/ENVIRONMENT.md` | proposed Python stack, caches, variable names |
| `docs/project/HOOKS.md`, `ORCHESTRATION_METHOD.md` | the Claude Code guard; how agents run stages |
| `docs/project/RESEARCH_ADVISOR.md`, `RESEARCH_ADVISOR_CODEX.md` | research advisor roles: Claude Mythos (design, adversarial and vulnerability reviews), Codex Astra (statistics, theory, literature) |
| `src/findsee/`, `tests/`, `eval/`, `scripts/` | code (to be written) |
| `work/` | workboard, backlog, evaluation records, agent session folders |
| `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `AGENT_ADVISOR.md` | rules for coding agents (Claude Code, Codex, Gemini) |
| `advisor/` | review ledgers of advisor sessions |

## Getting started

1. Clone, then create the environment (`docs/project/ENVIRONMENT.md`): conda env `findsee` or a `.venv` in the folder.
2. Read `docs/project/WORK_SPLIT.md`, pick a part, write your name in its owner cell.
3. Work on a branch `part-<a|b|c|d>/<topic>`; open a pull request to `main`; one other member reviews.
4. Using a coding agent: launch it from the project folder with the environment active. Claude Code loads
   `CLAUDE.md` and the hooks; Codex reads `AGENTS.md`; Gemini reads `GEMINI.md`. Check the guard once per machine:
   `python .claude/hooks/selftest.py`.
5. Never commit `.env`, `data/raw/`, model weights, or photos/recordings of people (`docs/project/DATA_POLICY.md`).
