# Stage Brief S1: Mode 2 Contract Tests (Lane C2)

- **Session:** `C-20261122T1606Z-gemini-1384` (Gemini MAIN, Part C, Lane C2)
- **Stage bound:** Write ONLY `tests/mode2/conftest.py`, `tests/mode2/test_presets.py`, and `tests/mode2/test_pipeline.py`. Do NOT execute Python or pytest. Stop and hand back once all three files are written and self-checked.

## Settled facts (cited)

1. **Frozen interface (`work/claude-main/C-20261122T1606Z-claude-0984/LANES.md` section 1):**
   - `findsee.types.Preset`: frozen dataclass with fields:
     - `name: str` (non-empty)
     - `zoom: float` (`>= 1.0`, centre crop of `1/zoom` of each side, then bicubic upscale back to input size)
     - `denoise: str` (`"none"`, `"median"`, `"bilateral"`, `"nlm"`, denoiser applied after the crop)
     - `clahe_clip: float` (`> 0`, CLAHE clip limit on the Lab L channel)
     - `clahe_tile: int` (`>= 1`, CLAHE tile grid size `tile x tile`)
     - `sharpen_amount: float` (`>= 0`, unsharp-mask amount, `0` = off)
     - `display: str` (`"plain"`, `"binary_dark"`, `"color_precomp"`)
     - `blue_gain: float` (`>= 1.0`, blue-channel gain, used only by `color_precomp`)
     - Invalid values raise `ValueError` in `__post_init__`. Equality and hashing are the dataclass defaults.
   - `findsee.mode2.presets`:
     - `PRESETS: dict[str, Preset]` with exact keys `"cataract"` and `"amd"`; each value's `name` equals its key.
     - `get_preset(name: str) -> Preset`; unknown name raises `KeyError`.
     - Draft values listed in `LANES.md` are marked "Draft values (not evaluated; tuning is a later stage)" and must NOT be hardcoded in tests.
   - `findsee.mode2.pipeline.enhance(image, preset) -> np.ndarray`:
     - `image`: `np.ndarray`, BGR, `dtype uint8`, shape `(H, W, 3)`, `H, W >= 8`. Anything else raises `ValueError` (wrong dtype, wrong ndim, channel count != 3, too small).
     - `preset`: a `Preset` or a preset name `str` (looked up with `get_preset`, so an unknown name raises `KeyError`).
     - Returns a **new** array, `uint8`, shape equal to input shape. Input is never modified. Deterministic (same input + preset -> byte-identical output). No I/O, no logging above `DEBUG`.
     - Order: `crop (zoom) -> denoise -> CLAHE on Lab L -> bicubic upscale to input size -> unsharp mask -> display`.
     - `zoom == 1.0` skips the crop and the upscale.
     - Display modes:
       - `plain`: BGR result of the steps above.
       - `binary_dark`: grayscale -> adaptive threshold -> dark text becomes yellow `(0, 255, 255)` on black `(0, 0, 0)`; every output pixel is exactly one of those two colours.
       - `color_precomp`: `plain` result with channel 0 (blue) multiplied by `blue_gain`, rounded and clipped to 255; channels 1 and 2 are identical to `plain`. For same input and preset differing only in `display`, `out_precomp[..., 0] >= out_plain[..., 0]` elementwise.
2. **Import paths (`LANES.md` section 2 & user prompt):** `pyproject.toml` (written by Lane C1) configures `pythonpath = ["src"]` for pytest. Import `findsee.*` directly with NO `sys.path` hacks.
3. **Environment (`LANES.md` section 0):** No conda `findsee` or `.venv` exists on this machine. Do NOT run Python or pytest, and do NOT substitute another interpreter (`CLAUDE.md` rule 1.3).
4. **Target libraries (`LANES.md` section 0):** `numpy`, `cv2` (`opencv-python`), `pytest`, Python stdlib (`dataclasses`, `logging`), and `findsee.*`. Nothing else.

## Numbered steps

1. **Read required context (do NOT read `src/` or `pyproject.toml`):**
   - `AGENTS.md`, `CLAUDE.md`, `work/claude-main/C-20261122T1606Z-claude-0984/LANES.md`, `tests/README.md`.
