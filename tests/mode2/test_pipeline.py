"""Contract tests for Mode 2 enhancement pipeline ``findsee.mode2.pipeline.enhance``.

All assertions are derived strictly from LANES.md section 1:
- Input validation (uint8 BGR ``(H, W, 3)`` with ``H, W >= 8``)
- Output shape, dtype, immutability of input, and byte-identical determinism
- Preset lookup by ``str`` or ``Preset`` object
- Display mode contracts (``plain``, ``binary_dark``, ``color_precomp``)
- ``zoom == 1.0``, all four ``denoise`` options, ``sharpen_amount == 0.0``
- Logging contract (no records above ``logging.DEBUG``)
"""

from __future__ import annotations

from collections.abc import Callable
import dataclasses
import logging

import numpy as np
import pytest

from findsee.mode2.pipeline import enhance
from findsee.mode2.presets import get_preset
from findsee.types import Preset

# Exact BGR pixel value for black background in binary_dark mode.
_BLACK_BGR: np.ndarray = np.array([0, 0, 0], dtype=np.uint8)

# Exact BGR pixel value for yellow foreground text in binary_dark mode.
_YELLOW_BGR: np.ndarray = np.array([0, 255, 255], dtype=np.uint8)


@pytest.mark.parametrize("preset_name", ["cataract", "amd"])
@pytest.mark.parametrize(
    ("height", "width"),
    [
        (240, 320),
        (65, 97),
        (121, 163),
        (8, 8),
    ],
)
def test_enhance_preserves_shape_and_dtype(
    make_card_bgr: Callable[..., np.ndarray],
    preset_name: str,
    height: int,
    width: int,
) -> None:
    """enhance preserves (H, W, 3) shape and uint8 dtype across sizes and presets."""
    # Generate a synthetic BGR uint8 card of the requested (H, W) size.
    image: np.ndarray = make_card_bgr(height, width, add_noise=True, seed=0)
    # Run the Mode 2 enhancement pipeline with the named preset.
    output: np.ndarray = enhance(image, preset_name)
    # Output must be a uint8 ndarray with identical (H, W, 3) shape.
    assert isinstance(output, np.ndarray)
    assert output.shape == (height, width, 3)
    assert output.dtype == np.uint8


@pytest.mark.parametrize(
    "preset",
    [
        "cataract",
        "amd",
        Preset(
            name="noop_like",
            zoom=1.0,
            denoise="none",
            clahe_clip=1.0,
            clahe_tile=8,
            sharpen_amount=0.0,
            display="plain",
            blue_gain=1.0,
        ),
    ],
)
def test_enhance_returns_new_array_without_mutating_input(
    synthetic_card_bgr: np.ndarray,
    preset: Preset | str,
) -> None:
    """enhance returns a fresh array that shares no memory with and never mutates input."""
    # Keep an independent copy of the input prior to enhancement.
    original: np.ndarray = synthetic_card_bgr.copy()
    # Execute enhance on the fixture image.
    output: np.ndarray = enhance(synthetic_card_bgr, preset)

    # Output must be a distinct array with no shared backing memory.
    assert output is not synthetic_card_bgr
    assert not np.shares_memory(output, synthetic_card_bgr)
    # Input array must be byte-for-byte unchanged after enhance returns.
    assert np.array_equal(synthetic_card_bgr, original)

    # Mutating the returned output array must not affect the input array.
    output[0, 0, 0] = np.uint8(int(output[0, 0, 0]) ^ 0xFF)
    assert np.array_equal(synthetic_card_bgr, original)


@pytest.mark.parametrize("preset_name", ["cataract", "amd"])
def test_enhance_is_deterministic_byte_identical(
    synthetic_card_bgr: np.ndarray,
    preset_name: str,
) -> None:
    """Repeated enhance calls with the same input and preset are byte-identical."""
    # Run enhance twice with identical inputs.
    out_first: np.ndarray = enhance(synthetic_card_bgr, preset_name)
    out_second: np.ndarray = enhance(synthetic_card_bgr, preset_name)
    # Both outputs must match elementwise and at the raw byte level.
    assert np.array_equal(out_first, out_second)
    assert out_first.tobytes() == out_second.tobytes()


