# 2026-11-22_16-06_part-c-lane-c1-enhance — Part C `enhance()` + presets (lane C1 of the parallel-orchestrator trial)

- **Status:** STAGED (tests pass in conda `findsee`; uncommitted)
- **Agent / part:** claude (lead orchestrator `C-20261122T1606Z-claude-0984`, one `stage-runner` worker) / C
- **Backlog id:** B-08 (review H5)
- **Commit(s):** uncommitted - temporary branch `part-c/dual-orch-test`; the user commits or discards
- **Baseline:** none

## Files
- `pyproject.toml` — new; only `[tool.pytest.ini_options]` (`pythonpath = ["src"]`, `testpaths`, `addopts`).
- `src/findsee/__init__.py` — new; package docstring, empty `__all__`.
- `src/findsee/types.py` — new; `Preset` frozen dataclass with `__post_init__` validation, `DENOISE_METHODS`,
  `DISPLAY_MODES`. Other shared types are left to their parts.
- `src/findsee/mode2/__init__.py` — new; re-exports `enhance`, `PRESETS`, `get_preset`.
- `src/findsee/mode2/presets.py` — new; draft `cataract` / `amd` presets (not evaluated), `get_preset`.
- `src/findsee/mode2/pipeline.py` — new; `enhance(image, preset)`: crop -> denoise -> CLAHE (Lab L) -> bicubic
  upscale -> unsharp mask -> display (`plain`, `binary_dark`, `color_precomp`).
- `docs/project/ARCHITECTURE.md` — `Preset` location and the `enhance` contract row corrected to the code.

## What and why
First implementation of Part C's interface (B-08), built to the frozen contract in
`work/claude-main/C-20261122T1606Z-claude-0984/LANES.md` section 1 so that lane C2 (Gemini MAIN) could write the
contract tests at the same time. Output size = input size (crop then upscale back), which keeps the display size
fixed for the app. Choices beyond the contract: a non-`Preset`/non-`str` preset raises `TypeError`; the CLAHE grid is
clamped to the crop size for crops smaller than `clahe_tile` pixels; numpy `float32` preset values are rejected.

## Evidence
| what | before | after | record ids | tier | split, n |
|---|---|---|---|---|---|
| unit tests (`tests/mode2`, both lanes) | none | 182 passed, 0 failed (conda `findsee`: Python 3.11.18, numpy 2.4.6, OpenCV 5.1.0, pytest 9.2.0; Windows 10 19045) | `evidence/pytest_mode2_20261122T1636Z.txt` in the lead's session folder | E0 | synthetic in-memory fixtures |

## Interfaces touched
`Preset` (types.py) and `enhance` defined for the first time, as in `ARCHITECTURE.md`, with the details fixed in
LANES.md; Part D (app) consumes `enhance`. No other part's interface changed.

## Rollback
Delete the files above (they are new) and restore `ARCHITECTURE.md`; nothing else depends on them yet except the lane
C2 tests and benchmark.

## Platform coverage
Windows 10: tests pass (conda `findsee`). macOS / Linux: untested. CPU only (no GPU code).

## Comment discipline
Read by the lead: every block, constant and variable is commented; every function and class has a docstring with
shapes, dtypes and ranges.

## Notes / follow-ups
- The user creates the environment (`docs/project/ENVIRONMENT.md`) and runs `python -m pytest tests/mode2`.
- The preset values are drafts; tuning needs Part D's simulation + OCR harness (B-09, B-11).
