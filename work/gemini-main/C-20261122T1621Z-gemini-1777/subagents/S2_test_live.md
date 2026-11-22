# Stage Brief S2 — Write `tests/mode2/test_live.py` (Lane C2 Round 2)

- **Session:** `C-20261122T1621Z-gemini-1777` (Gemini MAIN, Part C)
- **Target write set (ONLY this file):** `tests/mode2/test_live.py`
- **Authoritative contract:** `work/claude-main/C-20261122T1606Z-claude-0984/LANES.md` sections 0, 1, and 2R

## 1. Mandatory Reading Order

Read these files first (and ONLY these):
1. `AGENTS.md`
2. `CLAUDE.md`
3. `work/claude-main/C-20261122T1606Z-claude-0984/LANES.md` (sections 0, 1, 2R)
4. `tests/mode2/conftest.py`
5. `tests/mode2/test_presets.py`
6. `tests/mode2/test_pipeline.py`

## 2. Hard Rules (Full-Access Mode — Kept by Contract)

Because this task runs in `full-access` mode, no permission prompts will appear. You MUST enforce every rule below yourself:
- **NEVER open, read, or inspect** `src/findsee/mode2/live.py`, `src/findsee/mode2/presets.py`, or ANY file under `src/`. Your tests must be written strictly against `LANES.md` sections 1 and 2R so they stay an independent check of the contract.
- **Write ONLY `tests/mode2/test_live.py`**. Do not create, edit, or delete any other file (not `conftest.py`, not `test_pipeline.py`, not `WORKBOARD.md`, not `change_log/`, not scratch files).
- **NEVER open a real camera or display window, and NEVER import or test `run_live`.**
- **Run NO Python, pytest, or any interpreter** (no project environment exists on this machine; tests are `"not run: no project environment"`).
- **No installs, downloads, mutating git commands, `.env`/secret reads, outside-root accesses, or process kills.**
- **You are a worker:** do NOT launch any sub-agents.

## 3. Code & Comment Style (`CLAUDE.md` rules 1.4 and 5.7)

Match the exact quality and style of `tests/mode2/test_presets.py` and `tests/mode2/test_pipeline.py`:
- Start with a concise module docstring referencing `LANES.md` sections 1 and 2R, followed by `from __future__ import annotations`.
- Every helper class, method, helper function, and test function MUST have a clear docstring.
- Add detailed comments for **every code block, line, and variable** explaining purpose, reasoning, units/shapes/dtypes/ranges.
- **Strictly ASCII-only bytes (`0x00-0x7F`) in the `.py` file!** All non-ASCII characters inside test string literals MUST use Python `\uXXXX` or `\UXXXXXXXX` escape sequences (for example `"\u767d\u5167\u969c"`, `"caf\u00e9"`, `"\U0001f50d"`), and comments/docstrings must contain zero non-ASCII characters; UTF-8 encoding.
- Imports needed:
  - `from collections.abc import Callable, Iterable`
  - `import cv2`
  - `import numpy as np`
  - `import pytest`
  - `import findsee.mode2.live as live_mod`
  - `from findsee.mode2.live import FpsMeter, draw_status, open_camera`
- Reuse `synthetic_card_bgr` and `make_card_bgr` from `tests/mode2/conftest.py` (do NOT edit `conftest.py`).

## 4. Contract Test Specification (`LANES.md` sections 1 and 2R)

Implement comprehensive contract tests for `FpsMeter`, `draw_status`, and `open_camera` strictly matching `LANES.md` sections 1 and 2R:

### A. `FpsMeter(window: int = 30, clock: Callable[[], float] = time.perf_counter)`
Create a well-documented `_FakeClock` helper class (driven by an explicit list/sequence or mutable `now` timestamp, tracking `calls` count so tests can also assert `fps()` does not call `clock()`).
1. **Window validation:** `window < 2` (`1`, `0`, `-1`, `-10`) raises `ValueError`.
2. **Initial and single-tick behavior:**
   - With `0` ticks, `fps()` is `None` (both default `window=30` and explicit `window=2`).
   - `tick()` returns `None` (`assert meter.tick() is None`).
   - With `1` tick, `fps()` is `None`.
   - Calling `fps()` does not invoke `clock()` (only `tick()` reads the clock).