@pytest.mark.parametrize("preset_name", ["cataract", "amd"])
def test_enhance_str_preset_matches_preset_object(
    synthetic_card_bgr: np.ndarray,
    preset_name: str,
) -> None:
    """Passing a preset name string gives byte-identical output to its Preset object."""
    # Run enhance with the preset name string and with the resolved Preset.
    out_by_name: np.ndarray = enhance(synthetic_card_bgr, preset_name)
    out_by_obj: np.ndarray = enhance(synthetic_card_bgr, get_preset(preset_name))
    # Both call paths must produce identical bytes.
    assert out_by_name.tobytes() == out_by_obj.tobytes()


@pytest.mark.parametrize("unknown_name", ["", "unknown", "AMD"])
def test_enhance_unknown_preset_name_raises_key_error(
    synthetic_card_bgr: np.ndarray,
    unknown_name: str,
) -> None:
    """enhance raises KeyError when given an unknown preset name string."""
    # Unknown preset strings are resolved via get_preset and must raise KeyError.
    with pytest.raises(KeyError):
        enhance(synthetic_card_bgr, unknown_name)


@pytest.mark.parametrize(
    ("shape", "dtype"),
    [
        # Wrong dtypes (must be uint8).
        ((240, 320, 3), np.float32),
        ((240, 320, 3), np.float64),
        ((240, 320, 3), np.uint16),
        # Wrong number of dimensions (must be 3-D).
        ((240, 320), np.uint8),
        ((1, 240, 320, 3), np.uint8),
        # Wrong channel count (must be 3 BGR channels).
        ((240, 320, 1), np.uint8),
        ((240, 320, 4), np.uint8),
        # Spatial dimensions smaller than 8x8.
        ((7, 8, 3), np.uint8),
        ((8, 7, 3), np.uint8),
        ((4, 4, 3), np.uint8),
        ((0, 0, 3), np.uint8),
    ],
)
def test_enhance_invalid_image_array_raises_value_error(
    shape: tuple[int, ...],
    dtype: np.dtype[np.generic] | type[np.generic],
) -> None:
    """Invalid image ndarray dtype, ndim, channel count, or size raises ValueError."""
    # Allocate an invalid test ndarray matching the parametrized spec.
    bad_image: np.ndarray = np.zeros(shape, dtype=dtype)
    # Pipeline input validation must reject it with ValueError.
    with pytest.raises(ValueError):
        enhance(bad_image, "cataract")


def test_binary_dark_outputs_only_black_and_yellow_pixels(
    synthetic_card_bgr: np.ndarray,
) -> None:
    """binary_dark mode outputs exclusively (0, 0, 0) or (0, 255, 255) BGR pixels."""
    # Force display="binary_dark" on a registered preset without assuming defaults.
    preset: Preset = dataclasses.replace(get_preset("amd"), display="binary_dark")
    # Enhance the noisy synthetic card.
    output: np.ndarray = enhance(synthetic_card_bgr, preset)
    # Flatten to (H*W, 3) to check every pixel's exact BGR triple.
    pixels: np.ndarray = output.reshape(-1, 3)
    # Boolean masks for exact black and exact yellow BGR pixels.
    is_black: np.ndarray = np.all(pixels == _BLACK_BGR, axis=1)
    is_yellow: np.ndarray = np.all(pixels == _YELLOW_BGR, axis=1)
    # Every pixel must be either black or yellow, with no intermediate values.
    assert np.all(is_black | is_yellow)


def test_binary_dark_polarity_maps_dark_text_to_yellow_on_black(
    clean_card_bgr: np.ndarray,
) -> None:
    """On a clean bright card with thin dark text, binary_dark yields < 50% yellow."""
    # Minimal binary_dark preset (no zoom, no denoise, no sharpen) for polarity check.
    preset: Preset = Preset(
        name="binary_polarity",
        zoom=1.0,
        denoise="none",
        clahe_clip=2.0,
        clahe_tile=8,
        sharpen_amount=0.0,
        display="binary_dark",
        blue_gain=1.0,
    )
    # Enhance the noise-free card where dark strokes occupy a small minority of pixels.
    output: np.ndarray = enhance(clean_card_bgr, preset)
    # Flatten to (H*W, 3) to inspect exact BGR colors and coverage fraction.
    pixels: np.ndarray = output.reshape(-1, 3)
    is_black: np.ndarray = np.all(pixels == _BLACK_BGR, axis=1)
    is_yellow: np.ndarray = np.all(pixels == _YELLOW_BGR, axis=1)

    # Every pixel must be strictly black or yellow, and both colors must appear.
    assert np.all(is_black | is_yellow)
    assert np.any(is_black)
    assert np.any(is_yellow)
    # Dark text becomes yellow on black background, so yellow fraction is < 0.5.
    yellow_fraction: float = float(np.mean(is_yellow))
    assert yellow_fraction < 0.5


