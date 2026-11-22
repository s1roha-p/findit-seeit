"""Mode 2 synthetic CPU frame-rate (FPS) microbenchmark for FindSee (Part C).

This script implements an E0-tier CPU microbenchmark for backlog item B-10
(Mode 2 live-path throughput at 1280x720). It synthesizes an in-memory BGR
uint8 document-like test card with seeded Gaussian noise, runs warm-up and
timed calls to ``findsee.mode2.pipeline.enhance`` for one or all registered
presets, and prints an ASCII-safe JSON summary to stdout.

Constraints enforced by this script:
- Writes zero files to disk at runtime (Part D ``eval/records.py`` does not
  exist yet, so ``record_id`` is ``null`` with an explicit reason).
- Never opens a camera (``cv2.VideoCapture``) and never reads or writes image
  files or personal data.
- Reports E0 synthetic CPU numbers only; E2 protocol speed numbers require
  300 timed frames after 30 warm-up frames on the demo machine recorded via
  ``eval/records.py``.
"""

import argparse
import dataclasses
import json
import os
import pathlib
import platform
import sys
import time

import cv2
import numpy as np

# Resolve the repository root (parent of eval/) as an absolute pathlib.Path.
_REPO_ROOT: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent

# Resolve the package source directory (<repo_root>/src) as a string for sys.path.
_SRC_DIR: str = str(_REPO_ROOT / "src")

# Prepend src/ to sys.path when absent so direct invocation
# (`python eval/bench_mode2_fps.py`) can import findsee without editable install.
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

# Import the frozen Mode 2 interface defined in LANES.md section 1.
from findsee.mode2.pipeline import enhance
from findsee.mode2.presets import PRESETS, get_preset

# Constant BGR uint8 color (235, 235, 235) for the light paper-like card background.
_CARD_BG_BGR: tuple[int, int, int] = (235, 235, 235)

# Constant BGR uint8 color (20, 20, 20) for dark border marks and synthetic text.
_CARD_FG_BGR: tuple[int, int, int] = (20, 20, 20)

# Constant standard deviation (in 8-bit intensity levels) for synthetic sensor noise.
_NOISE_SIGMA: float = 4.0

# Constant minimum spatial dimension (pixels) accepted by Mode 2 enhance().
_MIN_DIM_PX: int = 8

# Constant minimum width (pixels) required before attempting OpenCV text rendering.
_MIN_TEXT_WIDTH_PX: int = 32

# Constant minimum height (pixels) required before attempting OpenCV text rendering.
_MIN_TEXT_HEIGHT_PX: int = 24

# Constant ASCII-only placeholder text lines drawn onto the synthetic test card.
_CARD_TEXT_LINES: tuple[str, ...] = (
    "FINDSEE MODE2 BENCH",
    "SYNTHETIC TEXT CARD",
    "0123456789 ABCDEFGH",
)

# Constant explanation string when no immutable E2 record writer is available yet.
_RECORD_ID_REASON: str = "no record writer yet (Part D eval/records.py)"