3. **Exact fps calculations:**
   - Uniform ticks `[0.0, 1.0 / 30.0, 2.0 / 30.0, 3.0 / 30.0]` -> `isinstance(val, float)` and `val == pytest.approx(30.0)`.
   - Two ticks `[10.0, 10.5]` -> `pytest.approx(2.0)`.
   - Non-uniform ticks `[0.0, 0.25, 0.5, 1.0]` with `window=4` -> `(4 - 1) / (1.0 - 0.0) == pytest.approx(3.0)`.
4. **Rolling window eviction (only newest `window` ticks kept):**
   - `window=2`: feed `[0.0, 1.0, 1.25]` -> oldest `0.0` evicted; kept `[1.0, 1.25]` -> `(2 - 1) / (1.25 - 1.0) == pytest.approx(4.0)`.
   - `window=4`: feed `[0.0, 10.0, 10.2, 10.4, 10.6, 10.8]` -> kept `[10.2, 10.4, 10.6, 10.8]` -> `(4 - 1) / (10.8 - 10.2) == pytest.approx(5.0)` (not corrupted by the slow first tick).
   - Default `window=30`: feed 35 ticks where the first 5 ticks span `0.0..4.0` (`1.0 s` apart) and ticks 5..34 advance by `0.02 s` (`50.0 fps`); after all 35 ticks, kept ticks are `[5..34]` (`n=30`, span `29 * 0.02 = 0.58 s`), so `fps() == pytest.approx(50.0)`.
5. **Zero or non-positive span:**
   - `[5.0, 5.0]` -> `None`; `[5.0, 5.0, 5.0]` -> `None`.
   - Negative span `[10.0, 9.0]` -> `None`.
   - Recovery when a strictly larger tick follows zero-span ticks: `[5.0, 5.0, 6.0]` with `window=3` -> `n=3`, span `6.0 - 5.0 = 1.0`, `fps() == pytest.approx(2.0)`.

### B. `draw_status(frame, text) -> np.ndarray`
1. **Shape, dtype, and non-mutation across sizes:**
   - Test across `(240, 320, 3)`, `(65, 97, 3)`, `(8, 8, 3)` using `make_card_bgr`, for both non-empty `"cataract | 30.0 fps"` and `""`.
   - Verify `isinstance(out, np.ndarray)`, `out.shape == frame.shape`, `out.dtype == np.uint8`, `out is not frame`, `not np.shares_memory(out, frame)`.
   - Save `original = frame.copy()`; verify `np.array_equal(frame, original)` after `draw_status`, and also after mutating `out[0, 0, 0]`.
2. **Empty string `""` returns an unchanged copy:**
   - Using `synthetic_card_bgr` (and `(8, 8, 3)`), verify `draw_status(frame, "")` returns a new non-sharing array that is `np.array_equal(out, frame)`.
3. **Non-empty text modifies pixels:**
   - On `synthetic_card_bgr`, `draw_status(synthetic_card_bgr, "cataract | 30.0 fps")` differs from `synthetic_card_bgr` (`not np.array_equal(out, synthetic_card_bgr)`), with pixel changes present inside the top-left quadrant `out[:120, :160]`.
   - On an all-black frame `np.zeros((240, 320, 3), dtype=np.uint8)`, `draw_status(black, "OK")` also modifies pixels (`np.any(out != black)`), verifying text strokes are visibly drawn on top of the filled black box.
   - **Do NOT assert** exact bounding-box coordinates, pixel height/width, font face, or exact BGR text color (not specified by section 2R).
4. **Printable ASCII boundaries accepted (`0x20` to `0x7E`):**
   - Test `" "` (`0x20`), `"~" ` (`0x7E`), and `" !~09AZaz"` (or all printable ASCII `"".join(chr(c) for c in range(0x20, 0x7F))`? Keep short or representative like `" "`, `"~"`, `"09AZaz!@#_-.:|"`): returns valid `(H, W, 3)` `uint8` new array without raising.
5. **Non-ASCII and control characters raise `ValueError`:**
   - Parametrize using ASCII-escaped string literals ONLY:
     - Control / DEL chars: `"\x00"`, `"\t"`, `"\n"`, `"\r"`, `"\x1f"`, `"\x7f"`, `"ok\nline2"`, `"fps\t30"`
     - Non-ASCII chars: `"\u0080"`, `"\u00a0"`, `"caf\u00e9"`, `"\u767d\u5167\u969c"`, `"\u85e5\u888b 30fps"`, `"\U0001f50d"`
   - Assert `pytest.raises(ValueError)` and ensure `frame` was not mutated.
