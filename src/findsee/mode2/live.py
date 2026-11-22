"""Mode 2 live magnifier path (Part C): camera capture, fps meter, status overlay and the interactive loop.

Interface (frozen): ``work/claude-main/C-20261122T1606Z-claude-0984/LANES.md`` section 2R.

- ``FpsMeter(window=30, clock=time.perf_counter)``: frames per second over the newest ``window`` ticks.
- ``draw_status(frame, text)``: a NEW copy of ``frame`` with ASCII ``text`` drawn top-left on a filled black box.
- ``open_camera(index=0, width=1280, height=720)``: open one camera, request a size, return the capture and the
  EFFECTIVE ``(width, height)`` (CLAUDE.md rule 8: report requested and effective; no fallback to another camera).
- ``run_live(camera_index=0, preset="cataract", width=1280, height=720)``: the interactive loop.

Privacy (``docs/project/DATA_POLICY.md``): camera frames stay in memory only. Nothing in this module writes a frame,
a crop or a video to disk, and nothing is uploaded; each frame is dropped once it has been shown.

Hardware: ``run_live`` needs a real camera and a display (an OpenCV HighGUI window), so it is not unit-tested. The
other three names are testable with fakes (an injected clock; a monkeypatched ``cv2.VideoCapture`` as seen from this
module). ``findsee.mode2.__init__`` does not import this module, so importing the package needs no GUI backend.

Libraries: ``numpy`` and ``opencv-python`` (``cv2``) only, plus the standard library.
"""

from __future__ import annotations

import collections  # collections.deque(maxlen=window): bounded FIFO of tick timestamps
import logging  # package code logs through logging (CLAUDE.md rule 5.9), never print
import time  # time.perf_counter: the default monotonic, high-resolution clock for FpsMeter
from typing import Callable  # type of the injectable clock (no-argument function returning seconds)

import cv2  # OpenCV: VideoCapture, text drawing, HighGUI window and keyboard
import numpy as np  # ndarray type of frames

from findsee.mode2.pipeline import _validate_image, enhance  # frame check shared with enhance(); the pipeline
from findsee.mode2.presets import get_preset  # preset name -> Preset (unknown name -> KeyError)
from findsee.types import Preset  # the validated parameter dataclass

# Names exported by ``from findsee.mode2.live import *``.
__all__ = ["FpsMeter", "draw_status", "open_camera", "run_live"]

# Module logger ("findsee.mode2.live"); the application configures handlers and levels.
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------------------------------------------
# Constants (named so tests, the report and the demo can cite them).
# ---------------------------------------------------------------------------------------------------------------

# Smallest accepted FpsMeter window in ticks: fps needs at least two timestamps to measure one interval.
MIN_FPS_WINDOW: int = 2

# Printable-ASCII code-point range accepted by draw_status (space 0x20 to tilde 0x7E, inclusive). OpenCV's Hershey
# fonts cannot draw Chinese or other non-ASCII glyphs; the app shows Chinese text in its UI, not on the frame.
STATUS_MIN_CODEPOINT: int = 0x20
STATUS_MAX_CODEPOINT: int = 0x7E

# Hershey font used for the status line (plain sans-serif, the most legible built-in OpenCV font).
STATUS_FONT: int = cv2.FONT_HERSHEY_SIMPLEX
# Font scale (unitless multiplier of the font's base size, about 22 px cap height at 1.0); 0.7 keeps a 1280 x 720
# status line readable without covering much of the magnified image.
STATUS_FONT_SCALE: float = 0.7
# Stroke thickness of the text in pixels.
STATUS_THICKNESS: int = 2
# Padding in pixels between the frame's top-left corner / the box edges and the text.
STATUS_PADDING: int = 6
# Text colour, BGR uint8 values: white.
STATUS_TEXT_BGR: tuple[int, int, int] = (255, 255, 255)
# Box colour, BGR uint8 values: black (white on black = maximum contrast for low-vision users).
STATUS_BOX_BGR: tuple[int, int, int] = (0, 0, 0)

# Title of the HighGUI window opened by run_live (ASCII so every OpenCV backend can show it).
WINDOW_NAME: str = "FindSee Mode 2 - live magnifier"

# Key codes returned by cv2.waitKey(1) & 0xFF (low byte of the key code).
KEY_ESC: int = 27  # Esc: quit
KEY_QUIT: int = ord("q")  # q: quit
KEY_CATARACT: int = ord("1")  # 1: switch to the "cataract" preset
KEY_AMD: int = ord("2")  # 2: switch to the "amd" preset
KEY_RAW: int = ord("0")  # 0: show the raw (unenhanced) camera frame

