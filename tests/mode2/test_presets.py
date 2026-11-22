"""Contract tests for Mode 2 Preset dataclass and preset registry.

All assertions are derived strictly from LANES.md section 1:
- ``findsee.types.Preset`` (frozen dataclass, field domains, ValueError on invalid)
- ``findsee.mode2.presets.PRESETS`` (exact keys ``"cataract"`` and ``"amd"``)
- ``findsee.mode2.presets.get_preset`` (lookup and KeyError on unknown names)
"""

from __future__ import annotations

import dataclasses

import pytest

from findsee.mode2.presets import PRESETS, get_preset
from findsee.types import Preset

# Expected exact keys of the Mode 2 preset registry (LANES.md section 1).
_EXPECTED_PRESET_KEYS: set[str] = {"cataract", "amd"}

# Allowed values for Preset.denoise (LANES.md section 1).
_ALLOWED_DENOISE_MODES: tuple[str, ...] = ("none", "median", "bilateral", "nlm")

# Allowed values for Preset.display (LANES.md section 1).
_ALLOWED_DISPLAY_MODES: tuple[str, ...] = ("plain", "binary_dark", "color_precomp")


def _make_valid_preset() -> Preset:
    """Construct a valid Preset instance using keyword arguments only."""
    # Use display="color_precomp" so blue_gain validation is exercised in context.
    return Preset(
        name="contract_base",
        zoom=2.0,
        denoise="bilateral",
        clahe_clip=2.5,
        clahe_tile=8,
        sharpen_amount=1.0,
        display="color_precomp",
        blue_gain=1.2,
    )


def test_presets_registry_keys_and_field_domains() -> None:
    """PRESETS has exact keys 'cataract' and 'amd' with valid field domains."""
    # Registry must be a dict containing exactly the two contract keys.
    assert isinstance(PRESETS, dict)
    assert set(PRESETS.keys()) == _EXPECTED_PRESET_KEYS

    # Validate each registered preset against LANES.md section 1 domains.
    for key, preset in PRESETS.items():
        # Every registry value must be a Preset whose name matches its key.
        assert isinstance(preset, Preset)
        assert preset.name == key
        assert isinstance(preset.name, str) and len(preset.name) > 0

        # Check numeric and categorical domains without hardcoding draft values.
        assert preset.zoom >= 1.0
        assert preset.denoise in _ALLOWED_DENOISE_MODES
        assert preset.clahe_clip > 0.0
        assert isinstance(preset.clahe_tile, int) and preset.clahe_tile >= 1
        assert preset.sharpen_amount >= 0.0
        assert preset.display in _ALLOWED_DISPLAY_MODES
        assert preset.blue_gain >= 1.0


@pytest.mark.parametrize("preset_name", ["cataract", "amd"])
def test_get_preset_returns_matching_preset(preset_name: str) -> None:
    """get_preset returns the Preset equal to PRESETS[name] for valid names."""
    # Look up preset by name through the public helper.
    loaded: Preset = get_preset(preset_name)
    # Returned Preset must equal the registry entry and carry the matching name.
    assert isinstance(loaded, Preset)
    assert loaded == PRESETS[preset_name]
    assert loaded.name == preset_name


@pytest.mark.parametrize("unknown_name", ["", "unknown", "CATARACT"])
def test_get_preset_unknown_name_raises_key_error(unknown_name: str) -> None:
    """get_preset raises KeyError for unknown or wrong-case preset names."""
    # Any name not in PRESETS must raise KeyError.
    with pytest.raises(KeyError):
        get_preset(unknown_name)


def test_preset_is_frozen_dataclass_with_equality_and_hashing() -> None:
    """Preset is a frozen dataclass with default value equality and hashing."""
    # Verify Preset is a dataclass type.
    assert dataclasses.is_dataclass(Preset)

    # Construct two identical instances and one differing instance via kwargs.
    p1: Preset = _make_valid_preset()
    p2: Preset = _make_valid_preset()
    p3: Preset = dataclasses.replace(p1, zoom=3.0)

    # Default dataclass equality and hashing must agree for identical fields.
    assert p1 == p2
    assert hash(p1) == hash(p2)
    assert p1 != p3

    # Frozen dataclass instances must be usable as set elements and dict keys.
    preset_set: set[Preset] = {p1, p2, p3}
    assert len(preset_set) == 2
    preset_map: dict[Preset, str] = {p1: "first", p3: "third"}
    assert preset_map[p2] == "first"

    # Mutating any attribute on a frozen dataclass must raise FrozenInstanceError.
    with pytest.raises(dataclasses.FrozenInstanceError):
        p1.zoom = 1.5  # type: ignore[misc]


def test_preset_accepts_boundary_valid_values() -> None:
    """Preset accepts all contract lower bounds, denoisers, and display modes."""
    # Construct a Preset right on every allowed numeric lower boundary.
    boundary_preset: Preset = Preset(
        name="boundary",
        zoom=1.0,
        denoise="none",
        clahe_clip=0.1,
        clahe_tile=1,
        sharpen_amount=0.0,
        display="plain",
        blue_gain=1.0,
    )
    # Confirm every boundary field is stored as provided.
    assert boundary_preset.name == "boundary"
    assert boundary_preset.zoom == 1.0
    assert boundary_preset.denoise == "none"
    assert boundary_preset.clahe_clip == 0.1
    assert boundary_preset.clahe_tile == 1
    assert boundary_preset.sharpen_amount == 0.0
    assert boundary_preset.display == "plain"
    assert boundary_preset.blue_gain == 1.0

    # Verify every allowed denoise mode is accepted.
    for denoise_mode in _ALLOWED_DENOISE_MODES:
        variant: Preset = dataclasses.replace(boundary_preset, denoise=denoise_mode)
        assert variant.denoise == denoise_mode

    # Verify every allowed display mode is accepted.
    for display_mode in _ALLOWED_DISPLAY_MODES:
        variant = dataclasses.replace(boundary_preset, display=display_mode)
        assert variant.display == display_mode


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("name", ""),
        ("zoom", 0.99),
        ("zoom", 0.0),
        ("zoom", -1.0),
        ("denoise", "gaussian"),
        ("denoise", ""),
        ("clahe_clip", 0.0),
        ("clahe_clip", -1.0),
        ("clahe_tile", 0),
        ("clahe_tile", -2),
        ("sharpen_amount", -0.01),
        ("display", "inverted"),
        ("display", ""),
        ("blue_gain", 0.99),
        ("blue_gain", 0.0),
        ("blue_gain", -1.0),
    ],
)
def test_preset_invalid_field_raises_value_error(
    field_name: str,
    bad_value: object,
) -> None:
    """Each out-of-domain field value raises ValueError in Preset.__post_init__."""
    # Start from a valid base preset with display="color_precomp".
    base: Preset = _make_valid_preset()
    # Replacing a single field with an invalid value must raise ValueError.
    with pytest.raises(ValueError):
        dataclasses.replace(base, **{field_name: bad_value})
