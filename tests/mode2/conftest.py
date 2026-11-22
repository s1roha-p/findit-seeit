"""Shared synthetic fixtures for Mode 2 (see clearly) contract tests.

All fixtures are generated purely in memory with NumPy and OpenCV: zero disk
I/O, zero image files on disk, and zero photos of people.
"""

from __future__ import annotations

from collections.abc import Callable

import cv2
import numpy as np
import pytest

# Light neutral BGR card background intensity (uint8 in [0, 255]).
_CARD_BG_VALUE: int = 235

# Dark neutral BGR ink color for text and border marks (uint8 BGR tuple).
_CARD_INK_BGR: tuple[int, int, int] = (20, 20, 20)

# Standard deviation (in intensity units) for optional Gaussian sensor noise.
_NOISE_SIGMA: float = 4.0


def _make_synthetic_card(
    height: int = 240,
    width: int = 320,
    *,
    add_noise: bool = True,
    seed: int = 0,
) -> np.ndarray:
    """Create a synthetic BGR uint8 high-contrast text card in memory.

    Args:
        height: Output image height in pixels (expected >= 8).
        width: Output image width in pixels (expected >= 8).
        add_noise: When True, add seeded zero-mean Gaussian noise.
        seed: Integer seed for ``numpy.random.default_rng`` when adding noise.

    Returns:
        A contiguous ``np.ndarray`` of shape ``(height, width, 3)`` and dtype
        ``np.uint8`` in BGR channel order, with dark outer border/corner marks
        and dark centered text/strokes on a bright ``(235, 235, 235)`` card.
    """
    # Allocate bright BGR canvas of shape (height, width, 3), dtype uint8.
    card: np.ndarray = np.full(
        (height, width, 3),
        _CARD_BG_VALUE,
        dtype=np.uint8,
    )

    # Track the shorter side so border geometry scales safely down to 8x8.
    min_side: int = min(height, width)

    # Draw a thin dark outer border so edge content differs from center content.
    if min_side >= 32:
        # Inset margin scaled to canvas size (6 px on 240x320, >= 2 px).
        margin: int = max(2, min_side // 40)
        # Keep strokes thin (2 px on standard 240x320, 1 px on smaller cards).
        border_thickness: int = 2 if min_side >= 64 else 1
        # Draw outer border rectangle inside the canvas bounds.
        cv2.rectangle(
            card,
            (margin, margin),
            (width - 1 - margin, height - 1 - margin),
            _CARD_INK_BGR,
            thickness=border_thickness,
        )

        # Length of each thin corner registration tick (well outside 2x crop).
        tick_len: int = max(3, min_side // 20)
        # Offset of corner ticks slightly inside the outer border.
        tick_offset: int = margin + max(3, border_thickness + 2)
        # Clamp tick coordinates so small >= 32 canvases stay in bounds.
        right_x: int = width - 1 - tick_offset
        bottom_y: int = height - 1 - tick_offset

        # Draw four thin L-shaped corner registration marks near the edges.
        if right_x > tick_offset + tick_len and bottom_y > tick_offset + tick_len:
            # Top-left corner horizontal and vertical ticks.
            cv2.line(
                card,
                (tick_offset, tick_offset),
                (tick_offset + tick_len, tick_offset),
                _CARD_INK_BGR,
                thickness=border_thickness,
            )
            cv2.line(
                card,
                (tick_offset, tick_offset),
                (tick_offset, tick_offset + tick_len),
                _CARD_INK_BGR,
                thickness=border_thickness,
            )
            # Top-right corner horizontal and vertical ticks.
            cv2.line(
                card,
                (right_x, tick_offset),
                (right_x - tick_len, tick_offset),
                _CARD_INK_BGR,
                thickness=border_thickness,
            )
            cv2.line(
                card,
                (right_x, tick_offset),
                (right_x, tick_offset + tick_len),
                _CARD_INK_BGR,
                thickness=border_thickness,
            )
            # Bottom-left corner horizontal and vertical ticks.
            cv2.line(
                card,
                (tick_offset, bottom_y),
                (tick_offset + tick_len, bottom_y),
                _CARD_INK_BGR,
                thickness=border_thickness,
            )
            cv2.line(
                card,
                (tick_offset, bottom_y),
                (tick_offset, bottom_y - tick_len),
                _CARD_INK_BGR,
                thickness=border_thickness,
            )
            # Bottom-right corner horizontal and vertical ticks.
            cv2.line(
                card,
                (right_x, bottom_y),
                (right_x - tick_len, bottom_y),
                _CARD_INK_BGR,
                thickness=border_thickness,
            )
            cv2.line(
                card,
                (right_x, bottom_y),
                (right_x, bottom_y - tick_len),
                _CARD_INK_BGR,
                thickness=border_thickness,
            )
    else:
        # For tiny canvases (down to 8x8), draw a 1 px border along the edges.
        cv2.rectangle(
            card,
            (0, 0),
            (width - 1, height - 1),
            _CARD_INK_BGR,
            thickness=1,
        )

    # Draw dark high-contrast foreground strokes in the center region.
    if height >= 40 and width >= 60:
        # Use OpenCV simplex font for crisp, thin ASCII strokes.
        font_face: int = cv2.FONT_HERSHEY_SIMPLEX
        # Use thickness=2 on standard 240x320 and 1 on compact canvases.
        text_thickness: int = 2 if min_side >= 120 else 1
        # Short two-line ASCII text sized to remain inside 2x and 3x crops.
        lines: tuple[str, str] = ("500mg", "1 TAB")
        # Initial font scale proportional to canvas dimensions.
        raw_scale: float = min(height / 240.0, width / 320.0) * 0.65
        font_scale: float = max(0.35, min(0.65, raw_scale))

        # Shrink font_scale if needed so widest line fits inside 45% of width.
        max_text_width: int = max(1, int(width * 0.45))
        widest_px: int = max(
            cv2.getTextSize(line, font_face, font_scale, text_thickness)[0][0]
            for line in lines
        )
        if widest_px > max_text_width:
            # Scale down proportionally while keeping a readable positive floor.
            font_scale = max(0.25, font_scale * (max_text_width / widest_px))

        # Measure each line's bounding box (width, height) at the final scale.
        metrics: list[tuple[int, int]] = [
            cv2.getTextSize(line, font_face, font_scale, text_thickness)[0]
            for line in lines
        ]
        # Vertical gap between the two centered text lines in pixels.
        line_gap: int = max(4, metrics[0][1] // 2)
        # Combined height of both text lines plus the inter-line gap.
        total_text_height: int = metrics[0][1] + line_gap + metrics[1][1]
        # Top y-coordinate that vertically centers the two-line text block.
        top_y: int = max(2, (height - total_text_height) // 2)

        # Render both centered lines onto the card with anti-aliased strokes.
        current_top: int = top_y
        for line, (text_w, text_h) in zip(lines, metrics):
            # Left x-coordinate that horizontally centers this line.
            origin_x: int = max(2, (width - text_w) // 2)
            # OpenCV putText uses the baseline y-coordinate (bottom of glyphs).
            baseline_y: int = min(height - 2, current_top + text_h)
            # Draw dark text directly onto the BGR uint8 card array.
            cv2.putText(
                card,
                line,
                (origin_x, baseline_y),
                font_face,
                font_scale,
                _CARD_INK_BGR,
                thickness=text_thickness,
                lineType=cv2.LINE_AA,
            )
            # Advance vertical cursor for the next line.
            current_top = baseline_y + line_gap
    else:
        # For tiny canvases (e.g., 8x8), draw a thin centered 1 px dark cross.
        cy: int = height // 2
        cx: int = width // 2
        # Half-arm length kept inside the 1 px outer border.
        half_y: int = max(1, (height - 4) // 2)
        half_x: int = max(1, (width - 4) // 2)
        # Clamped slice bounds guaranteed to stay within [1, dim - 1).
        y_start: int = max(1, cy - half_y)
        y_end: int = min(height - 1, cy + half_y + 1)
        x_start: int = max(1, cx - half_x)
        x_end: int = min(width - 1, cx + half_x + 1)
        # Paint 1 px horizontal and vertical center bars in dark BGR ink.
        card[cy, x_start:x_end] = _CARD_INK_BGR
        card[y_start:y_end, cx] = _CARD_INK_BGR

    # Optionally add reproducible zero-mean Gaussian noise and clip to uint8.
    if add_noise:
        # Local seeded RNG avoids mutating global NumPy random state.
        rng: np.random.Generator = np.random.default_rng(seed)
        # Float64 Gaussian noise matching (height, width, 3).
        noise: np.ndarray = rng.normal(
            loc=0.0,
            scale=_NOISE_SIGMA,
            size=card.shape,
        )
        # Add noise in float64, round to nearest integer, and clip to [0, 255].
        noisy_float: np.ndarray = np.rint(card.astype(np.float64) + noise)
        card = np.clip(noisy_float, 0.0, 255.0).astype(np.uint8)

    # Return contiguous BGR uint8 synthetic card array.
    return card


@pytest.fixture
def synthetic_card_bgr() -> np.ndarray:
    """Return a fresh 240x320 BGR uint8 synthetic card with seeded noise."""
    # Standard 240x320 card with add_noise=True and deterministic seed=0.
    return _make_synthetic_card(240, 320, add_noise=True, seed=0)


@pytest.fixture
def clean_card_bgr() -> np.ndarray:
    """Return a fresh 240x320 BGR uint8 synthetic card with zero noise."""
    # Noise-free 240x320 card for unambiguous binary_dark polarity checks.
    return _make_synthetic_card(240, 320, add_noise=False, seed=0)


@pytest.fixture
def make_card_bgr() -> Callable[..., np.ndarray]:
    """Return the synthetic BGR card factory for custom and edge-case sizes."""
    # Expose the pure in-memory factory callable directly to tests.
    return _make_synthetic_card