# Label shown in the status line while the raw frame is displayed.
RAW_LABEL: str = "raw"


# ---------------------------------------------------------------------------------------------------------------
# FpsMeter.
# ---------------------------------------------------------------------------------------------------------------


class FpsMeter:
    """Sliding-window frames-per-second meter.

    Call ``tick()`` once per displayed frame; ``fps()`` returns ``(n - 1) / (t_newest - t_oldest)`` over the ``n``
    newest kept ticks (``2 <= n <= window``), i.e. intervals per second across the window.

    Args:
        window: number of newest ticks kept, ``int >= 2`` (default 30, about one second at 30 fps).
        clock: no-argument function returning the current time in seconds as a ``float`` (default
            ``time.perf_counter``); injectable so tests can use a fake clock.

    Raises:
        ValueError: ``window`` is not an ``int`` (``bool`` excluded) or is ``< 2``.
    """

    def __init__(self, window: int = 30, clock: Callable[[], float] = time.perf_counter) -> None:
        """Create an empty meter; see the class docstring for the arguments."""
        # window must be a real int (bool is an int subclass and would mean 0 / 1) and at least MIN_FPS_WINDOW.
        if isinstance(window, bool) or not isinstance(window, int) or window < MIN_FPS_WINDOW:
            raise ValueError(f"FpsMeter window must be an int >= {MIN_FPS_WINDOW}; got {window!r}")
        # Number of newest ticks kept (int >= 2).
        self.window: int = window
        # Time source: seconds as float; only differences between its values are used, so any origin works.
        self._clock: Callable[[], float] = clock
        # Tick timestamps in seconds, oldest first; maxlen drops the oldest automatically once window is reached.
        self._ticks: collections.deque[float] = collections.deque(maxlen=window)

    def tick(self) -> None:
        """Record one frame at the current ``clock()`` time (only the newest ``window`` ticks are kept)."""
        # Append the current timestamp (seconds); the deque discards the oldest when full.
        self._ticks.append(self._clock())

    def fps(self) -> float | None:
        """Return the frame rate over the kept ticks, in frames per second.

        Returns:
            ``(n - 1) / (t_newest - t_oldest)`` as a ``float`` when ``n >= 2`` ticks are kept and the span is
            ``> 0`` seconds; ``None`` with fewer than 2 ticks or a span ``<= 0`` (e.g. a clock that did not advance).
        """
        # Number of kept ticks (0 .. window).
        n = len(self._ticks)
        # One tick or none: no interval to measure.
        if n < 2:
            return None
        # Time span in seconds from the oldest to the newest kept tick.
        span = self._ticks[-1] - self._ticks[0]
        # A zero or negative span (clock not advancing / going backwards) has no meaningful rate.
        if span <= 0:
            return None
        # n ticks bound n - 1 intervals; intervals per second = frames per second.
        return (n - 1) / span


# ---------------------------------------------------------------------------------------------------------------
# Status overlay.
# ---------------------------------------------------------------------------------------------------------------


def draw_status(frame: np.ndarray, text: str) -> np.ndarray:
    """Return a copy of ``frame`` with ``text`` drawn at the top-left in white on a filled black box.

    Args:
        frame: BGR ``uint8`` array, shape ``(H, W, 3)``, ``H, W >= 8`` (validated exactly like ``enhance``'s input).
            Never modified.
        text: a ``str`` whose every character is printable ASCII (code points ``0x20``-``0x7E``); may be empty.

    Returns:
        A NEW BGR ``uint8`` array of shape ``(H, W, 3)``. For ``text == ""`` it is an unchanged copy of ``frame``.
        Otherwise the box spans from ``(0, 0)`` to the text size plus ``STATUS_PADDING`` on each side, clipped to the
        frame; text longer than the frame is simply cut off at the right / bottom edge.

    Raises:
        ValueError: ``frame`` is not a BGR ``uint8`` ``(H, W, 3)`` array with ``H, W >= 8``; ``text`` is not a
            ``str``; or ``text`` contains a character outside ``0x20``-``0x7E`` (e.g. Chinese, tab, newline).
    """
    # Same frame contract as enhance(): ndarray, uint8, (H, W, 3), H and W >= 8 (ValueError otherwise).
    _validate_image(frame)
    # text must be a str (not bytes, None, a number ...).
    if not isinstance(text, str):
        raise ValueError(f"text must be a str; got {type(text).__name__}")
    # Every character must be printable ASCII; report the first offending one with its position and code point.
    for position, char in enumerate(text):
        if not STATUS_MIN_CODEPOINT <= ord(char) <= STATUS_MAX_CODEPOINT:
            raise ValueError(
                f"text must be printable ASCII (0x20-0x7E); character {position} is U+{ord(char):04X}"
            )
    # Private C-contiguous copy (ndarray.copy defaults to C order), so drawing never touches the caller's frame.
    out = frame.copy()
    # Empty text: nothing to draw, return the unchanged copy.
    if text == "":
        return out
    # Frame height and width in pixels.
    frame_h, frame_w = out.shape[:2]
    # Rendered text size in pixels: (width, height above the baseline) and the descender depth below the baseline.
    (text_w, text_h), baseline = cv2.getTextSize(text, STATUS_FONT, STATUS_FONT_SCALE, STATUS_THICKNESS)
    # Box bottom-right corner (inclusive pixel coordinates), clipped to the last column / row of the frame.
    box_right = min(frame_w - 1, text_w + 2 * STATUS_PADDING)
    box_bottom = min(frame_h - 1, text_h + baseline + 2 * STATUS_PADDING)
    # Filled black box from the top-left corner (thickness cv2.FILLED = -1 fills the rectangle).
    cv2.rectangle(out, (0, 0), (box_right, box_bottom), STATUS_BOX_BGR, thickness=cv2.FILLED)
    # Text origin = bottom-left of the text's baseline, in pixels: padding from the left, padding + cap height down.
    origin = (STATUS_PADDING, STATUS_PADDING + text_h)
    # White anti-aliased text; OpenCV clips anything outside the frame.
    cv2.putText(
        out, text, origin, STATUS_FONT, STATUS_FONT_SCALE, STATUS_TEXT_BGR, STATUS_THICKNESS, cv2.LINE_AA
    )
    return out