def test_color_precomp_boosts_blue_and_preserves_green_and_red(
    synthetic_card_bgr: np.ndarray,
) -> None:
    """color_precomp scales channel 0 up (>= plain) and leaves channels 1 and 2 equal."""
    # Build plain and color_precomp presets differing only in display mode.
    base: Preset = get_preset("cataract")
    plain_preset: Preset = dataclasses.replace(base, display="plain", blue_gain=1.3)
    precomp_preset: Preset = dataclasses.replace(
        base,
        display="color_precomp",
        blue_gain=1.3,
    )

    # Run both display modes on the same synthetic card.
    out_plain: np.ndarray = enhance(synthetic_card_bgr, plain_preset)
    out_precomp: np.ndarray = enhance(synthetic_card_bgr, precomp_preset)

    # Channel 0 (blue) must be elementwise >= plain; channels 1 and 2 must be identical.
    assert np.all(out_precomp[..., 0] >= out_plain[..., 0])
    assert np.array_equal(out_precomp[..., 1], out_plain[..., 1])
    assert np.array_equal(out_precomp[..., 2], out_plain[..., 2])


def test_color_precomp_unit_blue_gain_equals_plain(
    synthetic_card_bgr: np.ndarray,
) -> None:
    """With blue_gain=1.0, color_precomp produces the exact same output as plain."""
    # Build plain and color_precomp presets with blue_gain=1.0.
    base: Preset = get_preset("cataract")
    plain_preset: Preset = dataclasses.replace(base, display="plain", blue_gain=1.0)
    precomp_preset: Preset = dataclasses.replace(
        base,
        display="color_precomp",
        blue_gain=1.0,
    )

    # Enhance with both presets and require exact elementwise equality.
    out_plain: np.ndarray = enhance(synthetic_card_bgr, plain_preset)
    out_precomp: np.ndarray = enhance(synthetic_card_bgr, precomp_preset)
    assert np.array_equal(out_precomp, out_plain)


def test_color_precomp_dyadic_blue_gain_matches_scaled_blue(
    synthetic_card_bgr: np.ndarray,
) -> None:
    """With dyadic blue_gain=1.5, blue channel stays within floor/ceil of raw * 1.5."""
    # Dyadic gain 1.5 is exact in both IEEE-754 float32 and float64 arithmetic.
    gain: float = 1.5
    base: Preset = get_preset("cataract")
    plain_preset: Preset = dataclasses.replace(base, display="plain", blue_gain=gain)
    precomp_preset: Preset = dataclasses.replace(
        base,
        display="color_precomp",
        blue_gain=gain,
    )

    # Compute plain and color_precomp outputs on the same synthetic card.
    out_plain: np.ndarray = enhance(synthetic_card_bgr, plain_preset)
    out_precomp: np.ndarray = enhance(synthetic_card_bgr, precomp_preset)

    # Compute rounding-mode-agnostic [floor, ceil] bounds clipped to [0, 255].
    raw_blue: np.ndarray = out_plain[..., 0].astype(np.float64) * gain
    lower_bound: np.ndarray = np.clip(np.floor(raw_blue), 0.0, 255.0).astype(np.uint8)
    upper_bound: np.ndarray = np.clip(np.ceil(raw_blue), 0.0, 255.0).astype(np.uint8)

    # Blue channel must lie within [lower_bound, upper_bound] at every pixel.
    assert np.all(out_precomp[..., 0] >= lower_bound)
    assert np.all(out_precomp[..., 0] <= upper_bound)
    # Green and red channels must remain identical to plain.
    assert np.array_equal(out_precomp[..., 1], out_plain[..., 1])
    assert np.array_equal(out_precomp[..., 2], out_plain[..., 2])


