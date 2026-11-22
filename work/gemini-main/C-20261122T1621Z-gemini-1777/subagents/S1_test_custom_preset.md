# Stage Brief S1 — Write `tests/mode2/test_custom_preset.py` (Lane C2 Round 2)

- **Session:** `C-20261122T1621Z-gemini-1777` (Gemini MAIN, Part C)
- **Target write set (ONLY this file):** `tests/mode2/test_custom_preset.py`
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
- **NEVER open, read, or inspect** `src/findsee/mode2/presets.py`, `src/findsee/mode2/live.py`, or ANY file under `src/`. Your tests must be written strictly against `LANES.md` sections 1 and 2R so they stay an independent check of the contract.
- **Write ONLY `tests/mode2/test_custom_preset.py`**. Do not create, edit, or delete any other file (not `conftest.py`, not `test_presets.py`, not `WORKBOARD.md`, not `change_log/`, not scratch files).
- **Run NO Python, pytest, or any interpreter** (no project environment exists on this machine; tests are `"not run: no project environment"`).
- **No installs, downloads, mutating git commands, `.env`/secret reads, outside-root accesses, or process kills.**
- **You are a worker:** do NOT launch any sub-agents.

## 3. Code & Comment Style (`CLAUDE.md` rules 1.4 and 5.7)

Match the exact quality and style of `tests/mode2/test_presets.py` and `tests/mode2/test_pipeline.py`:
- Start with a concise module docstring referencing `LANES.md` sections 1 and 2R, followed by `from __future__ import annotations`.
- Every helper function and every test function MUST have a clear docstring.
- Add detailed comments for **every code block, line, and variable** explaining purpose, reasoning, bounds/types/shapes/dtypes.
- **Strictly ASCII-only bytes (`0x00-0x7F`)** in the file (no non-ASCII dashes, arrows, quotes, or symbols in docstrings, comments, or literals); UTF-8 encoding.
- Imports needed:
  - `import dataclasses`
  - `import numpy as np`
  - `import pytest`
  - `from findsee.mode2.pipeline import enhance`
  - `from findsee.mode2.presets import PRESETS, get_preset, make_custom`
  - `from findsee.types import Preset`
- Reuse the `synthetic_card_bgr` fixture from `tests/mode2/conftest.py` (do NOT edit `conftest.py`).

## 4. Contract Test Specification (`LANES.md` sections 1 and 2R)

Implement comprehensive contract tests covering all requirements in `LANES.md` section 2R for `make_custom(base, *, zoom=None, clahe_clip=None, sharpen_amount=None, display=None, name="custom") -> Preset`:

1. **Default `name="custom"` and copying all un-overridden fields:**
   - Test with `"cataract"`, `"amd"`, and a distinct custom `Preset` base (e.g., `Preset(name="custom_base", zoom=1.5, denoise="nlm", clahe_clip=2.5, clahe_tile=4, sharpen_amount=0.8, display="plain", blue_gain=1.75)`).
   - Compare against `get_preset(key)` (do NOT hardcode draft field values for `"cataract"` or `"amd"`).
   - Verify `isinstance(result, Preset)`, `result.name == "custom"`, and every other field (`zoom`, `denoise`, `clahe_clip`, `clahe_tile`, `sharpen_amount`, `display`, `blue_gain`) matches `base`.
   - When `base` is a `Preset` (including one whose `base.name == "custom"`), verify `result is not base` (returns a NEW `Preset` instance).

2. **Custom `name` applied:**
   - Test `make_custom(base, name="reading_mode")` on `"cataract"`, `"amd"`, and a `Preset` base; verify `result.name == "reading_mode"` and all other 7 fields match `base`.