6. **Invalid frames raise `ValueError`:**
   - Parametrize the invalid frame matrix matching `test_pipeline.py`:
     - Wrong dtype: `(240, 320, 3)` with `np.float32`, `np.float64`, `np.uint16`
     - Wrong ndim: `(240, 320)` and `(1, 240, 320, 3)` with `np.uint8`
     - Wrong channels: `(240, 320, 1)` and `(240, 320, 4)` with `np.uint8`
     - Too small: `(7, 8, 3)`, `(8, 7, 3)`, `(4, 4, 3)`, `(0, 0, 3)` with `np.uint8`
   - Also verify invalid frame with `text=""` still validates the frame and raises `ValueError` (e.g. `(7, 8, 3)` `uint8` and `(240, 320, 3)` `float32`).
   - **Do NOT test** non-`str` `text` or non-`ndarray` `frame` (section 2R does not specify `ValueError` vs `TypeError` for wrong Python types).

### C. `open_camera(index=0, width=1280, height=720) -> tuple[cv2.VideoCapture, tuple[int, int]]`
Use `monkeypatch.setattr(live_mod.cv2, "VideoCapture", FakeCapture)` (never construct a real `cv2.VideoCapture`).
Create a well-documented `_FakeCapture` factory/class:
- `__init__(self, index: int, *args: object, **kwargs: object)` stores `index`, `args`, `kwargs`, `set_calls: list[tuple[int, float]]`, `set_props: dict[int, float]`, `get_calls: list[int]`, `released: bool = False`, `release_calls: int = 0`, and records itself into `created: list[_FakeCapture]`.
- `isOpened(self) -> bool` returns configured `opened`.
- `set(self, prop_id: int, value: float) -> bool` appends `(prop_id, value)`, stores `set_props[prop_id] = value`, returns `True`.
- `get(self, prop_id: int) -> float` appends `prop_id`, returns `float(effective_width)` for `cv2.CAP_PROP_FRAME_WIDTH`, `float(effective_height)` for `cv2.CAP_PROP_FRAME_HEIGHT`, `0.0` otherwise.
- `release(self) -> None` sets `released = True` and increments `release_calls`.

Tests for `open_camera`:
1. **Default arguments (`open_camera()`):**
   - Requests `index=0`, `CAP_PROP_FRAME_WIDTH == 1280`, `CAP_PROP_FRAME_HEIGHT == 720` via `set` (assert via `set_props` or `set(...)` without assuming width is `set` before height!).
   - Returns `(cap, (eff_w, eff_h))` where `cap is created[0]`, `len(created) == 1`, `cap.released is False`, `isinstance(dims, tuple) and len(dims) == 2`, `type(eff_w) is int`, `type(eff_h) is int`, and `(eff_w, eff_h) == (1280, 720)` when `get` returns `(1280.0, 720.0)`.
2. **Explicit arguments & distinct effective dimensions from `get()`:**
   - Test keyword call `open_camera(index=2, width=1920, height=1080)` and positional call `open_camera(1, 800, 600)` when `_FakeCapture.get()` returns a different float effective size such as `640.0` and `480.0`.
   - Verify `cap.index` matches requested index, `cap.set_props[cv2.CAP_PROP_FRAME_WIDTH]` and `cap.set_props[cv2.CAP_PROP_FRAME_HEIGHT]` equal the requested width/height, and the returned size is `(640, 480)` with exact `int` elements (`type(eff_w) is int and type(eff_h) is int`), NOT `(1920, 1080)` or `(800, 600)`.
3. **Failure when `isOpened()` is `False`:**
   - Parametrize over `index` in `[0, 3]` (default and non-zero index).
   - With `opened=False`, verify `open_camera(index=index)` raises `RuntimeError`, `str(index) in str(exc_info.value)`, `created[0].released is True`, `created[0].release_calls == 1`, and `len(created) == 1` (confirms no fallback to another camera index).
   - **Do NOT assert** whether `set()` happened before or after `isOpened()` (that ordering is unspecified in section 2R).

## 5. Hand-back Format

When finished, provide a concise report listing:
- Confirmation of the single file written (`tests/mode2/test_live.py`)
- All test functions created and what each covers
- Confirmation that no `src/` file was opened, no real camera/window/`run_live` was used, zero non-ASCII bytes exist in the file, and no Python/pytest/interpreter was executed
- Any ambiguities noticed in `LANES.md` section 2R and how your tests interpreted them