# Constant limitations disclosure matching EVALUATION_PROTOCOL.md E0 vs E2 rules.
_LIMITATIONS_TEXT: str = (
    "E0 synthetic CPU microbenchmark only (no camera, no disk record writer); "
    "E2 protocol requires 300 frames after 30 warmup on the demo machine with "
    "eval/records.py."
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse and validate command-line arguments for the Mode 2 FPS benchmark.

    Args:
        argv: Optional list of CLI argument strings (excluding program name).
            When ``None``, ``argparse`` reads from ``sys.argv[1:]``.

    Returns:
        Validated ``argparse.Namespace`` containing ``preset`` (str),
        ``frames`` (int >= 1), ``warmup`` (int >= 0), ``width`` (int >= 8),
        and ``height`` (int >= 8).

    Raises:
        SystemExit: Raised by ``parser.error()`` when any argument is invalid.
    """
    # Build the deterministic sorted list of allowed --preset values.
    preset_choices: tuple[str, ...] = ("both", *sorted(PRESETS.keys()))

    # Create the CLI parser with a concise ASCII description.
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=(
            "E0 synthetic CPU FPS benchmark for FindSee Mode 2 enhance() "
            "(backlog B-10; prints JSON to stdout, writes no files)."
        )
    )

    # Register --preset to select one registered preset or all ("both").
    parser.add_argument(
        "--preset",
        default="both",
        choices=preset_choices,
        help="Mode 2 preset name to benchmark, or 'both' for all presets.",
    )

    # Register --frames for the number of timed enhance() iterations (>= 1).
    parser.add_argument(
        "--frames",
        type=int,
        default=60,
        help="Number of timed frames per preset (default: 60, minimum: 1).",
    )

    # Register --warmup for the number of untimed warm-up iterations (>= 0).
    parser.add_argument(
        "--warmup",
        type=int,
        default=5,
        help="Number of untimed warm-up frames per preset (default: 5, minimum: 0).",
    )

    # Register --width for the synthetic BGR frame width in pixels (>= 8).
    parser.add_argument(
        "--width",
        type=int,
        default=1280,
        help="Synthetic frame width in pixels (default: 1280, minimum: 8).",
    )

    # Register --height for the synthetic BGR frame height in pixels (>= 8).
    parser.add_argument(
        "--height",
        type=int,
        default=720,
        help="Synthetic frame height in pixels (default: 720, minimum: 8).",
    )

    # Parse raw CLI arguments into a Namespace.
    args: argparse.Namespace = parser.parse_args(argv)

    # Reject non-positive timed frame counts because median/p90 need >= 1 sample.
    if args.frames < 1:
        parser.error(f"--frames must be >= 1, got {args.frames}")

    # Reject negative warm-up counts.
    if args.warmup < 0:
        parser.error(f"--warmup must be >= 0, got {args.warmup}")

    # Reject widths below the Mode 2 pipeline minimum of 8 pixels.
    if args.width < _MIN_DIM_PX:
        parser.error(f"--width must be >= {_MIN_DIM_PX}, got {args.width}")

    # Reject heights below the Mode 2 pipeline minimum of 8 pixels.
    if args.height < _MIN_DIM_PX:
        parser.error(f"--height must be >= {_MIN_DIM_PX}, got {args.height}")

    # Return the validated CLI arguments.
    return args


def build_synthetic_frame(width: int, height: int, seed: int = 0) -> np.ndarray:
    """Build a deterministic in-memory BGR uint8 synthetic text-card frame.

    The card has a light gray background ``(235, 235, 235)``, dark corner
    registration marks ``(20, 20, 20)``, centered dark ASCII text rendered via
    ``cv2.putText`` (when the frame is large enough to host text safely), and
    seeded zero-mean Gaussian noise (sigma = 4.0 intensity levels) clipped to
    ``[0, 255]``. Border marks and text rendering are guarded so even the
    minimum valid size ``8x8`` succeeds without out-of-bounds indexing or
    OpenCV errors.

    Args:
        width: Frame width in pixels; must be an integer >= 8.
        height: Frame height in pixels; must be an integer >= 8.
        seed: Non-negative integer seed for ``np.random.default_rng``.

    Returns:
        Contiguous ``np.ndarray`` of shape ``(height, width, 3)``, BGR channel
        order, dtype ``np.uint8``, pixel values in ``[0, 255]``.

    Raises:
        ValueError: If ``width < 8`` or ``height < 8``.
    """
    # Enforce the Mode 2 minimum frame dimensions when called programmatically.
    if width < _MIN_DIM_PX or height < _MIN_DIM_PX:
        raise ValueError(
            f"width and height must be >= {_MIN_DIM_PX}, got width={width}, height={height}"
        )

    # Allocate the base (height, width, 3) uint8 BGR canvas filled with light gray.
    canvas: np.ndarray = np.full(
        shape=(height, width, 3),
        fill_value=_CARD_BG_BGR,
        dtype=np.uint8,
    )

    # Compute the shorter side in pixels to scale margins, marks, and strokes.
    min_dim: int = min(width, height)

    # Compute an inward border margin clamped to at least 1 pixel.
    margin: int = max(1, min_dim // 20)

    # Compute the inner bounding box coordinates inside [0, width - 1] and [0, height - 1].
    left_x: int = margin
    right_x: int = width - 1 - margin
    top_y: int = margin
    bottom_y: int = height - 1 - margin

    # Draw dark L-shaped corner registration marks only when an inner box exists.
    if left_x < right_x and top_y < bottom_y:
        # Compute interior span along x and y to prevent corner arms from overlapping.
        span_x: int = right_x - left_x
        span_y: int = bottom_y - top_y

        # Compute corner arm length bounded by one-third of each interior span.
        arm_len: int = max(1, min(min_dim // 12, span_x // 3, span_y // 3))

        # Compute line thickness in pixels (>= 1) scaled gently with frame size.
        mark_thickness: int = max(1, min_dim // 180)

        # Draw top-left corner horizontal and vertical dark marks.
        cv2.line(canvas, (left_x, top_y), (left_x + arm_len, top_y), _CARD_FG_BGR, mark_thickness)
        cv2.line(canvas, (left_x, top_y), (left_x, top_y + arm_len), _CARD_FG_BGR, mark_thickness)

        # Draw top-right corner horizontal and vertical dark marks.
        cv2.line(canvas, (right_x, top_y), (right_x - arm_len, top_y), _CARD_FG_BGR, mark_thickness)
        cv2.line(canvas, (right_x, top_y), (right_x, top_y + arm_len), _CARD_FG_BGR, mark_thickness)

        # Draw bottom-left corner horizontal and vertical dark marks.
        cv2.line(canvas, (left_x, bottom_y), (left_x + arm_len, bottom_y), _CARD_FG_BGR, mark_thickness)
        cv2.line(canvas, (left_x, bottom_y), (left_x, bottom_y - arm_len), _CARD_FG_BGR, mark_thickness)

        # Draw bottom-right corner horizontal and vertical dark marks.
        cv2.line(canvas, (right_x, bottom_y), (right_x - arm_len, bottom_y), _CARD_FG_BGR, mark_thickness)
        cv2.line(canvas, (right_x, bottom_y), (right_x, bottom_y - arm_len), _CARD_FG_BGR, mark_thickness)

    # Render centered dark ASCII text only when the frame can fit readable glyphs.
    if width >= _MIN_TEXT_WIDTH_PX and height >= _MIN_TEXT_HEIGHT_PX:
        # Select a clean built-in Hershey sans-serif font face.
        font_face: int = cv2.FONT_HERSHEY_SIMPLEX

        # Compute a proportional initial font scale from the shorter frame side.
        font_scale: float = max(0.3, min_dim / 600.0)

        # Compute stroke thickness in pixels (>= 1) proportional to font scale.
        text_thickness: int = max(1, int(round(font_scale * 2.0)))

        # Measure the widest text line at the initial scale to fit inside the card.
        max_line_width: int = 1
        for text_line in _CARD_TEXT_LINES:
            # Query (width_px, height_px) and baseline_px for this ASCII string.
            (line_w, _line_h), _baseline = cv2.getTextSize(
                text_line, font_face, font_scale, text_thickness
            )
            # Track the widest rendered line in pixels.
            if line_w > max_line_width:
                max_line_width = line_w

        # Compute available horizontal text budget (80% of frame width).
        target_text_width: float = max(1.0, width * 0.8)

        # Shrink font_scale when the widest line would overflow the card width.
        if max_line_width > target_text_width:
            font_scale = max(0.25, font_scale * (target_text_width / float(max_line_width)))
            text_thickness = max(1, int(round(font_scale * 2.0)))

        # Measure final glyph metrics for all lines to compute vertical centering.
        measured_lines: list[tuple[str, int, int, int]] = []
        total_block_height: int = 0
        line_gap_px: int = max(4, int(round(12.0 * font_scale)))
        for idx, text_line in enumerate(_CARD_TEXT_LINES):
            # Query final (line_w, line_h) and baseline for each text line.
            (line_w, line_h), baseline = cv2.getTextSize(
                text_line, font_face, font_scale, text_thickness
            )
            # Store tuple of (text, width_px, height_px, baseline_px).
            measured_lines.append((text_line, line_w, line_h, baseline))
            # Accumulate vertical height including inter-line spacing.
            total_block_height += line_h + baseline
            if idx + 1 < len(_CARD_TEXT_LINES):
                total_block_height += line_gap_px

        # Compute the top y-coordinate of the centered multi-line text block.
        cursor_y: int = max(0, (height - total_block_height) // 2)

        # Draw each ASCII text line horizontally centered on the canvas.
        for text_line, line_w, line_h, baseline in measured_lines:
            # Advance cursor_y from top of line to the OpenCV text baseline.
            baseline_y: int = cursor_y + line_h

            # Stop drawing remaining lines if baseline_y would fall outside the frame.
            if baseline_y >= height:
                break

            # Compute horizontally centered origin x clamped to [0, width - 1].
            origin_x: int = max(0, min(width - 1, (width - line_w) // 2))

            # Render the dark ASCII text line with anti-aliased strokes.
            cv2.putText(
                canvas,
                text_line,
                (origin_x, baseline_y),
                font_face,
                font_scale,
                _CARD_FG_BGR,
                text_thickness,
                cv2.LINE_AA,
            )

            # Advance cursor_y past the descender baseline and inter-line gap.
            cursor_y = baseline_y + baseline + line_gap_px

    # Instantiate an isolated deterministic NumPy RNG with the requested seed.
    rng: np.random.Generator = np.random.default_rng(seed)

    # Sample zero-mean Gaussian noise (float64, shape (height, width, 3), sigma=4.0).
    noise: np.ndarray = rng.normal(loc=0.0, scale=_NOISE_SIGMA, size=canvas.shape)

    # Add noise in float64, round to nearest integer, clip to [0, 255], cast to uint8.
    noisy_frame: np.ndarray = np.clip(
        np.rint(canvas.astype(np.float64) + noise),
        0.0,
        255.0,
    ).astype(np.uint8)

    # Return a guaranteed C-contiguous (height, width, 3) BGR uint8 array.
    return np.ascontiguousarray(noisy_frame, dtype=np.uint8)


def benchmark_preset(
    frame: np.ndarray,
    preset_name: str,
    warmup: int,
    frames: int,
) -> dict[str, object]:
    """Benchmark ``enhance(frame, preset)`` latency and throughput for one preset.

    Args:
        frame: Input BGR ``uint8`` array of shape ``(H, W, 3)`` with ``H, W >= 8``.
        preset_name: Registered preset key in ``findsee.mode2.presets.PRESETS``.
        warmup: Number of untimed warm-up calls before measurement (>= 0).
        frames: Number of timed calls to collect latency samples (>= 1).

    Returns:
        Dictionary containing ``preset`` (str), ``preset_config`` (dict),
        ``median_ms`` (float), ``p90_ms`` (float), and ``fps`` (float or None
        if ``median_ms <= 0.0``).

    Raises:
        ValueError: If ``frames < 1`` or ``warmup < 0``.
        KeyError: If ``preset_name`` is not in ``PRESETS``.
        RuntimeError: If the returned enhanced frame violates the output
            contract (shape equal to ``frame.shape`` and dtype ``np.uint8``).
    """
    # Guard against invalid iteration counts when called programmatically.
    if frames < 1:
        raise ValueError(f"frames must be >= 1, got {frames}")
    if warmup < 0:
        raise ValueError(f"warmup must be >= 0, got {warmup}")

    # Resolve the frozen Preset dataclass by name (raises KeyError if unknown).
    preset = get_preset(preset_name)

    # Run untimed warm-up calls so CPU caches and OpenCV internals stabilize.
    for _ in range(warmup):
        _ = enhance(frame, preset)

    # Allocate list to record per-frame elapsed durations in milliseconds.
    timings_ms: list[float] = []

    # Hold the most recent output array for post-loop contract validation.
    last_out: np.ndarray | None = None

    # Execute timed iterations using monotonic high-resolution time.perf_counter().
    for _ in range(frames):
        # Capture start timestamp in seconds.
        t_start: float = time.perf_counter()

        # Execute the Mode 2 enhancement pipeline on the synthetic frame.
        last_out = enhance(frame, preset)

        # Capture end timestamp in seconds.
        t_end: float = time.perf_counter()

        # Convert elapsed duration from seconds to milliseconds and record it.
        elapsed_ms: float = (t_end - t_start) * 1000.0
        timings_ms.append(elapsed_ms)

    # Validate output shape and dtype outside the timed loop (never use assert,
    # because `python -O` strips assertions).
    if last_out is None or last_out.shape != frame.shape or last_out.dtype != np.uint8:
        actual_desc: str = (
            "None"
            if last_out is None
            else f"shape={last_out.shape}, dtype={last_out.dtype}"
        )
        raise RuntimeError(
            f"enhance() contract violation for preset {preset_name!r}: "
            f"expected shape={frame.shape}, dtype=uint8; got {actual_desc}"
        )

    # Compute the median frame latency in milliseconds across all timed runs.
    median_ms: float = float(np.median(timings_ms))

    # Compute the 90th-percentile frame latency in milliseconds.
    p90_ms: float = float(np.percentile(timings_ms, 90))

    # Derive throughput in frames per second from median latency (None if zero).
    fps: float | None = (1000.0 / median_ms) if median_ms > 0.0 else None

    # Return the structured per-preset timing record.
    return {
        "preset": preset_name,
        "preset_config": dataclasses.asdict(preset),
        "median_ms": median_ms,
        "p90_ms": p90_ms,
        "fps": fps,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the E0 Mode 2 synthetic CPU FPS benchmark and print ASCII JSON.

    Args:
        argv: Optional CLI argument list for programmatic testing; ``None``
            reads ``sys.argv[1:]``.

    Returns:
        Process exit status code ``0`` on success.
    """
    # Parse and validate command-line options.
    args: argparse.Namespace = parse_args(argv)

    # Construct the deterministic in-memory (height, width, 3) BGR uint8 frame.
    frame: np.ndarray = build_synthetic_frame(
        width=args.width,
        height=args.height,
        seed=0,
    )

    # Resolve the ordered list of preset names to benchmark.
    target_presets: list[str] = (
        list(sorted(PRESETS.keys())) if args.preset == "both" else [args.preset]
    )

    # Benchmark each requested preset and collect results keyed by preset name.
    results_by_preset: dict[str, dict[str, object]] = {}
    for preset_name in target_presets:
        results_by_preset[preset_name] = benchmark_preset(
            frame=frame,
            preset_name=preset_name,
            warmup=args.warmup,
            frames=args.frames,
        )

    # Assemble the E0 JSON summary payload with full environment and protocol metadata.
    summary: dict[str, object] = {
        "backlog_id": "B-10",
        "tier": "E0",
        "record_id": None,
        "record_id_reason": _RECORD_ID_REASON,
        "synthetic": True,
        "frame_shape": [args.height, args.width, 3],
        "frames": args.frames,
        "warmup": args.warmup,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "cv2_version": cv2.__version__,
        "cv2_num_threads": int(cv2.getNumThreads()),
        "results": results_by_preset,
        "limitations": _LIMITATIONS_TEXT,
    }

    # Serialize the summary as strictly ASCII JSON and emit it to stdout only.
    print(json.dumps(summary, indent=2, ensure_ascii=True))

    # Return zero exit status without writing any files to disk.
    return 0


# Standard module entry point delegating to main() and propagating its exit code.
if __name__ == "__main__":
    raise SystemExit(main())