2. **Write `tests/mode2/conftest.py`:**
   - Implement a pure in-memory synthetic BGR `uint8` card generator `_make_synthetic_card(height: int = 240, width: int = 320, *, add_noise: bool = True, seed: int = 0) -> np.ndarray`:
     - Light BGR card background `(235, 235, 235)` of shape `(height, width, 3)` and dtype `np.uint8`.
     - Dark outer border / corner registration marks (`(20, 20, 20)`) scaled safely so even `(8, 8, 3)` succeeds without out-of-bounds indexing or `cv2` errors, ensuring `zoom=1.0` vs `zoom=2.0` produce distinct outputs due to edge vs center content.
     - Dark high-contrast ASCII text `(20, 20, 20)` drawn with `cv2.putText` centered in the middle region (stays inside 2x-3x center crop on `240x320` and larger odd sizes; guarded gracefully when image is very small such as `8x8` so tiny canvases still contain non-uniform dark foreground marks in the center without error).
     - When `add_noise=True`, add seeded zero-mean Gaussian noise using `np.random.default_rng(seed)` (e.g., `sigma=4.0`), round, and clip to `[0, 255]` as `np.uint8`.
     - Zero disk I/O, zero image files, zero photos of people.
   - Expose pytest fixtures:
     - `synthetic_card_bgr() -> np.ndarray`: fresh 240x320 BGR `uint8` card with dark text and seeded noise (`seed=0`).
     - `clean_card_bgr() -> np.ndarray`: fresh 240x320 BGR `uint8` card with dark text and `add_noise=False` (for unambiguous `binary_dark` foreground/background polarity test).
     - `make_card_bgr`: fixture returning the callable factory `(height: int, width: int, *, add_noise: bool = True, seed: int = 0) -> np.ndarray` for odd sizes (e.g. `65x97`, `121x163`) and minimum size (`8x8`).
3. **Write `tests/mode2/test_presets.py`:**
   - Verify `isinstance(PRESETS, dict)` and `set(PRESETS.keys()) == {"cataract", "amd"}`.
   - For every `key, preset in PRESETS.items()`: verify `isinstance(preset, Preset)`, `preset.name == key`, and every field satisfies `LANES.md` section 1 allowed domains (`bool(preset.name)`, `preset.zoom >= 1.0`, `preset.denoise in {"none", "median", "bilateral", "nlm"}`, `preset.clahe_clip > 0`, `preset.clahe_tile >= 1`, `preset.sharpen_amount >= 0`, `preset.display in {"plain", "binary_dark", "color_precomp"}`, `preset.blue_gain >= 1.0`). Do NOT assert draft numeric values (`zoom == 2.0`, etc.).
   - Verify `get_preset("cataract") == PRESETS["cataract"]` and `get_preset("amd") == PRESETS["amd"]`.
   - Verify unknown preset names (`""`, `"unknown"`, `"CATARACT"`) raise `KeyError`.
   - Verify `Preset` is a frozen dataclass (`dataclasses.is_dataclass(Preset)`, mutating a field raises `dataclasses.FrozenInstanceError`), and check default equality & hashing (`p1 == p2`, `hash(p1) == hash(p2)`, usable in `set`/`dict`, unequal instances differ).
   - Verify boundary valid values succeed using keyword arguments (never assuming positional field order): `zoom=1.0`, `clahe_clip=0.1`, `clahe_tile=1`, `sharpen_amount=0.0`, `blue_gain=1.0`, all 4 `denoise` options, all 3 `display` options.
   - Verify each invalid field value raises `ValueError` in `__post_init__` using `dataclasses.replace` on a valid base preset (with `display="color_precomp"`):
     - `name=""`
     - `zoom=0.99`, `zoom=0.0`, `zoom=-1.0`
     - `denoise="gaussian"`, `denoise=""`
     - `clahe_clip=0.0`, `clahe_clip=-1.0`
     - `clahe_tile=0`, `clahe_tile=-2`
     - `sharpen_amount=-0.01`
     - `display="inverted"`, `display=""`
     - `blue_gain=0.99`, `blue_gain=0.0`, `blue_gain=-1.0`
   - Do NOT test whitespace-only `name`, `NaN`/`inf`, or `bool` (unspecified in `LANES.md` section 1).
