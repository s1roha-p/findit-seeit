# Hand-back: Lane C2 (`C-20261122T1606Z-gemini-1384`)

- **From:** Gemini MAIN orchestrator `C-20261122T1606Z-gemini-1384` (Part C, Lane C2)
- **To:** Lead orchestrator Claude MAIN `C-20261122T1606Z-claude-0984` (Part C, Lane C1)
- **Branch:** `part-c/dual-orch-test` (shared checkout, untouched beyond Lane C2 write set)
- **Completed:** `2026-11-22T16:24Z`

## 1. Outcome
Lane C2 complete and staged: Mode 2 pytest contract tests (`tests/mode2/`) and E0 synthetic CPU FPS benchmark (`eval/bench_mode2_fps.py`) were built strictly against `LANES.md` section 1 and verified line-by-line (not run: no project environment).

## 2. Files written
- `tests/mode2/conftest.py` (256 lines) — Pure in-memory BGR `uint8` synthetic text-card generator and pytest fixtures (`synthetic_card_bgr`, `clean_card_bgr`, `make_card_bgr`) scaling safely down to `8x8` with zero disk I/O and nothing of people.
- `tests/mode2/test_presets.py` (175 lines) — Contract tests for `findsee.types.Preset` (frozen dataclass, equality/hashing, keyword-arg boundaries, `ValueError` validation) and `findsee.mode2.presets` (`PRESETS`, `get_preset`).
- `tests/mode2/test_pipeline.py` (392 lines) — Contract tests for `findsee.mode2.pipeline.enhance` (shape/dtype across standard, odd, and `8x8` sizes, input immutability/no shared memory, determinism, `str` vs `Preset`, invalid `ndarray` rejection, `binary_dark`, `color_precomp`, `zoom == 1.0` vs `2.0`, all 4 `denoise` modes, `sharpen_amount == 0.0`, and logging cap).
- `eval/bench_mode2_fps.py` (496 lines) — E0 synthetic 1280x720 CPU FPS microbenchmark (backlog B-10, `time.perf_counter()`, `"tier": "E0"`, `"record_id": null` with reason, ASCII JSON stdout, zero runtime disk writes, no camera).
- `work/gemini-main/C-20261122T1606Z-gemini-1384/SESSION.md` — Session log recording resume in top-level thread, runner task/thread IDs, verification, and completion.
- `work/gemini-main/C-20261122T1606Z-gemini-1384/HANDBACK.md` — This hand-back report for the lead orchestrator.
- `change_log/2026-11-22_16-06_part-c-lane-c2-tests.md` — Lane C2 change log updated to `Status: STAGED`.
- `work/WORKBOARD.md` — Updated ONLY the last cell of row `C-20261122T1606Z-gemini-1384` to point to `HANDBACK.md` and the staged change log.

## 3. Runners launched
Launched both edit-only runners in parallel via `delegate_task` (`providerInstanceId: "antigravity"`, `model: "gemini-4-neon"`, `options: {"thought_level": "medium"}`, `isolation: "shared"`, no `runtimeMode`):

- **S1** (`taskId`: `node:delegated-task:command%3Amcp%3Ae2e7861b-8592-4236-a1b3-264382afbd00%3Adelegate-task%3Ac2-s1-mode2-contract-tests-top-level`, `childThreadId`: `thread:delegated-task:command%3Amcp%3Ae2e7861b-8592-4236-a1b3-264382afbd00%3Adelegate-task%3Ac2-s1-mode2-contract-tests-top-level`):
  - Wrote `tests/mode2/conftest.py`, `tests/mode2/test_presets.py`, and `tests/mode2/test_pipeline.py` without reading `src/**` or `pyproject.toml`.
  - Applied all proactive orchestrator refinements from the launch brief (`caplog.at_level(logging.DEBUG)` with `levelno > logging.DEBUG`, thin strokes for `adaptiveThreshold`, keyword-only `Preset` construction, rounding-mode-agnostic `[floor, ceil]` bounds at dyadic `blue_gain=1.5`, and no `sys.path` hacks).
  - Verified line-by-line against `LANES.md` section 1 and `CLAUDE.md` rule 1.4 (`0` non-ASCII bytes, `0` post-write corrections needed).
- **S2** (`taskId`: `node:delegated-task:command%3Amcp%3Ae2e7861b-8592-4236-a1b3-264382afbd00%3Adelegate-task%3Ac2-s2-mode2-fps-benchmark-top-level`, `childThreadId`: `thread:delegated-task:command%3Amcp%3Ae2e7861b-8592-4236-a1b3-264382afbd00%3Adelegate-task%3Ac2-s2-mode2-fps-benchmark-top-level`):
  - Wrote `eval/bench_mode2_fps.py` without reading `src/**` or `pyproject.toml`.
  - Applied all proactive orchestrator refinements (`pathlib`-based `src/` prepend to `sys.path`, `8x8` safe synthetic frame rendering guard, explicit `RuntimeError` validation outside the timed loop instead of `assert`, `json.dumps(..., ensure_ascii=True)`, and zero disk writes / camera calls).
  - Verified line-by-line against `LANES.md` section 1, `EVALUATION_PROTOCOL.md`, and `CLAUDE.md` rule 1.4 (`0` non-ASCII bytes, `0` post-write corrections needed).

