# Stage C1R2 — `make_custom` slider presets and the live path `live.py` (source only)

Orchestrator: Claude MAIN `C-20261122T1606Z-claude-0984` (lead). A Gemini MAIN (`C-20261122T1621Z-gemini-1777`) is
writing `tests/mode2/test_custom_preset.py` and `tests/mode2/test_live.py` against the same contract **right now**; a
round-1 Gemini session may still touch its own round-1 files. Never touch `tests/**` or `eval/**`.

## Settled (cite, do not re-decide)

- The interface is frozen in `work/claude-main/C-20261122T1606Z-claude-0984/LANES.md` **section 2R**. The tests are
  written against that text, so implement it literally (names, signatures, defaults, error types, return types).
- Round-1 code is in place and reviewed: `src/findsee/types.py`, `src/findsee/mode2/{presets,pipeline,__init__}.py`.
  Reuse `pipeline._validate_image` for `draw_status`'s frame check rather than duplicating it.
- **No project environment exists**: run no Python, pytest or any interpreter.

## Steps

1. Read `AGENTS.md`, LANES.md sections 1 and 2R, and the round-1 source files above.
2. `presets.py`: add `make_custom` (keyword-only overrides; build with `dataclasses.replace` so `Preset` validation
   runs; a `str` base goes through `get_preset`). Add it to `__all__`. Do not change `PRESETS` or `get_preset`.
3. New `live.py`:
   - `FpsMeter` with `collections.deque(maxlen=window)`; `clock` injectable; exact formula from 2R.
   - `draw_status(frame, text)`: validate the frame with `pipeline._validate_image`; text must be `str` and every
     character in `0x20-0x7E` (else `ValueError`); copy the frame; empty text returns the copy; otherwise
     `cv2.getTextSize` with `FONT_HERSHEY_SIMPLEX`, scale and thickness as named module constants, a filled black
     rectangle clipped to the frame, then white text with `cv2.LINE_AA`.
   - `open_camera(index=0, width=1280, height=720)`: exactly as 2R; call `cv2.VideoCapture(index)` through the module
     attribute `cv2.VideoCapture` (the tests monkeypatch `findsee.mode2.live.cv2.VideoCapture`); `int(round(get(...)))`.
   - `run_live(...)`: as 2R; `logging.getLogger(__name__)`; resolve the preset name with `get_preset`; keys via
     `cv2.waitKey(1) & 0xFF`; always `release()` and `cv2.destroyAllWindows()` in `finally`; a failed `read()` logs a
     WARNING and stops the loop (no silent retry); no frame is ever written to disk.
   - Module docstring: the privacy note (frames stay in memory) and that `run_live` needs a camera and a display.
4. `mode2/__init__.py`: also export `make_custom` (do not import `live` there, so importing the package never needs
   a GUI backend).
5. Re-read every file against LANES 2R line by line; list each point you interpreted.

## Must-nots

Write only `src/findsee/mode2/presets.py`, `src/findsee/mode2/live.py`, `src/findsee/mode2/__init__.py`. No Python
runs, no installs, no git commands beyond read-only ones. Detailed comments on every block, line and variable;
docstrings with shapes, dtypes, units and ranges; ASCII only.

## Hand-back

Files with sha256, per-file summary, the interpretation list, "tests: not run: no project environment", deviations,
next bounded action.
