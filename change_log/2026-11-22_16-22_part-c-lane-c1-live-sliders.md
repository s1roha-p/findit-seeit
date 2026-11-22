# 2026-11-22_16-22_part-c-lane-c1-live-sliders — Part C slider presets and live path (lane C1, round 2)

- **Status:** STAGED (unit tests pass in conda `findsee`; `run_live` not run on a camera; uncommitted)
- **Agent / part:** claude (lead orchestrator `C-20261122T1606Z-claude-0984`, one `stage-runner` worker) / C
- **Backlog id:** B-10 (review M2); demo sliders from `docs/project/WORK_SPLIT.md` Part C
- **Commit(s):** uncommitted - temporary branch `part-c/dual-orch-test`; the user commits or discards
- **Baseline:** none

## Files
- `src/findsee/mode2/presets.py` — adds `make_custom(base, *, zoom, clahe_clip, sharpen_amount, display, name)`.
- `src/findsee/mode2/live.py` — new: `FpsMeter`, `draw_status`, `open_camera`, `run_live`.
- `src/findsee/mode2/__init__.py` — also exports `make_custom`; deliberately does not import `live` (no GUI backend
  needed to import the package).

## What and why
The demo needs sliders (zoom, contrast, sharpen, display) and a live camera magnifier with a measured frame rate
(B-10). Built to `work/claude-main/C-20261122T1606Z-claude-0984/LANES.md` section 2R while Gemini lane C2 round 2
wrote the tests for the same text in parallel. `open_camera` reports requested and effective size and never falls
back to another camera (CLAUDE.md rule 8); frames are never written to disk (DATA_POLICY). Beyond 2R: a wrong-type
`base`/`preset` raises `TypeError`; a non-int `FpsMeter` window raises `ValueError`; `run_live` also accepts a
`Preset` and replaces non-ASCII preset-name characters with `?` in the overlay.

## Evidence
| what | before | after | record ids | tier | split, n |
|---|---|---|---|---|---|
| unit tests (`tests/mode2/test_custom_preset.py` 53, `test_live.py` 60) | none | all pass (in the 182/182 run) | `evidence/pytest_mode2_20261122T1636Z.txt` (lead's session folder) | E0 | fakes, no camera |
| `enhance` throughput, synthetic 1280x720, CPU, 8 OpenCV threads | none | cataract median 12.26 ms (~82 fps), amd median 16.45 ms (~61 fps); 60 frames after 5 warmup | `evidence/bench_mode2_fps_E0_20261122T1636Z.json` | E0 | synthetic, n=60 per preset |
| live fps at 720p from a real camera | none | null - `run_live` not run (no camera probed in this session) | none | none | none |

## Interfaces touched
New public names `make_custom` and `findsee.mode2.live.*`, defined in LANES.md 2R; consumed by Part D's app.

## Rollback
Delete `live.py`; remove `make_custom` from `presets.py` and from `mode2/__init__.py`.

## Platform coverage
Windows 10: unit tests pass (conda `findsee`). macOS / Linux: untested. Camera / display: not probed.

## Comment discipline
Read by the lead: every block, constant and variable commented; docstrings with shapes, dtypes, units.

## Notes / follow-ups
- Closing the window with its X button is not detected (backend-dependent); quit with q or Esc.
- After the environment exists: `python -m pytest tests/mode2`, then `run_live` on the demo machine to measure fps.
