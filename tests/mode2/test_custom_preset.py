"""Contract tests for Mode 2 slider preset builder ``findsee.mode2.presets.make_custom``.

All assertions are derived strictly from LANES.md sections 1 and 2R:
- Signature: ``make_custom(base, *, zoom=None, clahe_clip=None, sharpen_amount=None,
  display=None, name="custom") -> Preset``
- Default ``name="custom"`` and copying of all un-overridden fields
- Individual and combined overrides (including falsy non-None ``sharpen_amount=0.0``)
- Keyword-only parameter enforcement after ``base``
- Equivalence between ``str`` and ``Preset`` bases
- ``KeyError`` on unknown preset name strings and ``ValueError`` on invalid overrides
- Immutability of ``base`` and ``PRESETS`` (custom result is never registered)
- Compatibility of returned ``Preset`` instances with ``findsee.mode2.pipeline.enhance``
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from findsee.mode2.pipeline import enhance
from findsee.mode2.presets import PRESETS, get_preset, make_custom
from findsee.types import Preset


def _make_custom_base(*, name: str = "custom_base") -> Preset:
    """Build a distinct non-default Preset for verifying field copy semantics.

    Args:
        name: Non-empty preset name string for the constructed base Preset.

    Returns:
        A valid frozen ``Preset`` with non-default ``denoise``, ``clahe_tile``,
        ``sharpen_amount``, and ``blue_gain`` so copy-through is distinguishable.
    """
    # Construct a valid Preset with distinct values on all un-overridable fields.
    return Preset(
        name=name,
        zoom=1.5,
        denoise="nlm",
        clahe_clip=2.5,
        clahe_tile=4,
        sharpen_amount=0.8,
        display="plain",
        blue_gain=1.75,
    )


def _resolve_base(base_spec: str | Preset) -> Preset:
    """Resolve a preset name string or Preset instance to its reference Preset.

    Args:
        base_spec: Either a registered preset name string or a ``Preset`` object.

    Returns:
        The ``Preset`` instance representing the expected un-overridden fields.
    """
    # Look up string keys through get_preset; pass Preset instances through directly.
    if isinstance(base_spec, str):
        return get_preset(base_spec)
    return base_spec


def _assert_non_name_fields_match(actual: Preset, expected: Preset) -> None:
    """Assert that all seven Preset fields other than ``name`` match exactly.

    Args:
        actual: The ``Preset`` returned by ``make_custom``.
        expected: The reference ``Preset`` providing expected field values.
    """
    # Compare every optical, filtering, and display field against the reference.
    assert actual.zoom == expected.zoom
    assert actual.denoise == expected.denoise
    assert actual.clahe_clip == expected.clahe_clip
    assert actual.clahe_tile == expected.clahe_tile
    assert actual.sharpen_amount == expected.sharpen_amount
    assert actual.display == expected.display
    assert actual.blue_gain == expected.blue_gain


@pytest.mark.parametrize(
    "base_spec",
    [
        "cataract",
        "amd",
        _make_custom_base(),
    ],
)
def test_make_custom_default_name_copies_all_other_fields(
    base_spec: str | Preset,
) -> None:
    """make_custom defaults name to 'custom' and copies all other fields from base."""
    # Resolve the reference Preset without hardcoding draft registry values.
    reference: Preset = _resolve_base(base_spec)
    # Call make_custom with no overrides so defaults apply.
    result: Preset = make_custom(base_spec)

    # Result must be a Preset instance carrying the default name "custom".
    assert isinstance(result, Preset)
    assert result.name == "custom"
    # Every field other than name must match the base Preset exactly.
    _assert_non_name_fields_match(result, reference)

    # When base is a Preset object, make_custom must return a NEW instance.
    if isinstance(base_spec, Preset):
        assert result is not base_spec


def test_make_custom_returns_new_instance_even_when_base_named_custom() -> None:
    """make_custom returns a NEW Preset instance even when base.name is 'custom'."""
    # Create a Preset whose name already equals the default "custom".
    base_named_custom: Preset = _make_custom_base(name="custom")
    # Invoke make_custom with no overrides; all field values will match base.
    result: Preset = make_custom(base_named_custom)

    # Result must be value-equal to base yet be a distinct Preset object.
    assert isinstance(result, Preset)
    assert result == base_named_custom
    assert result is not base_named_custom


@pytest.mark.parametrize(
    "base_spec",
    [
        "cataract",
        "amd",
        _make_custom_base(),
    ],
)
def test_make_custom_applies_custom_name_and_copies_other_fields(
    base_spec: str | Preset,
) -> None:
    """make_custom sets an explicit name while copying all seven other fields."""
    # Resolve the expected field values from the base specification.
    reference: Preset = _resolve_base(base_spec)
    # Explicit non-empty custom name for the derived preset.
    custom_name: str = "reading_mode"
    # Build the derived preset with only the name argument overridden.
    result: Preset = make_custom(base_spec, name=custom_name)

    # Confirm the returned Preset has the requested name and unchanged other fields.
    assert isinstance(result, Preset)
    assert result.name == custom_name
    _assert_non_name_fields_match(result, reference)


@pytest.mark.parametrize(
    ("field_name", "override_value"),
    [
        # Lower-boundary zoom (1.0) and magnified zoom (3.5).
        ("zoom", 1.0),
        ("zoom", 3.5),
        # Valid low and high CLAHE clip limits (> 0).
        ("clahe_clip", 0.5),
        ("clahe_clip", 4.5),
        # Lower-boundary falsy sharpen_amount (0.0) and strong sharpening (2.5).
        ("sharpen_amount", 0.0),
        ("sharpen_amount", 2.5),
        # All three contract display modes from LANES.md section 1.
        ("display", "plain"),
        ("display", "binary_dark"),
        ("display", "color_precomp"),
    ],
)
def test_make_custom_single_override_preserves_other_fields(
    field_name: str,
    override_value: float | str,
) -> None:
    """Each individual override updates only its own field plus default name."""
    # Use a custom base with non-zero sharpen_amount and distinct non-slider fields.
    base: Preset = _make_custom_base()
    # Pack the single keyword override under test.
    kwargs: dict[str, object] = {field_name: override_value}
    # Derive the new preset with only one slider parameter overridden.
    result: Preset = make_custom(base, **kwargs)  # type: ignore[arg-type]

    # Build the expected Preset by replacing name and the single overridden field.
    expected: Preset = dataclasses.replace(
        base,
        name="custom",
        **{field_name: override_value},  # type: ignore[arg-type]
    )
    # Returned Preset must match expected on all eight fields and be a new object.
    assert isinstance(result, Preset)
    assert result == expected
    assert getattr(result, field_name) == override_value
    assert result.name == "custom"
    # Explicitly confirm un-overridable fields stayed copied from base.
    assert result.denoise == base.denoise
    assert result.clahe_tile == base.clahe_tile
    assert result.blue_gain == base.blue_gain
    assert result is not base


def test_make_custom_sharpen_amount_zero_overrides_nonzero_base() -> None:
    """Passing sharpen_amount=0.0 overrides a positive base sharpen_amount."""
    # Start from a base with strictly positive sharpen_amount (0.8).
    base: Preset = _make_custom_base()
    assert base.sharpen_amount > 0.0

    # Override sharpen_amount with falsy float 0.0 to guard against truthiness checks.
    result: Preset = make_custom(base, sharpen_amount=0.0)

    # Resulting sharpen_amount must be 0.0 while every other field copies from base.
    assert result.sharpen_amount == 0.0
    assert result.name == "custom"
    assert result.zoom == base.zoom
    assert result.denoise == base.denoise
    assert result.clahe_clip == base.clahe_clip
    assert result.clahe_tile == base.clahe_tile
    assert result.display == base.display
    assert result.blue_gain == base.blue_gain


def test_make_custom_combined_overrides_and_custom_name() -> None:
    """Applying all slider overrides and name keeps denoise, clahe_tile, blue_gain."""
    # Base carries non-default denoise="nlm", clahe_tile=4, blue_gain=1.75.
    base: Preset = _make_custom_base()
    # Apply every allowed keyword argument simultaneously.
    result: Preset = make_custom(
        base,
        zoom=3.25,
        clahe_clip=4.0,
        sharpen_amount=1.75,
        display="color_precomp",
        name="elder_slider_1",
    )

    # All five overridden fields must reflect the supplied values.
    assert isinstance(result, Preset)
    assert result.name == "elder_slider_1"
    assert result.zoom == 3.25
    assert result.clahe_clip == 4.0
    assert result.sharpen_amount == 1.75
    assert result.display == "color_precomp"
    # All three non-slider fields must remain copied verbatim from base.
    assert result.denoise == "nlm"
    assert result.clahe_tile == 4
    assert result.blue_gain == 1.75
    assert result is not base


@pytest.mark.parametrize(
    "base_spec",
    [
        "cataract",
        _make_custom_base(),
    ],
)
def test_make_custom_enforces_keyword_only_overrides(
    base_spec: str | Preset,
) -> None:
    """Passing override arguments positionally after base raises TypeError."""
    # LANES.md section 2R specifies make_custom(base, *, zoom=None, ...).
    with pytest.raises(TypeError):
        make_custom(base_spec, 2.5)  # type: ignore[misc]


@pytest.mark.parametrize("preset_name", ["cataract", "amd"])
def test_make_custom_str_base_equals_preset_base(preset_name: str) -> None:
    """String base and resolved Preset base produce equal results."""
    # Resolve the named preset once via the public registry helper.
    base_obj: Preset = get_preset(preset_name)

    # Compare default-argument calls with string base vs Preset base.
    default_from_str: Preset = make_custom(preset_name)
    default_from_obj: Preset = make_custom(base_obj)
    assert default_from_str == default_from_obj

    # Compare combined-override calls with string base vs Preset base.
    custom_from_str: Preset = make_custom(
        preset_name,
        zoom=2.25,
        clahe_clip=3.5,
        sharpen_amount=0.5,
        display="plain",
        name="matched_custom",
    )
    custom_from_obj: Preset = make_custom(
        base_obj,
        zoom=2.25,
        clahe_clip=3.5,
        sharpen_amount=0.5,
        display="plain",
        name="matched_custom",
    )
    assert custom_from_str == custom_from_obj


@pytest.mark.parametrize("bad_name", ["", "unknown", "CATARACT", "custom"])
def test_make_custom_unknown_base_string_raises_key_error(bad_name: str) -> None:
    """Passing an unregistered base preset name string raises KeyError."""
    # Unknown names must fail through preset lookup with KeyError.
    with pytest.raises(KeyError):
        make_custom(bad_name)


@pytest.mark.parametrize(
    "base_spec",
    [
        "cataract",
        _make_custom_base(),
    ],
)
@pytest.mark.parametrize(
    "override_kwargs",
    [
        # Invalid zoom values (contract requires zoom >= 1.0).
        {"zoom": 0.99},
        {"zoom": 0.0},
        {"zoom": -1.0},
        # Invalid clahe_clip values (contract requires clahe_clip > 0).
        {"clahe_clip": 0.0},
        {"clahe_clip": -1.0},
        # Invalid sharpen_amount values (contract requires sharpen_amount >= 0).
        {"sharpen_amount": -0.01},
        {"sharpen_amount": -2.0},
        # Invalid display modes (must be plain, binary_dark, or color_precomp).
        {"display": ""},
        {"display": "inverted"},
        # Invalid empty name (contract requires non-empty name string).
        {"name": ""},
    ],
)
def test_make_custom_invalid_override_raises_value_error(
    base_spec: str | Preset,
    override_kwargs: dict[str, object],
) -> None:
    """Out-of-domain override values raise ValueError via Preset validation."""
    # Every invalid field value must be rejected with ValueError.
    with pytest.raises(ValueError):
        make_custom(base_spec, **override_kwargs)  # type: ignore[arg-type]


def test_make_custom_leaves_base_and_presets_unchanged_and_unregistered() -> None:
    """make_custom never mutates base or PRESETS and never registers its result."""
    # Snapshot PRESETS keys and every entry's field dictionary before any call.
    initial_keys: set[str] = set(PRESETS.keys())
    initial_entries: dict[str, dict[str, object]] = {
        key: dataclasses.asdict(value) for key, value in PRESETS.items()
    }
    # Create a custom Preset base and snapshot its fields before calling make_custom.
    base_preset: Preset = _make_custom_base()
    initial_base_dict: dict[str, object] = dataclasses.asdict(base_preset)

    # Call make_custom with default name, a temp name, and a colliding registry name.
    custom_default: Preset = make_custom("cataract", zoom=2.5)
    custom_temp: Preset = make_custom("amd", clahe_clip=3.5, name="slider_temp")
    custom_colliding_str: Preset = make_custom(
        "cataract",
        zoom=4.0,
        display="binary_dark",
        name="cataract",
    )
    custom_from_preset: Preset = make_custom(
        base_preset,
        zoom=2.75,
        display="color_precomp",
        name="cataract",
    )

    # Confirm the returned presets carry the requested names.
    assert custom_default.name == "custom"
    assert custom_temp.name == "slider_temp"
    assert custom_colliding_str.name == "cataract"
    assert custom_from_preset.name == "cataract"

    # PRESETS keys and all stored Preset field values must match the snapshot exactly.
    assert set(PRESETS.keys()) == initial_keys
    assert {key: dataclasses.asdict(value) for key, value in PRESETS.items()} == (
        initial_entries
    )
    # Neither default nor temporary custom names may be registered in PRESETS.
    assert "custom" not in PRESETS
    assert "slider_temp" not in PRESETS

    # Looking up or basing on unregistered "custom" must still raise KeyError.
    with pytest.raises(KeyError):
        get_preset("custom")
    with pytest.raises(KeyError):
        make_custom("custom")

    # The caller's Preset base object must remain completely unchanged.
    assert dataclasses.asdict(base_preset) == initial_base_dict


@pytest.mark.parametrize("base_name", ["cataract", "amd"])
@pytest.mark.parametrize(
    ("zoom", "sharpen_amount", "display"),
    [
        # No-zoom, no-sharpen plain mode.
        (1.0, 0.0, "plain"),
        # Zoomed and sharpened binary_dark mode.
        (2.5, 1.2, "binary_dark"),
        # Zoomed and sharpened color_precomp mode.
        (2.0, 0.75, "color_precomp"),
    ],
)
def test_make_custom_result_is_usable_by_enhance(
    synthetic_card_bgr: np.ndarray,
    base_name: str,
    zoom: float,
    sharpen_amount: float,
    display: str,
) -> None:
    """Presets built by make_custom run through enhance preserving shape and dtype."""
    # Keep a byte-exact copy of the input card to verify non-mutation.
    original: np.ndarray = synthetic_card_bgr.copy()
    # Build a slider-derived Preset from the parametrized base and display mode.
    custom_preset: Preset = make_custom(
        base_name,
        zoom=zoom,
        sharpen_amount=sharpen_amount,
        display=display,
        name=f"{base_name}_{display}_slider",
    )

    # Run the Mode 2 enhancement pipeline with the custom Preset.
    output: np.ndarray = enhance(synthetic_card_bgr, custom_preset)

    # Output must be a fresh uint8 ndarray matching the input (H, W, 3) shape.
    assert isinstance(output, np.ndarray)
    assert output.shape == synthetic_card_bgr.shape
    assert output.dtype == np.uint8
    assert output is not synthetic_card_bgr
    # Input synthetic card must remain completely unmodified.
    assert np.array_equal(synthetic_card_bgr, original)