4. **Write `tests/mode2/test_pipeline.py`:**
   - Shape `(H, W, 3)` and `np.uint8` dtype preserved for both `"cataract"` and `"amd"` across standard `(240, 320, 3)`, odd sizes `(65, 97, 3)` and `(121, 163, 3)`, and minimum size `(8, 8, 3)`.
   - Input not mutated and returns a new array (`out is not img`, `not np.shares_memory(out, img)`, pre-call copy `np.array_equal(img, original)`, mutating `out` does not alter `img`) for `"cataract"`, `"amd"`, and a minimal no-op-like preset (`zoom=1.0`, `denoise="none"`, `sharpen_amount=0.0`, `display="plain"`).
   - Byte-identical determinism: two calls with identical input and preset satisfy `np.array_equal(out1, out2)` and `out1.tobytes() == out2.tobytes()`.
   - `str` preset == `Preset` object: for `"cataract"` and `"amd"`, `enhance(img, name).tobytes() == enhance(img, get_preset(name)).tobytes()`.
   - Unknown preset name string raises `KeyError`.
   - Invalid `np.ndarray` inputs raise `ValueError`: float dtypes (`np.float32`, `np.float64`), non-uint8 integer (`np.uint16`), 2-D gray `(240, 320)`, 4-D batch `(1, 240, 320, 3)`, 1-channel `(240, 320, 1)`, 4-channel BGRA `(240, 320, 4)`, smaller than 8x8 (`(7, 8, 3)`, `(8, 7, 3)`, `(4, 4, 3)`, `(0, 0, 3)`). Do NOT assert `ValueError` for non-`ndarray` `image` or non-`Preset`/`str` `preset`.
   - `binary_dark` display mode:
     - On `synthetic_card_bgr` with `dataclasses.replace(get_preset("amd"), display="binary_dark")`: every pixel in `out.reshape(-1, 3)` equals `(0, 0, 0)` or `(0, 255, 255)`.
     - On `clean_card_bgr` with `zoom=1.0`, `denoise="none"`, `sharpen_amount=0.0`, `display="binary_dark"`: every pixel is `(0, 0, 0)` or `(0, 255, 255)`, both colors appear, and yellow pixel fraction `< 0.5` (verifying dark text becomes yellow on black without assuming adaptive threshold block size / C).
   - `color_precomp` vs `plain` relation via `dataclasses.replace`:
     - `plain_p = dataclasses.replace(base, display="plain", blue_gain=1.3)` vs `precomp_p = dataclasses.replace(base, display="color_precomp", blue_gain=1.3)`: `np.all(out_precomp[..., 0] >= out_plain[..., 0])`, `np.array_equal(out_precomp[..., 1], out_plain[..., 1])`, `np.array_equal(out_precomp[..., 2], out_plain[..., 2])`.
     - With `blue_gain=1.0`: `np.array_equal(out_precomp_1, out_plain)`.
     - With dyadic `blue_gain=1.5` (exact in IEEE-754 float32/float64): verify `out_precomp[..., 0]` is elementwise within `[np.clip(np.floor(raw), 0, 255), np.clip(np.ceil(raw), 0, 255)]` where `raw = out_plain[..., 0].astype(np.float64) * 1.5` (rounding-mode agnostic, catches ignored `blue_gain`).
   - `zoom == 1.0`: runs across all 3 display modes preserving shape/dtype; on `synthetic_card_bgr` (border marks + center text), `zoom=1.0` differs from `zoom=2.0`.
   - Every `denoise` option (`"none"`, `"median"`, `"bilateral"`, `"nlm"`) runs cleanly and preserves shape/dtype (on `(64, 80, 3)` card).
   - `sharpen_amount == 0.0` runs cleanly and preserves shape/dtype.
   - Logging contract: with pytest `caplog` at `logging.INFO`, calling `enhance(img, preset)` emits zero log records above `DEBUG`.
5. **Self-check before hand-back:**
   - Read every line of all three written files and verify:
     - Zero assertions beyond `LANES.md` section 1.
     - No `sys.path` hacks.
     - Valid Python 3.11+ syntax, valid `cv2` and `numpy` API usage (`cv2.putText`, `cv2.rectangle`, `np.random.default_rng`, `np.clip`, etc.).
     - `CLAUDE.md` rule 1.4 comment discipline: module docstring, docstrings on every fixture/function/helper, detailed comments on every code block, line, and variable, ASCII-only everywhere.

## Must-nots

- Do NOT read or write `src/**`, `pyproject.toml`, `eval/**`, `PROGRESS.md`, `work/BACKLOG.md`, `docs/**`, `work/WORKBOARD.md`, `LANES.md`, `change_log/**`, `data/**`, or any harness files.
- Do NOT run Python, pytest, or any interpreter.
- Do NOT run mutating git commands (`commit`, `push`, `checkout`, `switch`, `stash`, `reset`, etc.).
- Do NOT install or download anything, read `.env` files, or launch sub-agents.
- Do NOT create outside artifacts or leave scratch files behind.

## Hand-back format

Return a concise summary listing:
1. Files created and one-line purpose of each.
2. Checklist of every contract test group included against `LANES.md` section 1.
3. Confirmation of "not run: no project environment", no `src/` reads, and comment-discipline self-check.
4. Any contract edge cases or ambiguities noticed while writing the tests.
