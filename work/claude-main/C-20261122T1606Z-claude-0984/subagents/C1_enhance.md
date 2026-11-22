# Stage C1 — Part C `enhance()` and presets (source only; bounded to lane C1's write set)

Orchestrator: Claude MAIN `C-20261122T1606Z-claude-0984` (lead of a parallel-orchestrator trial). A Gemini MAIN works
lane C2 (tests and benchmark) in the same checkout at the same time; do not touch its files.

## Settled (cite, do not re-decide)

- The interface is frozen in `work/claude-main/C-20261122T1606Z-claude-0984/LANES.md` section 1 - field names, value
  sets, error types, output shape = input shape, determinism, the step order, the exact display-mode invariants. The
  lane C2 tests are written against that text, so implement it literally.
- Step order from review H5 (`docs/project/PROPOSAL_REVIEW.md`, `docs/project/WORK_SPLIT.md` Part C).
- Libraries: `numpy` and `opencv-python` (`cv2`) only.
- **No project environment exists on this machine** (no conda env `findsee`, no `.venv`): do not run Python, pytest or
  any interpreter. Report "not run: no project environment".

## Steps

1. Read `AGENTS.md`, LANES.md, `docs/project/ARCHITECTURE.md` (Part C rows), `docs/project/WORK_SPLIT.md` Part C.
2. Write `pyproject.toml` with ONLY a `[tool.pytest.ini_options]` table: `pythonpath = ["src"]`, `testpaths =
   ["tests"]`, `addopts = "-ra"`. TOML has comments: explain each key. No `[project]` table (packaging is not decided).
3. `src/findsee/__init__.py`: package docstring, `__all__ = []`, no imports with side effects.
4. `src/findsee/types.py`: the `Preset` frozen dataclass exactly as LANES.md section 1, with `__post_init__` validation
   raising `ValueError` naming the field and the allowed values. Module-level constants `DENOISE_METHODS` and
   `DISPLAY_MODES` (tuples). A module docstring noting that the other shared types of `ARCHITECTURE.md` (`Snapshot`,
   `Detection`, ...) are added by their parts; do not write them.
5. `src/findsee/mode2/__init__.py`: re-export `enhance`, `PRESETS`, `get_preset`.
6. `src/findsee/mode2/presets.py`: `PRESETS` with the draft values in LANES.md, `get_preset(name)` raising `KeyError`
   with the known names. State in a comment that the values are drafts, not evaluated.
7. `src/findsee/mode2/pipeline.py`: `enhance(image, preset)` plus small private helpers, one per step:
   - validation (`ValueError`: not ndarray, dtype != uint8, ndim != 3, channels != 3, H or W < 8);
   - work on a copy; never modify the input;
   - crop: centre crop of size `(max(1, round(H / zoom)), max(1, round(W / zoom)))`; skip when zoom == 1.0;
   - denoise: `none`; `median` -> `cv2.medianBlur(img, 3)`; `bilateral` -> `cv2.bilateralFilter(img, 5, 50, 50)`;
     `nlm` -> `cv2.fastNlMeansDenoisingColored(img, None, 5, 5, 7, 21)`; name these parameters as module constants;
   - CLAHE: BGR -> Lab, `cv2.createCLAHE(clipLimit, (tile, tile))` on L, back to BGR;
   - upscale: `cv2.resize(..., (W, H), interpolation=cv2.INTER_CUBIC)` to the INPUT size; skip when zoom == 1.0;
   - unsharp mask: `cv2.GaussianBlur(sigma=1.0)` then `cv2.addWeighted(img, 1 + amount, blur, -amount, 0)`; skip when
     amount == 0;
   - display: `plain` returns as is; `binary_dark`: gray -> `cv2.adaptiveThreshold(gray, 255,
     ADAPTIVE_THRESH_GAUSSIAN_C, THRESH_BINARY_INV, 31, 10)` -> where mask is 255 write (0, 255, 255), else (0, 0, 0)
     (dark text becomes yellow on black); the block size must stay odd and must not exceed the image - clamp it to the
     largest odd value <= min(H, W) and >= 3; `color_precomp`: channel 0 as float32 times `blue_gain`, `np.rint`,
     clip 0-255, back to uint8; channels 1 and 2 untouched.
   - Determinism: avoid anything thread- or time-dependent. Call nothing that logs above DEBUG.
   - Accept a `str` preset via `get_preset` (avoid a circular import: `pipeline` imports from `presets`, not the
     reverse).
   - Type hints, `from __future__ import annotations`.
8. Re-read each file against LANES.md section 1 line by line; list any point where you had to interpret.

## Must-nots

Write only the files in steps 2-7 (plus nothing else - no tests, no `eval/`, no docs, no workboard). No Python runs, no
installs, no git commands beyond read-only ones. Detailed comments on every block, line and variable; docstrings on
every function and class (shapes, dtypes, ranges). ASCII-only in code and comments except where Traditional Chinese
user text is needed (none here).

## Hand-back

Files written with sha256 (`sha256sum` via Bash is fine), a per-file summary, the interpretation list of step 8,
"tests: not run: no project environment", deviations from this brief, and the next bounded action.
