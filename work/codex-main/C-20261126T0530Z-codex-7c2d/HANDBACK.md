# Lane C3 hand-back

Codex MAIN `C-20261126T0530Z-codex-7c2d` to Gemini MAIN `C-20261126T0530Z-gemini-4f8a` on `part-c/dual-orch-test`.

## Outcome

Added both provenance-tagged `Unspecified (do not assert)` subsections to the Claude trial's frozen Part C contract. Removing the insertions recovers the original bytes.

## Files written

- `work/claude-main/C-20261122T1606Z-claude-0984/LANES.md` (two insertions).
- `work/codex-main/C-20261126T0530Z-codex-7c2d/SESSION.md` and this `HANDBACK.md`.
- `work/codex-main/C-20261126T0530Z-codex-7c2d/subagents/` contains the R1 and R2 briefs and their two reports.
- `work/WORKBOARD.md` (last cell of the C3 row, with the lead to release the claim at integration).

## Runners

Both delegates used `codex` / `gpt-6.2-sol`, `reasoningEffort: medium`, `runtimeMode: full-access`, `isolation: shared`. Each wrote its assigned report.

- R1 task ID `node:delegated-task:command%3Amcp%3A84d49da9-55de-4fff-8b1c-aa624433b907%3Adelegate-task%3AC-20261126T0530Z-codex-7c2d-R1`. Audited Section 1 and Gemini 1384 against the pipeline, presets, types, and tests. MAIN verified the invalid-image exception, blue bound, and DEBUG ceiling, scoped CLAHE to undersized-crop accommodation, added unsupported `get_preset` argument exceptions, and identified the documented values as this round's starting drafts. [R1 report](subagents/R1_sec1_report.md)
- R2 task ID `node:delegated-task:command%3Amcp%3A84d49da9-55de-4fff-8b1c-aa624433b907%3Adelegate-task%3AC-20261126T0530Z-codex-7c2d-R2`. Audited Section 2R and Gemini 1777 against preset and live helpers and tests. MAIN independently verified the supplied-name validation, camera index wording and release count, and narrowed the window type exception to cases beyond the `< 2` rule. The overlay bullet limits color choices to foreground and pixel-effect uncertainty to spaces. [R2 report](subagents/R2_sec2r_report.md)

## Section 1 additions

- `Preset` positional order, whitespace-only names, finiteness beyond the stated bounds, and handling of `bool` and NumPy scalar inputs at the domain boundaries.
- Exception types for `enhance` presets outside `Preset`/`str` and `get_preset` arguments outside `str`, validation precedence, and diagnostic wording.
- Future tuned preset values, with the historical starting drafts identified explicitly.
- Crop rounding, minimum internal crop size at high zoom, and allocation of odd leftover margins.
- Denoiser kernels and filter parameters, undersized-crop CLAHE grid adjustment, and unsharp blur parameters.
- Adaptive threshold weighting, `blockSize`, `C`, and small-canvas adjustment.
- Blue-gain intermediate precision and rounding tie-break.
- DEBUG record presence, count, and wording.

### Section 1 exclusions

- Non-array `image` still raises `ValueError` under the explicit "Anything else" clause. `ValueError` also remains required for invalid arrays and invalid preset fields. The `int` tile field and numeric inequalities still apply. `NaN` fails the bounds and negative infinity is below them. The open finiteness check concerns values such as positive infinity that meet the inequalities alone.
- `blue_gain < 1.0` is invalid for every display mode under the allowed-values column. The meaning column limits application of gain to `color_precomp`. Registry keys, names, and `KeyError` on unknown string names are specified or asserted. The enumerated drafts are documented for this round. Lookup object identity was audited and omitted from the concise list because the hand-backs and change logs raise no identity question.
- The input size floor, center crop and bicubic resize, zoom-1 skip, stage order, Lab L CLAHE, zero-sharpen behavior, output invariants, binary palette and polarity, and blue channel scaling and clipping remain specified. Tests additionally cover unit-gain identity, 1.5 gain floor/ceil bounds, blue non-decrease, and exact G/R preservation. The DEBUG ceiling and no-I/O rule are explicit.

## Section 2R additions

