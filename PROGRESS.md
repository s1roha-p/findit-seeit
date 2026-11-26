# PROGRESS — narrative of the project

Newest entries at the end. Each entry: `## <UTC> - <title> (<Agent> MAIN, part <X>)`, one or two tagged bullets
(`(claude)`, `(codex)`, `(gemini)`), record ids, what is for the user. Keep each under about 600 bytes.

## 2026-11-20T05:30Z - Repository pack created; proposal reviewed (Claude, set-up)
- (claude) Documents, agent harness and hook guard in place (every git rule asks, R6; Gemini a MAIN agent; research
  advisor roles for Claude Mythos and Codex Astra); guard self-test 0 failures in all three launch states
  (`change_log/2026-11-20_00-00_initial-pack.md`).
- (claude) Proposal reviewed (`docs/project/PROPOSAL_REVIEW.md`); four parts proposed (`docs/project/WORK_SPLIT.md`).
  For the team: decisions D1-D8 and proposed research commissions V-1, R-1, T-1, T-2 in `work/BACKLOG.md`.

## 2026-11-22T16:38Z - Part C v1 built by two parallel orchestrators (Claude MAIN lead + Gemini MAIN, part C)
- (claude) Trial of parallel orchestrators on branch `part-c/dual-orch-test` (uncommitted): frozen contract in
  `work/claude-main/C-20261122T1606Z-claude-0984/LANES.md`; C1 wrote `enhance()`, presets, `make_custom`, `live.py`.
  182/182 tests pass, E0, conda `findsee`, Windows 10. E0 synthetic 720p CPU: cataract ~82 fps, amd ~61 fps (not a
  camera run). Method: `docs/project/ORCHESTRATION_METHOD.md` "Parallel orchestrators".
- (gemini) C2 wrote the contract tests and `eval/bench_mode2_fps.py` blind to the C1 code (two sessions, 1384 and
  1777, `gemini-4-neon` runners); they passed on first run against C1.

## 2026-11-26T05:45Z - Part C env recorded; LANES gaps closed (Gemini MAIN lead + Codex MAIN, part C)
- (gemini) Added `requirements.txt` (`numpy==2.4.6`, `opencv-python==5.1.0.95`, `pytest==9.2.0`; `pillow` absent) & laptop row in `docs/project/ENVIRONMENT.md`; 182/182 `tests/mode2` pass, E0, conda `findsee` (`change_log/2026-11-26_05-30_part-c-env-and-lanes-gaps.md`).
- (codex) Added `Unspecified (do not assert)` lists to `LANES.md` §1 & §2R using two `gpt-6.2-sol` medium runners (`work/codex-main/C-20261126T0530Z-codex-7c2d/HANDBACK.md`).
