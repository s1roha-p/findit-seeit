"""Shared dataclasses of FindSee (``docs/project/ARCHITECTURE.md``, "Shared types").

This module currently holds only Part C's ``Preset`` (frozen interface:
``work/claude-main/C-20261122T1606Z-claude-0984/LANES.md`` section 1). The other shared types listed in
``ARCHITECTURE.md`` (``Snapshot``, ``Detection``, ``Sighting``, ...) are added here by the parts that own them;
they are deliberately not written by Part C.

The module depends only on the standard library so every part can import it cheaply.
"""

from __future__ import annotations

import math  # math.isfinite: rejects NaN / inf in float fields
from dataclasses import dataclass  # frozen dataclass -> immutable, hashable preset values

# Allowed values of ``Preset.denoise``, in no particular order of preference:
# "none" = skip denoising, "median" = 3x3 median blur, "bilateral" = edge-preserving bilateral filter,
# "nlm" = OpenCV fast non-local means (colour). Tuple (immutable) so callers cannot mutate the allowed set.
DENOISE_METHODS: tuple[str, ...] = ("none", "median", "bilateral", "nlm")

# Allowed values of ``Preset.display``:
# "plain" = the enhanced BGR image, "binary_dark" = adaptive-threshold yellow (0, 255, 255) on black (0, 0, 0),
# "color_precomp" = the plain image with the blue channel multiplied by ``blue_gain``. Tuple for immutability.
DISPLAY_MODES: tuple[str, ...] = ("plain", "binary_dark", "color_precomp")


def _is_real_number(value: object) -> bool:
    """Return True when ``value`` is a finite int or float (``bool`` excluded).

    Args:
        value: any object taken from a ``Preset`` field.

    Returns:
        True for finite ``int`` / ``float`` values; False for ``bool`` (a subclass of int that would silently mean
        0 or 1), strings, None, NaN and +/- infinity.
    """
    # bool is a subclass of int; reject it explicitly so Preset(zoom=True) is not read as zoom 1.
    if isinstance(value, bool):
        return False
    # Accept plain ints and floats only; numpy scalars of float type subclass float and are accepted too.
    if not isinstance(value, (int, float)):
        return False
    # NaN compares False with every bound and inf is never a meaningful parameter, so both are invalid.
    return math.isfinite(value)


@dataclass(frozen=True)
class Preset:
    """One named parameter set of the Mode 2 enhancement pipeline (``findsee.mode2.enhance``).

    The pipeline order (review H5) is: centre crop by ``zoom`` -> ``denoise`` -> CLAHE on the Lab L channel ->
    bicubic upscale back to the input size -> unsharp mask -> ``display`` mode.

    Attributes:
        name: preset key, non-empty ``str`` (e.g. ``"cataract"``).
        zoom: magnification, ``float >= 1.0``; the pipeline crops the centre ``1/zoom`` of each side and upscales
            it back to the input size. ``1.0`` skips both crop and upscale.
        denoise: one of ``DENOISE_METHODS``; the denoiser applied after the crop.
        clahe_clip: CLAHE clip limit, ``float > 0`` (OpenCV ``clipLimit``; higher = stronger local contrast).
        clahe_tile: CLAHE tile grid size, ``int >= 1``; the grid is ``clahe_tile x clahe_tile`` tiles.
        sharpen_amount: unsharp-mask amount, ``float >= 0``; ``0`` turns sharpening off.
        display: one of ``DISPLAY_MODES``; the final display mode.
        blue_gain: blue-channel gain, ``float >= 1.0``; used only when ``display == "color_precomp"``.

    Raises:
        ValueError: from ``__post_init__`` when any field has a wrong type or an out-of-range value; the message
            names the field and its allowed values.

    Equality and hashing are the dataclass defaults (field-wise; hashable because the dataclass is frozen).
    """

    # Preset key; must be a non-empty string.
    name: str
    # Magnification factor (unitless), >= 1.0.
    zoom: float
    # Denoiser name, one of DENOISE_METHODS.
    denoise: str
    # CLAHE clip limit (unitless contrast limit), > 0.
    clahe_clip: float
    # CLAHE grid size in tiles per side, integer >= 1.
    clahe_tile: int
    # Unsharp-mask amount (unitless weight of the detail layer), >= 0.
    sharpen_amount: float
    # Display mode name, one of DISPLAY_MODES.
    display: str
    # Multiplier for the blue (BGR channel 0) values, >= 1.0.
    blue_gain: float

    def __post_init__(self) -> None:
        """Validate every field; raise ``ValueError`` naming the field and the allowed values on the first error.

        Runs automatically after the generated ``__init__``. The dataclass is frozen, so values are only checked,
        never coerced or rewritten.
        """
        # name: a non-empty str (whitespace-only names are rejected as effectively empty).
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError(f"Preset.name must be a non-empty str; got {self.name!r}")
        # zoom: finite real number >= 1.0 (zooming out is not supported).
        if not _is_real_number(self.zoom) or self.zoom < 1.0:
            raise ValueError(f"Preset.zoom must be a finite number >= 1.0; got {self.zoom!r}")
        # denoise: one of the fixed method names.
        if not isinstance(self.denoise, str) or self.denoise not in DENOISE_METHODS:
            raise ValueError(f"Preset.denoise must be one of {DENOISE_METHODS}; got {self.denoise!r}")
        # clahe_clip: finite real number strictly greater than 0.
        if not _is_real_number(self.clahe_clip) or self.clahe_clip <= 0:
            raise ValueError(f"Preset.clahe_clip must be a finite number > 0; got {self.clahe_clip!r}")
        # clahe_tile: an int (not bool, not float) >= 1, because OpenCV needs an integer tile grid.
        if isinstance(self.clahe_tile, bool) or not isinstance(self.clahe_tile, int) or self.clahe_tile < 1:
            raise ValueError(f"Preset.clahe_tile must be an int >= 1; got {self.clahe_tile!r}")
        # sharpen_amount: finite real number >= 0 (0 disables the unsharp mask).
        if not _is_real_number(self.sharpen_amount) or self.sharpen_amount < 0:
            raise ValueError(f"Preset.sharpen_amount must be a finite number >= 0; got {self.sharpen_amount!r}")
        # display: one of the fixed display-mode names.
        if not isinstance(self.display, str) or self.display not in DISPLAY_MODES:
            raise ValueError(f"Preset.display must be one of {DISPLAY_MODES}; got {self.display!r}")
        # blue_gain: finite real number >= 1.0 (a gain below 1 would darken blue, which is not the intent).
        if not _is_real_number(self.blue_gain) or self.blue_gain < 1.0:
            raise ValueError(f"Preset.blue_gain must be a finite number >= 1.0; got {self.blue_gain!r}")
