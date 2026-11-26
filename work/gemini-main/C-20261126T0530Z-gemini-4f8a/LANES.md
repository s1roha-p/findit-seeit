# LANES — Parallel Orchestrator Contract for Part C (Env Recording & Contract-Gap Closure)

Lead orchestrator: **Gemini MAIN** `C-20261126T0530Z-gemini-4f8a` (Part C; taking over lead from Claude MAIN `C-20261122T1606Z-claude-0984`, which ran out of usage).
Branch: `part-c/dual-orch-test` (shared project checkout `C:\git\findit-seeit`; nobody switches it, commits, or pushes).
Method: `docs/project/ORCHESTRATION_METHOD.md` ("Parallel orchestrators").

## 0. Facts established by the lead

- **Conda environment `findsee` exists on this Windows 10 host:**
  - Python `3.11.18`, `numpy==2.4.6`, `opencv-python==5.1.0.95` (`cv2` `5.1.0`), `pytest==9.2.0`
  - Transitive `pytest` packages from `pip freeze`: `colorama==0.4.6`, `iniconfig==2.3.1`, `packaging==26.3`, `pluggy==1.7.0`, `Pygments==2.21.0`
  - `pillow` (listed under `all` in `docs/project/ENVIRONMENT.md`) is NOT installed yet.
- **Hardware probed on this host:**
  - OS: Microsoft Windows 10 Home `10.0.19045` (AMD64), `15.70 GB` (~16 GB) RAM
  - CPU: 11th Gen Intel Core i7-11370H @ 3.30 GHz (4 cores / 8 logical processors)
  - GPU: Intel Iris Xe Graphics (PnP Status `OK`); NVIDIA GeForce RTX 3060 Laptop GPU (present, PnP Status `Unknown`; `nvidia-smi` returned insufficient permissions, so VRAM is unverified; all runs so far are CPU-only)
- **Baseline tests:** `conda run -n findsee --no-capture-output python -m pytest tests/mode2 -q` passed `182 passed in 1.36s`.
- **Advisor ledgers:** `advisor/claude/advice.md`, `advisor/codex/advice.md`, and `advisor/gemini/advice.md` are all empty (`(none yet)`).
- **Prior trial records:** `work/claude-main/C-20261122T1606Z-claude-0984/LANES.md` (sections 0, 1, 2, 2R, 3), `work/gemini-main/C-20261122T1606Z-gemini-1384/HANDBACK.md`, and `work/gemini-main/C-20261122T1621Z-gemini-1777/HANDBACK.md`.

## 1. Lanes, disjoint write sets, and rules

| Lane | Orchestrator / session | Writes only | Workers |
|---|---|---|---|
| **G1 (Lead)** | Gemini MAIN `C-20261126T0530Z-gemini-4f8a` | `requirements.txt`, `docs/project/ENVIRONMENT.md`, `work/gemini-main/C-20261126T0530Z-gemini-4f8a/**`, `change_log/2026-11-26_05-30_part-c-env-and-lanes-gaps.md`, `PROGRESS.md`, `work/WORKBOARD.md` (adds both rows before launch; releases both rows at integration) | Lead directly |
| **C3 (Contract gaps)** | Codex MAIN `C-20261126T0530Z-codex-7c2d` (`codex` / `gpt-6.2-sol`, `reasoningEffort: high`) | `work/claude-main/C-20261122T1606Z-claude-0984/LANES.md` (ONLY adding `### Unspecified (do not assert)` subsections at the end of Section 1 and Section 2R), `work/codex-main/C-20261126T0530Z-codex-7c2d/**`, scratch `work/tmp/C-20261126T0530Z-codex-7c2d/` (delete when done), and ONLY the **last cell** of its own row in `work/WORKBOARD.md` (re-read immediately before editing) | Up to 2 parallel `codex` / `gpt-6.2-sol` (`reasoningEffort: medium`) runners via `delegate_task` |

### Rules for Lane C3 (`C-20261126T0530Z-codex-7c2d`)

1. **Frozen-contract preservation:** Do NOT modify any existing line or other section in `work/claude-main/C-20261122T1606Z-claude-0984/LANES.md`. Only add two `### Unspecified (do not assert)` subsections (one at the end of Section 1 and one at the end of Section 2R) with provenance tags, e.g.:
   - `### Unspecified (do not assert) (backfilled 2026-11-26 from Gemini 1384 hand-back)` at the end of Section 1
   - `### Unspecified (do not assert) (backfilled 2026-11-26 from Gemini 1777 hand-back)` at the end of Section 2R
2. **Non-contradiction rule:** Nothing in the new `"Unspecified (do not assert)"` lists may contradict any explicit requirement already stated in Sections 1 or 2R OR any assertion already present in `tests/mode2/{test_presets,test_pipeline,test_custom_preset,test_live}.py`. Verify every item against both the Part C code (`src/findsee/types.py`, `src/findsee/mode2/presets.py`, `src/findsee/mode2/pipeline.py`, `src/findsee/mode2/live.py`) and the existing test files.
3. **Worker split & no concurrent edit collision:** Each runner writes ONLY its own analysis report under `work/codex-main/C-20261126T0530Z-codex-7c2d/subagents/` (`R1_sec1_report.md` and `R2_sec2r_report.md`); Codex MAIN itself synthesizes, verifies, and applies the edits to `work/claude-main/C-20261122T1606Z-claude-0984/LANES.md`.
4. **Hard rules (kept by contract under `full-access`):**
   - Stay inside the fixed project root `C:\git\findit-seeit`.
   - Never read `.env`, `.env.*` (including `.env.example`), files ending in `.env`, or dump environment variables / secrets.
   - Read-only git only (`status`, `diff`, `log`, `show`). Never commit, push, switch branches, or run mutating git commands.
   - No package installs, downloads, or process kills.
   - No Python/pytest runs needed in Lane C3 (doc/contract audit lane; the lead runs `pytest` at integration).
   - UTF-8 for all files; ASCII-only in code.

## 2. Integration steps (Lead `C-20261126T0530Z-gemini-4f8a`)

1. Wait for Codex MAIN `C-20261126T0530Z-codex-7c2d` to finish and read its `HANDBACK.md`.
2. Audit `git status --short --branch` against the disjoint write sets and verify `work/tmp/C-20261126T0530Z-codex-7c2d` and `work/tmp/C-20261126T0530Z-gemini-4f8a` are clean/absent.
3. Review `git diff -- work/claude-main/C-20261122T1606Z-claude-0984/LANES.md` line-by-line against the code and `tests/mode2/*.py` to confirm zero edits outside the two new subsections and zero contradictions.
4. Verify `requirements.txt` (pure ASCII, parses cleanly, installed versions match pinned specs) and run `conda run -n findsee --no-capture-output python -m pytest tests/mode2 -v`.
5. Update `change_log/2026-11-26_05-30_part-c-env-and-lanes-gaps.md` to `STAGED`, append `PROGRESS.md` with `(gemini)` and `(codex)` bullets, update `SESSION.md`, release both rows on `work/WORKBOARD.md`, and present the report + commit plan to the user.
