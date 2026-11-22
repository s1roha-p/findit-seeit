"""Named Mode 2 presets (Part C).

Interface: ``work/claude-main/C-20261122T1606Z-claude-0984/LANES.md`` section 1.

- ``PRESETS``: ``dict[str, Preset]`` with exactly the keys ``"cataract"`` and ``"amd"``; each value's ``name``
  equals its key.
- ``get_preset(name)``: look a preset up by name; an unknown name raises ``KeyError``.
- ``make_custom(base, *, zoom=None, clahe_clip=None, sharpen_amount=None, display=None, name="custom")``: a NEW,
  unregistered ``Preset`` built from ``base`` with the given overrides (round 2, LANES.md section 2R); this is what
  the demo's sliders (zoom, contrast, sharpen, display) call.

``Preset`` itself lives in ``findsee.types`` (shared types); it is imported here so ``findsee.mode2.presets.Preset``
also resolves, as ``docs/project/ARCHITECTURE.md`` lists it under this module.

This module must not import ``findsee.mode2.pipeline`` (the pipeline imports this module; the reverse would be a
circular import).
"""

from __future__ import annotations

import dataclasses  # dataclasses.replace: copy a frozen Preset with some fields changed (re-runs validation)

from findsee.types import Preset  # the frozen, validated parameter dataclass

# Names exported by ``from findsee.mode2.presets import *``.
__all__ = ["PRESETS", "Preset", "get_preset", "make_custom"]

# DRAFT VALUES - NOT EVALUATED. These are starting points copied from LANES.md section 1; tuning them against
# measured legibility (CER on simulated-vision photos, docs/project/EVALUATION_PROTOCOL.md) is a later stage.
# Do not quote them as validated settings.
PRESETS: dict[str, Preset] = {
    # Cataract: clouded lens -> blur, contrast loss and yellowing. Moderate 2x zoom, edge-preserving bilateral
    # denoise, stronger CLAHE (clip 3.0) for contrast loss, sharpen 1.0, and a 1.3x blue gain to offset the
    # yellow (blue-absorbing) lens.
    "cataract": Preset(
        name="cataract",  # must equal the dict key
        zoom=2.0,  # centre half of each side, upscaled 2x
        denoise="bilateral",  # edge-preserving smoothing
        clahe_clip=3.0,  # CLAHE clip limit
        clahe_tile=8,  # 8 x 8 tile grid
        sharpen_amount=1.0,  # unsharp-mask amount
        display="color_precomp",  # blue-channel pre-compensation
        blue_gain=1.3,  # blue channel x1.3 (rounded, clipped to 255)
    ),
    # AMD: central vision loss -> needs strong magnification and maximum contrast. 3x zoom, median denoise (cheap,
    # removes speckle before thresholding), CLAHE clip 2.0, sharpen 1.5, binarised yellow-on-black display.
    "amd": Preset(
        name="amd",  # must equal the dict key
        zoom=3.0,  # centre third of each side, upscaled 3x
        denoise="median",  # 3x3 median blur
        clahe_clip=2.0,  # CLAHE clip limit
        clahe_tile=8,  # 8 x 8 tile grid
        sharpen_amount=1.5,  # unsharp-mask amount
        display="binary_dark",  # yellow (0, 255, 255) text on black
        blue_gain=1.0,  # unused by binary_dark; 1.0 = neutral
    ),
}


def get_preset(name: str) -> Preset:
    """Return the preset registered under ``name``.

    Args:
        name: a key of ``PRESETS`` (currently ``"cataract"`` or ``"amd"``); matched exactly (case-sensitive).

    Returns:
        The immutable ``Preset`` stored under ``name`` (the same object each call; it is frozen, so sharing is safe).

    Raises:
        KeyError: when ``name`` is not a known preset; the message lists the known names.
    """
    # Look the name up; a missing key (or an unhashable / non-str name that cannot match) becomes a KeyError
    # listing the known names, so a typo in a UI or test is easy to diagnose.
    try:
        return PRESETS[name]
    except (KeyError, TypeError):
        # TypeError covers an unhashable name (e.g. a list); it is still "not a known preset name".
        raise KeyError(f"unknown preset {name!r}; known presets: {sorted(PRESETS)}") from None


def make_custom(
    base: Preset | str,
    *,
    zoom: float | None = None,
    clahe_clip: float | None = None,
    sharpen_amount: float | None = None,
    display: str | None = None,
    name: str = "custom",
) -> Preset:
    """Return a NEW ``Preset`` equal to ``base`` with the given slider overrides applied (LANES.md section 2R).

    This is what the demo's sliders call: zoom, contrast (CLAHE clip), sharpen and display mode. Fields without a
    slider (``denoise``, ``clahe_tile``, ``blue_gain``) are always copied from ``base``. The result is NOT added to
    ``PRESETS``, and neither ``base`` nor ``PRESETS`` is changed (``Preset`` is frozen; a new object is built).

    Args:
        base: a ``Preset`` or a preset name (a key of ``PRESETS``, looked up with ``get_preset``).
        zoom: new magnification, ``float >= 1.0``; ``None`` keeps ``base.zoom``.
        clahe_clip: new CLAHE clip limit (the "contrast" slider), ``float > 0``; ``None`` keeps ``base.clahe_clip``.
        sharpen_amount: new unsharp-mask amount, ``float >= 0``; ``None`` keeps ``base.sharpen_amount``.
        display: new display mode, one of ``findsee.types.DISPLAY_MODES``; ``None`` keeps ``base.display``.
        name: the ``name`` of the returned preset, non-empty ``str``; always applied (default ``"custom"``).

    Returns:
        A new, validated ``Preset``. With every override ``None`` it equals ``base`` except for ``name``.

    Raises:
        KeyError: ``base`` is a ``str`` that is not a known preset name (raised by ``get_preset``).
        TypeError: ``base`` is neither a ``Preset`` nor a ``str``.
        ValueError: an override or ``name`` is invalid (raised by ``Preset.__post_init__``, which
            ``dataclasses.replace`` runs on the new object).
    """
    # Resolve the base: a name goes through get_preset (unknown -> KeyError); a Preset is used as is.
    if isinstance(base, str):
        base_preset = get_preset(base)
    elif isinstance(base, Preset):
        base_preset = base
    else:
        # Same convention as pipeline._resolve_preset: a wrong type is a programming error, not a bad value.
        raise TypeError(f"base must be a Preset or a preset name (str); got {type(base).__name__}")
    # Candidate overrides keyed by Preset field name; a None value means "keep the base value".
    candidates: dict[str, object] = {
        "zoom": zoom,  # magnification slider
        "clahe_clip": clahe_clip,  # contrast slider
        "sharpen_amount": sharpen_amount,  # sharpen slider
        "display": display,  # display-mode selector
    }
    # Only the overrides the caller actually set (non-None), plus the name, which is always applied.
    changes: dict[str, object] = {key: value for key, value in candidates.items() if value is not None}
    changes["name"] = name
    # dataclasses.replace builds a NEW Preset through __init__, so __post_init__ validates every field
    # (invalid override or name -> ValueError); base_preset itself is frozen and stays unchanged.
    return dataclasses.replace(base_preset, **changes)
