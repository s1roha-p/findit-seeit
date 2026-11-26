# 2026-11-26_05-30_part-c-env-and-lanes-gaps — Record Part C environment and close LANES.md contract gaps

- **Status:** STAGED (182/182 `tests/mode2` pass in conda `findsee`; uncommitted)
- **Agent / part:** gemini (lead `C-20261126T0530Z-gemini-4f8a`) + codex (Lane C3 `C-20261126T0530Z-codex-7c2d`) / C
- **Backlog id:** B-08, B-10
- **Commit(s):** uncommitted - temporary branch `part-c/dual-orch-test`; the user commits or discards
- **Baseline:** `work/claude-main/C-20261122T1606Z-claude-0984/evidence/pytest_mode2_20261122T1636Z.txt` (182 passed)

## Files
- `requirements.txt` — new; pinned Part C dependencies from conda env `findsee` (`numpy==2.4.6`, `opencv-python==5.1.0.95`, `pytest==9.2.0`), with rebuild instructions and transitive/uninstalled notes in comments.
- `docs/project/ENVIRONMENT.md` — updated status header, verified Python `3.11.18`, and filled in the dev laptop row in `## Machines`.
- `work/claude-main/C-20261122T1606Z-claude-0984/LANES.md` — added `### Unspecified (do not assert)` subsections at the end of Section 1 and Section 2R (Lane C3, Codex MAIN).

## What and why
Claude MAIN (`C-20261122T1606Z-claude-0984`) ran out of usage after planning the next two small Part C clean-up stages: (1) recording the verified conda `findsee` environment in `requirements.txt` and `docs/project/ENVIRONMENT.md` so teammates can rebuild the same stack, and (2) adding `"Unspecified (do not assert)"` lists to `LANES.md` sections 1 and 2R from both Gemini hand-backs (`1384` and `1777`) so the contract satisfies `docs/project/ORCHESTRATION_METHOD.md`.

## Evidence
| what | before | after | record ids | tier | split, n |
|---|---|---|---|---|---|
| `tests/mode2` in conda `findsee` | 182 passed (2026-11-22) | 182 passed in 0.94s (0 failed, 0 skipped; Python 3.11.18, numpy 2.4.6, OpenCV 5.1.0, pytest 9.2.0, Windows 10 19045) | lead integration stdout (`C-20261126T0530Z-gemini-4f8a/SESSION.md`) | E0 | synthetic in-memory fixtures |
| `requirements.txt` pins vs conda `findsee` | absent | pure ASCII, 3/3 pins match installed metadata (`numpy==2.4.6`, `opencv-python==5.1.0.95`, `pytest==9.2.0`) | `pip freeze` + `importlib.metadata` check | n/a | Windows 10 19045 |
| `LANES.md` §1 & §2R contract gap backfill | no `Unspecified (do not assert)` lists | two additions-only hunks (+33/-0 lines), zero frozen clauses changed, zero test contradictions | `work/codex-main/C-20261126T0530Z-codex-7c2d/HANDBACK.md` | n/a | static cross-check against `src/findsee/` & `tests/mode2/` |

## Interfaces touched
None (`work/claude-main/C-20261122T1606Z-claude-0984/LANES.md` received additive `Unspecified (do not assert)` notes only; no frozen interface or `src/` files changed).

## Rollback
Delete `requirements.txt` and restore `docs/project/ENVIRONMENT.md` and `work/claude-main/C-20261122T1606Z-claude-0984/LANES.md` to commit `397d7eb`.

## Platform coverage
Windows 10 Home 10.0.19045 (AMD64, conda `findsee`, CPU): `182 passed in 0.94s`. macOS / Linux: untested.

## Comment discipline
`requirements.txt` has top-of-file provenance/rebuild comments and a descriptive comment above every pinned dependency; no Python code was modified.

## Notes / follow-ups
- `pillow` (listed under `all` in `docs/project/ENVIRONMENT.md`) is not installed in conda `findsee` yet and is omitted from `requirements.txt`.
- `NVIDIA GeForce RTX 3060 Laptop GPU` is present in PnP (`Status: Unknown`) while `nvidia-smi` returned insufficient permissions, so VRAM remains unverified.
- Codex Lane C3 noted minor static doc/edge-case items in existing `src/` (outside this change's write scope): `pipeline.py:198-201` note says `min(tile, h, w)` square while code uses `(min(tile, w), min(tile, h))`; `types.py:40` comment overgeneralizes NumPy float subclassing (`np.float32` is rejected); static overflow risks for extreme `blue_gain` (`1e40` in `float32`) or huge Python `int` in `math.isfinite`.