## 4. Contract ambiguities in `LANES.md` section 1 and how the tests read them
1. **Non-`ndarray` `image` and non-`Preset`/`str` `preset` exception types:** Section 1 states "Anything else raises `ValueError`" in the bullet on `np.ndarray` properties (`dtype`, `ndim`, channel count, `< 8x8`) without explicitly naming `TypeError` vs `ValueError` for non-`ndarray` or wrong-type `preset`. Reading: tests only pass invalid `np.ndarray` shapes/dtypes (asserting `ValueError`) and `str` / `Preset` presets (asserting `KeyError` on unknown `str`).
2. **`Preset` non-domain edge cases (`name` whitespace, `NaN`/`inf`, `bool`, float for `clahe_tile`):** Section 1 specifies `name` non-empty and numeric inequalities without addressing whitespace-only strings, IEEE `NaN`/`inf`, Python `bool` subclassing `int`, or type coercion. Reading: left untested so tests do not reject a compliant implementation.
3. **`Preset` field order and `blue_gain` validation scope:** Section 1 says `blue_gain >= 1.0`, "used only by `color_precomp`", without stating whether `blue_gain < 1.0` fails unconditionally or only under `color_precomp`. Reading: tests always instantiate `Preset` by keyword arguments and test invalid `blue_gain` against a `display="color_precomp"` base preset.
4. **Draft preset parameters (`"cataract"`, `"amd"`):** Marked "Draft values (not evaluated; tuning is a later stage)". Reading: tests assert only exact registry keys `{"cataract", "amd"}`, `preset.name == key`, and allowed field domains; display-mode tests explicitly set `display` via `dataclasses.replace` instead of assuming draft display modes.
5. **`binary_dark` `adaptiveThreshold` `blockSize` and `C`:** Section 1 leaves `blockSize` and `C` unspecified (assuming `C > 0` so uniform bright background maps to black `(0, 0, 0)` rather than yellow `(0, 255, 255)`). Reading: polarity test uses thin dark strokes on a clean `(235, 235, 235)` card and checks only that every pixel is black or yellow, both appear, and yellow pixel fraction `< 0.5`.
6. **`color_precomp` rounding tie-break and intermediate precision:** Section 1 says "multiplied by `blue_gain`, rounded and clipped to 255" without choosing round-half-to-even (`np.rint`), round-half-up, or `float32` vs `float64`. Reading: tests check `>=` at `blue_gain=1.3`, exact equality at `blue_gain=1.0`, and rounding-mode-agnostic `[clip(floor(raw), 0, 255), clip(ceil(raw), 0, 255)]` bounds at dyadic `blue_gain=1.5`.
7. **Minimum `(8, 8, 3)` canvas with `zoom > 1.0` and `clahe_tile=8`:** Section 1 leaves crop rounding (`int`/`floor`/`round`) at `(8, 8)` unspecified. Reading: tests assert only that `(8, 8, 3)` executes cleanly and returns `(8, 8, 3)` `uint8` for both `"cataract"` and `"amd"`.
8. **Logging cap ("no logging above DEBUG"):** Reading: tests capture with `caplog.at_level(logging.DEBUG)` and fail only if any record has `record.levelno > logging.DEBUG`, permitting `DEBUG` logs while rejecting `INFO` and higher.

## 5. Tests
`not run: no project environment` (no conda env `findsee` or `.venv` exists on this host; no Python, pytest, or benchmark interpreter was invoked).

## 6. What needs the lead or the user
- **Lead (`C-20261122T1606Z-claude-0984`):** Cross-check `tests/mode2/**` and `eval/bench_mode2_fps.py` against Lane C1's `src/findsee/**` and `pyproject.toml`, decide any of the section-1 ambiguities in item 4 if needed, update `PROGRESS.md` and `work/BACKLOG.md` (B-08 / B-10), and release both claims on `work/WORKBOARD.md`.
- **User:** Provision the project environment (`conda` `findsee` or `.venv` with `numpy`, `opencv-python`, `pytest`), run `python -m pytest tests/mode2` and `python eval/bench_mode2_fps.py`, and handle git commit/push when ready.

## 7. Observations on the parallel-orchestrator method (for a later third orchestrator, e.g. Codex)
1. **Child-to-top-level thread migration worked cleanly:** Persistent `SESSION.md`, `subagents/` briefs, and the WIP `change_log/` file let the resumed top-level session pick up immediately after `task_cancel`. Adding an explicit pre-launch check that cancelled runners left no partial target files is worth keeping as a standard step.
2. **Top-level hand-back contract:** Unlike a `delegate_task` child, a top-level thread does not wake the lead automatically on completion. Requiring `HANDBACK.md` + final message + updating the last cell of the lane's workboard row gives the lead a reliable deterministic hand-back signal; document this explicitly for Codex / future top-level lanes.
3. **Workboard rule tension (`WORKBOARD.md` vs `LANES.md`):** `WORKBOARD.md` tells sessions to put `(released <UTC>)` in the first cell, whereas parallel-orchestrator non-lead lanes must touch **only the last cell** of their own row so only the lead releases claims at integration. Clarifying this exception in `docs/project/ORCHESTRATION_METHOD.md` ("Shared files") avoids accidental multi-cell edits by a third orchestrator.
4. **Explicit non-contract section in `LANES.md`:** Blind-room test generation against `LANES.md` §1 succeeded with zero source reads, but adding a short "Explicitly unspecified (do not assert)" list to `LANES.md` §1 would prevent future orchestrators (e.g., Codex in C3) from spending judgment calls on unstated edge cases like type errors vs `ValueError` or float rounding modes.
5. **Disjoint `eval/` ownership & non-hook enforcement:** Having disjoint file targets (`eval/bench_mode2_fps.py` in C2 vs `eval/eval_mode2_ocr.py` in C3) prevented any collision on the shared checkout. Because neither Gemini nor Codex runs under `.claude/hooks/guard.py`, repeating the hard rules in each self-contained runner prompt plus running orchestrator-level `git status` and non-ASCII byte checks after workers complete proved effective and should be reused for Codex.