@pytest.mark.parametrize("display_mode", ["plain", "binary_dark", "color_precomp"])
def test_zoom_one_runs_across_all_display_modes(
    synthetic_card_bgr: np.ndarray,
    display_mode: str,
) -> None:
    """zoom=1.0 skips crop/upscale and preserves shape and dtype for all display modes."""
    # Build a zoom=1.0 preset for the parametrized display mode.
    preset: Preset = Preset(
        name=f"zoom1_{display_mode}",
        zoom=1.0,
        denoise="none",
        clahe_clip=2.0,
        clahe_tile=8,
        sharpen_amount=0.5,
        display=display_mode,
        blue_gain=1.2,
    )
    # Run enhance and verify shape and dtype are preserved.
    output: np.ndarray = enhance(synthetic_card_bgr, preset)
    assert output.shape == synthetic_card_bgr.shape
    assert output.dtype == np.uint8


def test_zoom_one_differs_from_zoom_two(synthetic_card_bgr: np.ndarray) -> None:
    """On a card with border marks and center text, zoom=1.0 differs from zoom=2.0."""
    # Compare zoom=1.0 against zoom=2.0 with all other preset parameters equal.
    preset_z1: Preset = Preset(
        name="zoom_one",
        zoom=1.0,
        denoise="none",
        clahe_clip=2.0,
        clahe_tile=8,
        sharpen_amount=0.0,
        display="plain",
        blue_gain=1.0,
    )
    preset_z2: Preset = dataclasses.replace(preset_z1, name="zoom_two", zoom=2.0)

    # Outputs must differ because zoom=2.0 crops out the outer border and scales center.
    out_z1: np.ndarray = enhance(synthetic_card_bgr, preset_z1)
    out_z2: np.ndarray = enhance(synthetic_card_bgr, preset_z2)
    assert not np.array_equal(out_z1, out_z2)


@pytest.mark.parametrize("denoise_mode", ["none", "median", "bilateral", "nlm"])
def test_all_denoise_options_run_and_preserve_shape_dtype(
    make_card_bgr: Callable[..., np.ndarray],
    denoise_mode: str,
) -> None:
    """Every contract denoise option runs cleanly and preserves shape and dtype."""
    # Use a compact 64x80 synthetic card so NLM and bilateral stay fast.
    small_card: np.ndarray = make_card_bgr(64, 80, add_noise=True, seed=0)
    # Build a preset exercising the parametrized denoiser.
    preset: Preset = Preset(
        name=f"denoise_{denoise_mode}",
        zoom=1.5,
        denoise=denoise_mode,
        clahe_clip=2.0,
        clahe_tile=8,
        sharpen_amount=0.5,
        display="plain",
        blue_gain=1.0,
    )
    # Run enhance and verify shape and dtype preservation.
    output: np.ndarray = enhance(small_card, preset)
    assert output.shape == (64, 80, 3)
    assert output.dtype == np.uint8


def test_sharpen_amount_zero_runs_and_preserves_shape_dtype(
    synthetic_card_bgr: np.ndarray,
) -> None:
    """sharpen_amount=0.0 disables unsharp masking cleanly and preserves shape/dtype."""
    # Build a preset with sharpen_amount=0.0 (unsharp mask off).
    preset: Preset = Preset(
        name="sharpen_off",
        zoom=2.0,
        denoise="median",
        clahe_clip=2.0,
        clahe_tile=8,
        sharpen_amount=0.0,
        display="plain",
        blue_gain=1.0,
    )
    # Run enhance and confirm output contract.
    output: np.ndarray = enhance(synthetic_card_bgr, preset)
    assert output.shape == synthetic_card_bgr.shape
    assert output.dtype == np.uint8


@pytest.mark.parametrize("preset_name", ["cataract", "amd"])
def test_enhance_emits_no_logging_above_debug(
    synthetic_card_bgr: np.ndarray,
    caplog: pytest.LogCaptureFixture,
    preset_name: str,
) -> None:
    """enhance must emit zero log records above logging.DEBUG."""
    # Capture all log records from DEBUG upwards during pipeline execution.
    with caplog.at_level(logging.DEBUG):
        enhance(synthetic_card_bgr, preset_name)
    # Filter for any log record strictly above DEBUG (INFO, WARNING, ERROR, CRITICAL).
    above_debug: list[logging.LogRecord] = [
        record for record in caplog.records if record.levelno > logging.DEBUG
    ]
    assert above_debug == []
