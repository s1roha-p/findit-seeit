# Session record — `C-20261122T1606Z-claude-0984` (Claude MAIN, lead orchestrator, part C)

- **Task (user, 2026-11-22):** on a temporary branch, test two orchestrators (Claude + Gemini) working on Part C at
  the same time in T3 Code; Gemini orchestrator on Orchestrator Neon `high`, its runners on Gemini 4 Neon `medium`;
  improve the orchestration docs with a later third orchestrator (Codex) in mind.
- **Branch:** `part-c/dual-orch-test` from `main` `16135d0`; nothing committed (the user commits or discards).
- **Environment:** conda `findsee` (created by the user mid-session): Python 3.11.18, numpy 2.4.6, OpenCV 5.1.0,
  pytest 9.2.0; Windows 10 19045, AMD64, 8 logical CPUs. Before it existed, nothing was run.

## Timeline (UTC)

| Time | Event |
|---|---|
| 16:06 | Branch; facts (no code, no environment); `LANES.md` sections 0-3; workboard rows for C1 and C2 |
| 16:08 | Gemini orchestrator launched as a `delegate_task` child (session 1384) |
| 16:08-16:11 | C1 `stage-runner`: `types.Preset`, `presets`, `pipeline.enhance`, `pyproject.toml` |
| 16:13 | User asked for a top-level thread: child cancelled (it had written briefs only), relaunched as a thread |
| 16:18-16:24 | Gemini 1384: two `gemini-4-neon` runners wrote the contract tests and the benchmark; hand-back |
| 16:21 | Round 2 contract (`LANES.md` 2R); `full-access` launch refused (`runtime_mode_escalation_denied`, lead in `auto`); launched inheriting |
| 16:23-16:25 | C1R2 `stage-runner`: `make_custom`, `live.py` |
| 16:27 | User switched the lead to full access; round-2 thread interrupted (had only read) and relaunched `full-access` |
| ~16:30 | User created conda `findsee`; 182/182 tests pass |
| ~16:35 | Gemini 1777 hand-back (two full-access runners) |
| 16:36 | Evidence saved (`evidence/`); workboard released 16:38; backlog, PROGRESS, change logs updated |

## Evidence

- `evidence/pytest_mode2_20261122T1636Z.txt`: 182 passed, exit 0 (earlier identical runs: 182 passed in 0.66 s and
  0.70 s).
- `evidence/bench_mode2_fps_E0_20261122T1636Z.json`: E0 synthetic 1280x720, 60 frames after 5 warmup; cataract
  median 12.26 ms (~82 fps), amd median 16.45 ms (~61 fps). An earlier identical run: 12.25 ms / 16.26 ms.
- Usage (this session's transcripts): lead 64 responses, 64,339 output tokens; runners 19,141 and 18,056 output
  tokens. Codex/Gemini usage is outside the project root and was not read.

## Not done / next

- `run_live` on a real camera (B-10 E1 fps); preset tuning needs Part D's simulation + OCR harness (B-09, B-11).
- LANES 1 and 2R lack an "Unspecified (do not assert)" list; the method doc now requires one for future rounds.
- Merge decision for the branch is the user's (it was created as a temporary test branch).