# ---------------------------------------------------------------------------------------------------------------
# Camera.
# ---------------------------------------------------------------------------------------------------------------


def open_camera(index: int = 0, width: int = 1280, height: int = 720) -> tuple[cv2.VideoCapture, tuple[int, int]]:
    """Open camera ``index``, request ``width x height`` and return the capture with its EFFECTIVE size.

    The driver may ignore or round the requested size, so the size actually delivered is read back with ``get()``
    and returned (CLAUDE.md rule 8: report requested and effective). There is no fallback to another camera index
    or another backend.

    Args:
        index: OpenCV camera index (``int``, 0 = the system's default camera).
        width: requested frame width in pixels.
        height: requested frame height in pixels.

    Returns:
        ``(capture, (effective_width, effective_height))``: the open ``cv2.VideoCapture`` (the caller must
        ``release()`` it) and the effective size in pixels as Python ``int``s.

    Raises:
        RuntimeError: the camera could not be opened (``isOpened()`` is false); the capture has been released and
            the message names the index.
    """
    # Create the capture through the module attribute cv2.VideoCapture (tests monkeypatch exactly this name).
    capture = cv2.VideoCapture(index)
    # A camera that did not open is released (frees any partial backend handle) and reported; no other index tried.
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"camera index {index} could not be opened (cv2.VideoCapture({index}).isOpened() is False)")
    # Request the frame size in pixels; the return value of set() is not trusted (drivers differ), get() is.
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    # Read back the effective size; get() returns a float, rounded to the nearest int pixel count.
    effective_width = int(round(capture.get(cv2.CAP_PROP_FRAME_WIDTH)))
    effective_height = int(round(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    return capture, (effective_width, effective_height)


# ---------------------------------------------------------------------------------------------------------------
# Interactive loop.
# ---------------------------------------------------------------------------------------------------------------


def _ascii_label(name: str) -> str:
    """Return ``name`` with every character outside printable ASCII replaced by ``"?"``.

    Args:
        name: a preset name (any non-empty ``str``; a custom preset may carry a Chinese name).

    Returns:
        A ``str`` that ``draw_status`` accepts (code points ``0x20``-``0x7E`` only), same length as ``name``.
    """
    # Keep printable ASCII characters; replace anything else so the overlay never raises on a custom name.
    return "".join(
        char if STATUS_MIN_CODEPOINT <= ord(char) <= STATUS_MAX_CODEPOINT else "?" for char in name
    )


def _status_text(label: str, fps: float | None) -> str:
    """Build the status line, e.g. ``"cataract | 24.8 fps"`` or ``"raw | -- fps"`` before fps is known.

    Args:
        label: printable-ASCII preset label (or ``RAW_LABEL``).
        fps: frames per second from ``FpsMeter.fps()``, or ``None`` when not yet measurable.

    Returns:
        A printable-ASCII ``str`` for ``draw_status``.
    """
    # Unknown rate (fewer than two ticks): show a placeholder instead of a number.
    if fps is None:
        return f"{label} | -- fps"
    # One decimal is enough to judge smoothness on screen.
    return f"{label} | {fps:.1f} fps"


def run_live(
    camera_index: int = 0, preset: Preset | str = "cataract", width: int = 1280, height: int = 720
) -> None:
    """Run the interactive live magnifier: camera -> ``enhance`` -> status overlay -> window, until quit.

    Keys (read with ``cv2.waitKey(1) & 0xFF`` once per frame): ``q`` or Esc quit; ``1`` switches to the
    ``"cataract"`` preset; ``2`` to ``"amd"``; ``0`` shows the raw camera frame (any preset key leaves raw mode).
    The status line shows the active preset name (or ``"raw"``) and the display rate from ``FpsMeter``.

    Needs a real camera and a display; not unit-tested. Frames stay in memory and are never written to disk.
    Logs the requested and the effective capture size at INFO. A failed ``read()`` logs a WARNING and ends the loop
    (no silent retry). The capture is always released and all OpenCV windows destroyed on exit, also on an error.

    Args:
        camera_index: OpenCV camera index passed to ``open_camera`` (no fallback to another index).
        preset: the starting preset, a preset name (default ``"cataract"``, resolved with ``get_preset``) or a
            ``Preset`` (e.g. one built by ``make_custom``).
        width: requested capture width in pixels.
        height: requested capture height in pixels.

    Raises:
        KeyError: ``preset`` is an unknown preset name (raised before the camera is opened).
        TypeError: ``preset`` is neither a ``Preset`` nor a ``str``.
        RuntimeError: the camera could not be opened (from ``open_camera``).
        ValueError: a camera frame is not BGR ``uint8`` ``(H, W, 3)`` with ``H, W >= 8`` (from ``enhance``).
    """
    # Resolve the starting preset BEFORE touching the camera, so a typo fails fast without opening a device.
    if isinstance(preset, str):
        active = get_preset(preset)
    elif isinstance(preset, Preset):
        active = preset
    else:
        raise TypeError(f"preset must be a Preset or a preset name (str); got {type(preset).__name__}")
    # Open the camera (RuntimeError if it cannot be opened; open_camera releases it itself in that case).
    capture, (effective_width, effective_height) = open_camera(camera_index, width, height)
    # Report requested and effective size (CLAUDE.md rule 8).
    logger.info(
        "camera %d opened: requested %dx%d, effective %dx%d",
        camera_index,
        width,
        height,
        effective_width,
        effective_height,
    )
    # Display-rate meter over the newest 30 frames (default window).
    meter = FpsMeter()
    # True while the raw (unenhanced) frame is shown (key 0); a preset key sets it back to False.
    show_raw = False
    try:
        while True:
            # Grab one frame: ok is a bool, frame a BGR uint8 (H, W, 3) array or None.
            ok, frame = capture.read()
            # A failed read ends the loop with a warning; no silent retry and no switch to another camera.
            if not ok or frame is None:
                logger.warning("camera %d: read() failed; stopping the live loop", camera_index)
                break
            # Count this frame for the display rate.
            meter.tick()
            if show_raw:
                # Raw mode: show the camera frame as captured (draw_status copies it, so it is never altered).
                shown = frame
                label = RAW_LABEL
            else:
                # Enhanced mode: a new uint8 array of the frame's shape.
                shown = enhance(frame, active)
                # Overlay label: the preset name restricted to printable ASCII.
                label = _ascii_label(active.name)
            # Draw "label | fps" top-left on a black box (a new array; frames stay in memory only).
            shown = draw_status(shown, _status_text(label, meter.fps()))
            # Show the frame in the HighGUI window (created on first use).
            cv2.imshow(WINDOW_NAME, shown)
            # Wait 1 ms for a key (this also lets HighGUI repaint); keep the low byte of the key code.
            key = cv2.waitKey(1) & 0xFF
            if key in (KEY_QUIT, KEY_ESC):
                # Quit requested.
                logger.info("live loop: quit key pressed")
                break
            if key == KEY_CATARACT:
                # Switch to the cataract preset and leave raw mode.
                active = get_preset("cataract")
                show_raw = False
                logger.info("live loop: preset -> cataract")
            elif key == KEY_AMD:
                # Switch to the amd preset and leave raw mode.
                active = get_preset("amd")
                show_raw = False
                logger.info("live loop: preset -> amd")
            elif key == KEY_RAW:
                # Show the unenhanced frame; the active preset is kept for when a preset key is pressed again.
                show_raw = True
                logger.info("live loop: raw frame")
    finally:
        # Always free the camera and close the windows, also after an exception (e.g. a malformed frame).
        capture.release()
        cv2.destroyAllWindows()