- Wrong-base exception type and inherited whitespace/numeric edge policies for `make_custom`.
- Out-of-domain `FpsMeter` window type handling beyond `< 2`, boolean check precedence, incompatible clock behavior, and internal tick storage.
- Exact overlay geometry, padding, clipping, glyph placement, font, scale, thickness, antialiasing, foreground color, space-only pixel effects, and diagnostic precedence with two invalid arguments.
- Camera ordering of `isOpened()` and `set()` and of width versus height operations, negative index and non-positive size handling, and fractional readback conversion. Exact exception wording is open subject to inclusion of the camera index.
- Live window title, key polling mechanics, raw label, FPS format and placeholder, printable-ASCII sanitization, `Preset` object support and unsupported-preset validation, exact log wording and extra events, read failure, window close, and cleanup mechanics.

### Section 2R exclusions

- `make_custom` requires keyword-only overrides (`test_custom_preset.py:251`) and a fresh result even when an unchanged base is named `custom` (`test_custom_preset.py:110`). `name=None` is subject to the explicit name assignment and Section 1's non-empty string validation. The four named slider overrides have the `None` sentinel. Known and unknown base names, valid overrides, validation, and registry/base integrity are specified or asserted.
- `FpsMeter` keeps the `< 2` `ValueError` rule, window defaults and retention, timestamp formula, no `clock()` reads from `fps()`, and `None` for zero or negative spans (`test_live.py:219`, `test_live.py:229`, `test_live.py:355`). Python booleans compare below 2, so their exact rejection class is preserved under that reading.
- `draw_status` requires `ValueError` for a wrong Python type for `frame` or `text` by the shared image contract and explicit printable-ASCII string requirement. Invalid frames still fail with empty text (`test_live.py:586`). Top-left placement, the filled black box, visible glyphs for the tested strings, shape/type/copy behavior, space acceptance, and unchanged pixels for empty text stay covered (`test_live.py:430`, `test_live.py:448`, `test_live.py:495`).
- `open_camera` still requests both properties before effective readback, returns effective Python integer dimensions in width/height order, and opens one camera. Failure still releases it exactly once, raises `RuntimeError` with the index, and tries no fallback (`test_live.py:705`).
- `run_live` still requires the default arguments, key actions, preset-name and FPS overlay, memory-only frames, and requested and effective sizes at INFO. The absence of a hardware test does not change those clauses.

## Verification and discrepancies

- A targeted `git diff` showed two additions-only hunks in `LANES.md`, 33 inserted lines and zero deletions. `git diff --check` passed for that file. The original UTF-8 bytes, including LF endings, were recovered by removing the insertions and checking the original SHA-256. The workboard cell edit used its existing UTF-8 bytes and CRLF endings. No C3 scratch folder was created.
- `git status --short --untracked-files=all` showed the C3 contract, workboard, and the six expected C3 session files. The other paths were the lead's environment document, requirements file, change log, and two Gemini session files, already in the lead's write set. Byte comparison verified that the workboard edit affects only the last C3 cell. Git emitted its usual workboard CRLF normalization warning during the read-only diff.
- Contract and code review covered `types.py`, `presets.py`, `pipeline.py`, and `live.py`, all four named test files, both C1 logs, and both historical Gemini hand-backs. No Python, pytest, camera, or benchmark ran in C3. The lead owns test integration in conda `findsee`.
- The CLAHE helper note describes a square clamp to `min(tile, h, w)`. The code clamps the width and height independently and can choose a rectangular effective grid on undersized crops. The insertion preserves the historical requested grid and records the undersized-crop accommodation as open, consistent with the C1 log. [Pipeline source](../../../src/findsee/mode2/pipeline.py#L198)
- The `Preset` helper comment overgeneralizes NumPy float subclassing. Its actual `isinstance` check and the C1 log distinguish `np.float32`, which is rejected. The insertion keeps scalar subtype policy open. [Type source](../../../src/findsee/types.py#L38)
- R1 found two numerical risks by inspection. Extreme finite blue gains such as `1e40` can overflow during float32 conversion, and enormous Python integer inputs may overflow `math.isfinite`. These were not reproduced. The backfill preserves the blue-output and invalid-field guarantees and leaves the existing source in the lead's scope. [R1 evidence](subagents/R1_sec1_report.md#discrepancies-and-lead-decisions)

## Parallel orchestration observations

T3 reported this Codex MAIN as `gpt-6.2-sol` with `reasoningEffort: high` in `full-access`. Both `medium` delegates were accepted and started before either completed. R2 delivered first while MAIN was auditing both sections. Report paths were disjoint and the shared writes showed no overlap with the Gemini lead. Completion notifications arrived asynchronously with no approval prompt or task polling. This documentation-only run provides no runtime performance comparison between models or reasoning settings.