3. **Individual overrides applied while un-overridden fields stay copied:**
   - Parametrize / test each override independently on a `Preset` base (e.g. `zoom=1.0` boundary & `zoom=3.5`, `clahe_clip=0.5` & `4.5`, `sharpen_amount=0.0` falsy non-None boundary & `2.5`, `display` across `"plain"`, `"binary_dark"`, `"color_precomp"`).
   - Assert the overridden field equals the supplied value, `name == "custom"`, and every other field (including `denoise`, `clahe_tile`, `blue_gain`) remains equal to `base`.
   - Specifically verify `sharpen_amount=0.0` overrides a non-zero base `sharpen_amount` (guards against `if sharpen_amount:` truthiness bug instead of `is not None`).

4. **Combined overrides + custom `name`:**
   - Apply `zoom`, `clahe_clip`, `sharpen_amount`, `display`, and `name` together on a base with non-default `denoise="nlm"`, `clahe_tile=4`, `blue_gain=1.75`; verify all 5 overridden fields match the supplied values and `denoise`, `clahe_tile`, `blue_gain` copy from `base`.

5. **Keyword-only enforcement:**
   - Because section 2R specifies `make_custom(base, *, ...)`, verify passing a second positional argument such as `make_custom("cataract", 2.5)` raises `TypeError`.

6. **`str` base and `Preset` base produce equal results:**
   - For both `"cataract"` and `"amd"`, check `make_custom(name, ...) == make_custom(get_preset(name), ...)` both with default arguments and with combined overrides + custom `name`.

7. **Unknown `base` string raises `KeyError`:**
   - Parametrize over `["", "unknown", "CATARACT", "custom"]` and verify `make_custom(bad_name)` raises `KeyError`.

8. **Invalid override values raise `ValueError`:**
   - Parametrize `(override_kwargs)`:
     - `{"zoom": 0.99}`, `{"zoom": 0.0}`, `{"zoom": -1.0}`
     - `{"clahe_clip": 0.0}`, `{"clahe_clip": -1.0}`
     - `{"sharpen_amount": -0.01}`, `{"sharpen_amount": -2.0}`
     - `{"display": ""}`, `{"display": "inverted"}`
     - `{"name": ""}`
   - Test against both `"cataract"` and a custom `Preset` base, asserting `pytest.raises(ValueError)`.
   - **Do NOT test unspecified edge cases** not stated in `LANES.md` section 2R (do not test `name=None`, whitespace-only `name`, `NaN`/`Inf`, or wrong-type `base`).

9. **`base` and `PRESETS` unchanged and result not registered in `PRESETS`:**
   - Snapshot `PRESETS` (`{k: dataclasses.asdict(v) for k, v in PRESETS.items()}` and `set(PRESETS.keys())`) before calling `make_custom`.
   - Call `make_custom` with default `name="custom"`, with `name="slider_temp"`, and even with `name="cataract"` and altered `zoom`/`display` on both string bases and a `Preset` base.
   - Verify `PRESETS` keys and values match the pre-call snapshot identically, `"custom" not in PRESETS`, `"slider_temp" not in PRESETS`, `get_preset("custom")` raises `KeyError`, `make_custom("custom")` raises `KeyError`, and `dataclasses.asdict(base_preset)` is unchanged.

10. **Result usable by `enhance` (`shape` / `dtype`):**
    - Derive custom presets via `make_custom` from `"cataract"` and `"amd"` across `"plain"`, `"binary_dark"`, and `"color_precomp"` display modes (including `zoom=1.0`, `sharpen_amount=0.0`, and zoomed/sharpened settings).
    - Pass `synthetic_card_bgr` and each custom preset to `enhance(synthetic_card_bgr, custom)`.
    - Verify `isinstance(output, np.ndarray)`, `output.shape == synthetic_card_bgr.shape`, `output.dtype == np.uint8`, `output is not synthetic_card_bgr`, and `synthetic_card_bgr` is unmodified.

## 5. Hand-back Format

When finished, provide a concise report listing:
- Confirmation of the single file written (`tests/mode2/test_custom_preset.py`)
- All test functions created and what each covers
- Confirmation that no `src/` file was opened and no Python/pytest/interpreter was executed
- Any ambiguities noticed in `LANES.md` section 2R and how your tests interpreted them
