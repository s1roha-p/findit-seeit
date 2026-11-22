"""Contract tests for Mode 2 live-camera helpers in ``findsee.mode2.live``.

All assertions are derived strictly from LANES.md sections 1 and 2R:
- ``findsee.mode2.live.FpsMeter`` (window validation, rolling window, clock use)
- ``findsee.mode2.live.draw_status`` (frame and printable ASCII validation, copy)
- ``findsee.mode2.live.open_camera`` (size request, effective size, failure path)

``run_live`` is intentionally neither imported nor tested here because it opens
a real camera and display window.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

import cv2
import numpy as np
import pytest

import findsee.mode2.live as live_mod
from findsee.mode2.live import FpsMeter, draw_status, open_camera

# Standard synthetic test card height in pixels (matches conftest.py).
_CARD_HEIGHT: int = 240

# Standard synthetic test card width in pixels (matches conftest.py).
_CARD_WIDTH: int = 320

# Top-left quadrant height bound for draw_status placement checks (pixels).
_TOP_LEFT_HEIGHT: int = _CARD_HEIGHT // 2

# Top-left quadrant width bound for draw_status placement checks (pixels).
_TOP_LEFT_WIDTH: int = _CARD_WIDTH // 2

# Default requested camera frame width from LANES.md section 2R (pixels).
_DEFAULT_CAM_WIDTH: int = 1280

# Default requested camera frame height from LANES.md section 2R (pixels).
_DEFAULT_CAM_HEIGHT: int = 720


class _FakeClock:
    """Deterministic fake clock returning a scripted sequence of timestamps.

    Tracks how many times the clock callable is invoked so tests can verify
    that ``FpsMeter.fps()`` does not read the clock.
    """

    def __init__(self, timestamps: Iterable[float]) -> None:
        """Initialize the fake clock with a finite iterable of float seconds.

        Args:
            timestamps: Ordered timestamps (in seconds) returned on successive
                calls to this clock instance.
        """
        # Materialize the timestamp sequence into a list of floats in seconds.
        self._timestamps: list[float] = [float(ts) for ts in timestamps]
        # Cursor pointing at the next timestamp index to return.
        self._index: int = 0
        # Total number of times this clock callable has been invoked.
        self.calls: int = 0

    def __call__(self) -> float:
        """Return the next scripted timestamp and increment the call counter.

        Returns:
            The next float timestamp (in seconds) from the scripted sequence.

        Raises:
            IndexError: If called more times than timestamps were supplied.
        """
        # Fail fast if a test or implementation reads past the scripted ticks.
        if self._index >= len(self._timestamps):
            raise IndexError("FakeClock exhausted: more calls than timestamps")
        # Read the current timestamp before advancing internal counters.
        current_time: float = self._timestamps[self._index]
        # Advance cursor and record one clock invocation.
        self._index += 1
        self.calls += 1
        # Return the scripted timestamp in seconds.
        return current_time


class _FakeCapture:
    """Minimal fake for ``cv2.VideoCapture`` used to test ``open_camera``.

    Records constructor arguments, property ``set`` and ``get`` calls, and
    ``release`` calls without touching any real camera hardware.
    """

    def __init__(
        self,
        index: int,
        *args: object,
        opened: bool = True,
        effective_width: float = float(_DEFAULT_CAM_WIDTH),
        effective_height: float = float(_DEFAULT_CAM_HEIGHT),
        **kwargs: object,
    ) -> None:
        """Initialize a fake VideoCapture instance with configurable responses.

        Args:
            index: Camera device index passed to ``cv2.VideoCapture``.
            *args: Any extra positional arguments passed by the caller.
            opened: Value returned by ``isOpened()``.
            effective_width: Float width returned by ``get(CAP_PROP_FRAME_WIDTH)``.
            effective_height: Float height returned by ``get(CAP_PROP_FRAME_HEIGHT)``.
            **kwargs: Any extra keyword arguments passed by the caller.
        """
        # Store constructor arguments for contract verification.
        self.index: int = index
        self.args: tuple[object, ...] = args
        self.kwargs: dict[str, object] = dict(kwargs)
        # Configured open status and effective dimensions (float, as in OpenCV).
        self._opened: bool = opened
        self._effective_width: float = float(effective_width)
        self._effective_height: float = float(effective_height)
        # Ordered log of (prop_id, value) pairs passed to set().
        self.set_calls: list[tuple[int, float]] = []
        # Map of prop_id -> last value passed to set().
        self.set_props: dict[int, float] = {}
        # Ordered log of prop_id values queried via get().
        self.get_calls: list[int] = []
        # Release tracking state and call counter.
        self.released: bool = False
        self.release_calls: int = 0

    def isOpened(self) -> bool:
        """Return whether this fake capture reports an open camera stream."""
        # Return the preconfigured boolean open state.
        return self._opened

    def set(self, prop_id: int, value: float) -> bool:
        """Record a property write request and report success.

        Args:
            prop_id: OpenCV capture property identifier (int).
            value: Requested property value (int or float).

        Returns:
            Always ``True`` to mimic an accepted property request.
        """
        # Convert value to float to match OpenCV VideoCapture.set semantics.
        numeric_value: float = float(value)
        # Record both the ordered call history and latest value per property.
        self.set_calls.append((prop_id, numeric_value))
        self.set_props[prop_id] = numeric_value
        return True

    def get(self, prop_id: int) -> float:
        """Record a property read and return the configured effective value.

        Args:
            prop_id: OpenCV capture property identifier (int).

        Returns:
            Configured effective width or height as float, or ``0.0`` otherwise.
        """
        # Append queried property id to the read log.
        self.get_calls.append(prop_id)
        # Return effective width or height when queried for frame dimensions.
        if prop_id == cv2.CAP_PROP_FRAME_WIDTH:
            return self._effective_width
        if prop_id == cv2.CAP_PROP_FRAME_HEIGHT:
            return self._effective_height
        # Return 0.0 for any other OpenCV property id.
        return 0.0

    def release(self) -> None:
        """Mark this fake capture as released and increment the release count."""
        # Update release flag and counter.
        self.released = True
        self.release_calls += 1


def _make_fake_capture_factory(
    created: list[_FakeCapture],
    *,
    opened: bool = True,
    effective_width: float = float(_DEFAULT_CAM_WIDTH),
    effective_height: float = float(_DEFAULT_CAM_HEIGHT),
) -> Callable[..., _FakeCapture]:
    """Build a ``cv2.VideoCapture`` replacement that records created instances.

    Args:
        created: List mutated in place to collect each constructed fake capture.
        opened: Boolean returned by ``isOpened()`` on each fake capture.
        effective_width: Float width returned by ``get(CAP_PROP_FRAME_WIDTH)``.
        effective_height: Float height returned by ``get(CAP_PROP_FRAME_HEIGHT)``.

    Returns:
        A callable suitable for ``monkeypatch.setattr(live_mod.cv2, "VideoCapture", ...)``.
    """

    def _factory(index: int, *args: object, **kwargs: object) -> _FakeCapture:
        """Instantiate a configured ``_FakeCapture`` and append it to ``created``."""
        # Construct the fake capture with all caller arguments preserved.
        fake_cap: _FakeCapture = _FakeCapture(
            index,
            *args,
            opened=opened,
            effective_width=effective_width,
            effective_height=effective_height,
            **kwargs,
        )
        # Record the instance so tests can inspect creation count and calls.
        created.append(fake_cap)
        return fake_cap

    # Return the configured factory callable.
    return _factory


# ---------------------------------------------------------------------------
# Section A: FpsMeter contract tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_window", [1, 0, -1, -10])
def test_fps_meter_invalid_window_raises_value_error(bad_window: int) -> None:
    """FpsMeter raises ValueError whenever window < 2."""
    # Supply a fake clock so construction never touches the real monotonic clock.
    clock: _FakeClock = _FakeClock([])
    # Any window smaller than 2 cannot form a tick interval and must raise ValueError.
    with pytest.raises(ValueError):
        FpsMeter(window=bad_window, clock=clock)


def test_fps_meter_initial_and_single_tick_return_none_without_clock_on_fps() -> None:
    """With 0 or 1 ticks fps() is None, tick() returns None, and fps() skips clock."""
    # Verify behavior with the default window (30) and with minimum window (2).
    clock_default: _FakeClock = _FakeClock([1.0])
    meter_default: FpsMeter = FpsMeter(clock=clock_default)
    clock_small: _FakeClock = _FakeClock([2.0])
    meter_small: FpsMeter = FpsMeter(window=2, clock=clock_small)

    # With 0 ticks, fps() must return None and must not call the clock.
    assert meter_default.fps() is None
    assert clock_default.calls == 0
    assert meter_small.fps() is None
    assert clock_small.calls == 0

    # First tick() must return None and invoke the clock exactly once.
    tick_result_default: None = meter_default.tick()
    assert tick_result_default is None
    assert clock_default.calls == 1

    tick_result_small: None = meter_small.tick()
    assert tick_result_small is None
    assert clock_small.calls == 1

    # With 1 tick, fps() must still be None and must not invoke the clock.
    assert meter_default.fps() is None
    assert clock_default.calls == 1
    assert meter_small.fps() is None
    assert clock_small.calls == 1


@pytest.mark.parametrize(
    ("window", "timestamps", "expected_fps"),
    [
        # Four uniform ticks at 1/30 s intervals -> (4 - 1) / (3 / 30) = 30.0 fps.
        (30, [0.0, 1.0 / 30.0, 2.0 / 30.0, 3.0 / 30.0], 30.0),
        # Two ticks 0.5 s apart -> (2 - 1) / 0.5 = 2.0 fps.
        (2, [10.0, 10.5], 2.0),
        # Four non-uniform ticks over 1.0 s -> (4 - 1) / 1.0 = 3.0 fps.
        (4, [0.0, 0.25, 0.5, 1.0], 3.0),
    ],
)
def test_fps_meter_exact_fps_calculations(
    window: int,
    timestamps: list[float],
    expected_fps: float,
) -> None:
    """FpsMeter computes (n - 1) / (t_newest - t_oldest) for uniform and uneven ticks."""
    # Build a fake clock with the parametrized timestamp sequence.
    clock: _FakeClock = _FakeClock(timestamps)
    meter: FpsMeter = FpsMeter(window=window, clock=clock)

    # Feed every scripted tick into the meter.
    for _ in timestamps:
        assert meter.tick() is None

    # Read fps and verify float type, expected value, and no extra clock call.
    measured_fps: float | None = meter.fps()
    assert isinstance(measured_fps, float)
    assert measured_fps == pytest.approx(expected_fps)
    assert clock.calls == len(timestamps)


@pytest.mark.parametrize(
    ("window", "timestamps", "expected_fps"),
    [
        # window=2: keeps [1.0, 1.25] -> (2 - 1) / 0.25 = 4.0 fps.
        (2, [0.0, 1.0, 1.25], 4.0),
        # window=4: keeps [10.2, 10.4, 10.6, 10.8] -> (4 - 1) / 0.6 = 5.0 fps.
        (4, [0.0, 10.0, 10.2, 10.4, 10.6, 10.8], 5.0),
    ],
)
def test_fps_meter_rolling_window_evicts_oldest_ticks(
    window: int,
    timestamps: list[float],
    expected_fps: float,
) -> None:
    """FpsMeter keeps only the newest ``window`` ticks and evicts older ones."""
    # Drive FpsMeter with more ticks than its rolling window capacity.
    clock: _FakeClock = _FakeClock(timestamps)
    meter: FpsMeter = FpsMeter(window=window, clock=clock)

    # Record all ticks in sequence.
    for _ in timestamps:
        meter.tick()

    # Result must reflect only the newest ``window`` timestamps.
    measured_fps: float | None = meter.fps()
    assert isinstance(measured_fps, float)
    assert measured_fps == pytest.approx(expected_fps)


def test_fps_meter_default_window_keeps_newest_thirty_ticks() -> None:
    """Default window=30 evicts slow initial ticks once 30 faster ticks arrive."""
    # First 5 slow ticks spaced 1.0 s apart (0.0 .. 4.0 s).
    slow_ticks: list[float] = [float(i) for i in range(5)]
    # Next 30 fast ticks spaced 0.02 s apart (50.0 fps), starting at 5.0 s
    # so retaining tick 4 (4.0 s) would noticeably alter the span.
    fast_ticks: list[float] = [5.0 + 0.02 * i for i in range(30)]
    # Combined 35-tick timeline (5 slow + 30 fast).
    all_ticks: list[float] = slow_ticks + fast_ticks

    # Construct FpsMeter using its default window argument (expected 30).
    clock: _FakeClock = _FakeClock(all_ticks)
    meter: FpsMeter = FpsMeter(clock=clock)

    # Record all 35 ticks.
    for _ in all_ticks:
        meter.tick()

    # Kept 30 ticks span 29 * 0.02 = 0.58 s -> 29 / 0.58 = 50.0 fps.
    measured_fps: float | None = meter.fps()
    assert isinstance(measured_fps, float)
    assert measured_fps == pytest.approx(50.0)


@pytest.mark.parametrize(
    "timestamps",
    [
        # Two identical timestamps -> zero span.
        [5.0, 5.0],
        # Three identical timestamps -> zero span.
        [5.0, 5.0, 5.0],
        # Decreasing timestamps -> negative span.
        [10.0, 9.0],
    ],
)
def test_fps_meter_non_positive_span_returns_none(timestamps: list[float]) -> None:
    """FpsMeter.fps() returns None whenever t_newest - t_oldest <= 0."""
    # Feed scripted zero-span or negative-span timestamps into the meter.
    clock: _FakeClock = _FakeClock(timestamps)
    meter: FpsMeter = FpsMeter(window=len(timestamps), clock=clock)

    # Record every timestamp.
    for _ in timestamps:
        meter.tick()

    # Non-positive span must safely return None instead of dividing by zero.
    assert meter.fps() is None


def test_fps_meter_recovers_after_zero_span_ticks() -> None:
    """FpsMeter recovers once a strictly later tick produces a positive span."""
    # Window of 3 receives two identical ticks followed by a tick 1.0 s later.
    clock: _FakeClock = _FakeClock([5.0, 5.0, 6.0])
    meter: FpsMeter = FpsMeter(window=3, clock=clock)

    # First two ticks have zero span -> fps() is None.
    meter.tick()
    meter.tick()
    assert meter.fps() is None

    # Third tick gives n=3 kept ticks over span 6.0 - 5.0 = 1.0 s -> 2.0 fps.
    meter.tick()
    measured_fps: float | None = meter.fps()
    assert isinstance(measured_fps, float)
    assert measured_fps == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Section B: draw_status contract tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("height", "width"),
    [
        (_CARD_HEIGHT, _CARD_WIDTH),
        (65, 97),
        (8, 8),
    ],
)
@pytest.mark.parametrize("text", ["cataract | 30.0 fps", ""])
def test_draw_status_preserves_shape_dtype_and_does_not_mutate_input(
    make_card_bgr: Callable[..., np.ndarray],
    height: int,
    width: int,
    text: str,
) -> None:
    """draw_status returns a fresh uint8 (H, W, 3) array without mutating input."""
    # Build a synthetic BGR uint8 frame of the parametrized dimensions.
    frame: np.ndarray = make_card_bgr(height, width, add_noise=True, seed=0)
    # Keep an independent copy of the input pixels prior to calling draw_status.
    original: np.ndarray = frame.copy()

    # Overlay status text onto the frame.
    output: np.ndarray = draw_status(frame, text)

    # Output must be a distinct uint8 ndarray with identical shape and no shared memory.
    assert isinstance(output, np.ndarray)
    assert output.shape == (height, width, 3)
    assert output.dtype == np.uint8
    assert output is not frame
    assert not np.shares_memory(output, frame)
    # Input array must remain byte-for-byte identical.
    assert np.array_equal(frame, original)

    # Mutating the returned output array must not affect the input frame.
    output[0, 0, 0] = np.uint8(int(output[0, 0, 0]) ^ 0xFF)
    assert np.array_equal(frame, original)


def test_draw_status_empty_text_returns_unchanged_copy(
    synthetic_card_bgr: np.ndarray,
    make_card_bgr: Callable[..., np.ndarray],
) -> None:
    """draw_status with empty text '' returns a fresh byte-identical copy."""
    # Test both the standard 240x320 fixture and the minimum 8x8 frame size.
    tiny_frame: np.ndarray = make_card_bgr(8, 8, add_noise=False, seed=0)
    for frame in (synthetic_card_bgr, tiny_frame):
        # Empty string must return an unchanged copy without sharing memory.
        output: np.ndarray = draw_status(frame, "")
        assert isinstance(output, np.ndarray)
        assert output.shape == frame.shape
        assert output.dtype == np.uint8
        assert output is not frame
        assert not np.shares_memory(output, frame)
        assert np.array_equal(output, frame)


def test_draw_status_non_empty_text_modifies_top_left_pixels(
    synthetic_card_bgr: np.ndarray,
) -> None:
    """Non-empty status text modifies pixels in the top-left quadrant."""
    # Draw a realistic status banner onto the standard 240x320 synthetic card.
    output: np.ndarray = draw_status(synthetic_card_bgr, "cataract | 30.0 fps")
    # Overall output must differ from the input frame.
    assert not np.array_equal(output, synthetic_card_bgr)
    # Pixel changes must appear inside the top-left quadrant (120x160).
    top_left_out: np.ndarray = output[:_TOP_LEFT_HEIGHT, :_TOP_LEFT_WIDTH]
    top_left_in: np.ndarray = synthetic_card_bgr[:_TOP_LEFT_HEIGHT, :_TOP_LEFT_WIDTH]
    assert not np.array_equal(top_left_out, top_left_in)


def test_draw_status_on_black_frame_draws_visible_text_strokes() -> None:
    """On an all-black frame, draw_status renders visible non-black text pixels."""
    # Allocate an all-black BGR uint8 frame of shape (240, 320, 3).
    black_frame: np.ndarray = np.zeros(
        (_CARD_HEIGHT, _CARD_WIDTH, 3),
        dtype=np.uint8,
    )
    # Keep a reference copy to confirm non-mutation.
    original: np.ndarray = black_frame.copy()

    # Draw short ASCII text; visible strokes must stand out against the black box.
    output: np.ndarray = draw_status(black_frame, "OK")

    # Non-zero pixels must exist in the output and specifically in the top-left quadrant.
    assert np.any(output != black_frame)
    assert np.any(output[:_TOP_LEFT_HEIGHT, :_TOP_LEFT_WIDTH] != 0)
    # Input black frame must remain untouched.
    assert np.array_equal(black_frame, original)


@pytest.mark.parametrize(
    "valid_text",
    [
        # Lower boundary of printable ASCII (0x20 space).
        " ",
        # Upper boundary of printable ASCII (0x7E tilde).
        "~",
        # Mixed digits, letters, and punctuation inside 0x20-0x7E.
        "09AZaz!@#_-.:|",
        # Combined boundary characters and alphanumerics.
        " !~09AZaz",
    ],
)
def test_draw_status_accepts_printable_ascii_boundaries(
    synthetic_card_bgr: np.ndarray,
    valid_text: str,
) -> None:
    """draw_status accepts printable ASCII strings across the 0x20-0x7E range."""
    # Call draw_status with the valid printable ASCII string.
    output: np.ndarray = draw_status(synthetic_card_bgr, valid_text)
    # Verify a fresh valid BGR uint8 array of matching shape is returned.
    assert isinstance(output, np.ndarray)
    assert output.shape == synthetic_card_bgr.shape
    assert output.dtype == np.uint8
    assert output is not synthetic_card_bgr
    assert not np.shares_memory(output, synthetic_card_bgr)


@pytest.mark.parametrize(
    "bad_text",
    [
        # ASCII control characters (< 0x20) and DEL (0x7F).
        "\x00",
        "\t",
        "\n",
        "\r",
        "\x1f",
        "\x7f",
        "ok\nline2",
        "fps\t30",
        # Non-ASCII code points (>= 0x80), Latin-1, Traditional Chinese, and emoji.
        "\u0080",
        "\u00a0",
        "caf\u00e9",
        "\u767d\u5167\u969c",
        "\u85e5\u888b 30fps",
        "\U0001f50d",
    ],
)
def test_draw_status_rejects_non_ascii_and_control_characters(
    synthetic_card_bgr: np.ndarray,
    bad_text: str,
) -> None:
    """Non-ASCII or control characters in text raise ValueError without mutating frame."""
    # Save a copy to confirm validation fails cleanly before any pixel mutation.
    original: np.ndarray = synthetic_card_bgr.copy()
    # Any character outside printable ASCII 0x20-0x7E must raise ValueError.
    with pytest.raises(ValueError):
        draw_status(synthetic_card_bgr, bad_text)
    # Input frame must remain completely unchanged on error.
    assert np.array_equal(synthetic_card_bgr, original)


@pytest.mark.parametrize(
    ("shape", "dtype"),
    [
        # Wrong dtypes (must be uint8).
        ((_CARD_HEIGHT, _CARD_WIDTH, 3), np.float32),
        ((_CARD_HEIGHT, _CARD_WIDTH, 3), np.float64),
        ((_CARD_HEIGHT, _CARD_WIDTH, 3), np.uint16),
        # Wrong number of dimensions (must be 3-D).
        ((_CARD_HEIGHT, _CARD_WIDTH), np.uint8),
        ((1, _CARD_HEIGHT, _CARD_WIDTH, 3), np.uint8),
        # Wrong channel count (must be 3 BGR channels).
        ((_CARD_HEIGHT, _CARD_WIDTH, 1), np.uint8),
        ((_CARD_HEIGHT, _CARD_WIDTH, 4), np.uint8),
        # Spatial dimensions smaller than 8x8.
        ((7, 8, 3), np.uint8),
        ((8, 7, 3), np.uint8),
        ((4, 4, 3), np.uint8),
        ((0, 0, 3), np.uint8),
    ],
)
def test_draw_status_invalid_frame_raises_value_error(
    shape: tuple[int, ...],
    dtype: np.dtype[np.generic] | type[np.generic],
) -> None:
    """Invalid frame dtype, ndim, channel count, or size raises ValueError."""
    # Allocate an invalid test ndarray matching the parametrized spec.
    bad_frame: np.ndarray = np.zeros(shape, dtype=dtype)
    # draw_status must validate frame identically to enhance and raise ValueError.
    with pytest.raises(ValueError):
        draw_status(bad_frame, "ok")


@pytest.mark.parametrize(
    ("shape", "dtype"),
    [
        # Frame smaller than 8x8 with empty text.
        ((7, 8, 3), np.uint8),
        # Wrong dtype with empty text.
        ((_CARD_HEIGHT, _CARD_WIDTH, 3), np.float32),
    ],
)
def test_draw_status_invalid_frame_with_empty_text_raises_value_error(
    shape: tuple[int, ...],
    dtype: np.dtype[np.generic] | type[np.generic],
) -> None:
    """Invalid frames still raise ValueError even when text is empty ''."""
    # Allocate an invalid ndarray to ensure frame validation precedes empty-text shortcut.
    bad_frame: np.ndarray = np.zeros(shape, dtype=dtype)
    with pytest.raises(ValueError):
        draw_status(bad_frame, "")


# ---------------------------------------------------------------------------
# Section C: open_camera contract tests
# ---------------------------------------------------------------------------


def test_open_camera_default_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    """open_camera() requests index 0 and 1280x720, returning capture and int dims."""
    # Collect fake VideoCapture instances constructed during open_camera().
    created: list[_FakeCapture] = []
    # Patch cv2.VideoCapture on the live module's cv2 reference.
    monkeypatch.setattr(
        live_mod.cv2,
        "VideoCapture",
        _make_fake_capture_factory(
            created,
            opened=True,
            effective_width=float(_DEFAULT_CAM_WIDTH),
            effective_height=float(_DEFAULT_CAM_HEIGHT),
        ),
    )

    # Call open_camera with default parameters.
    cap, dims = open_camera()

    # Exactly one capture must be constructed for default index 0 and stay open.
    assert len(created) == 1
    assert cap is created[0]
    assert cap.index == 0
    assert cap.released is False
    assert cap.release_calls == 0

    # Both default width and height must have been requested via set() in any order.
    assert cap.set_props[cv2.CAP_PROP_FRAME_WIDTH] == _DEFAULT_CAM_WIDTH
    assert cap.set_props[cv2.CAP_PROP_FRAME_HEIGHT] == _DEFAULT_CAM_HEIGHT

    # Effective dimensions must be a 2-tuple of exact Python ints.
    assert isinstance(dims, tuple)
    assert len(dims) == 2
    eff_w, eff_h = dims
    assert type(eff_w) is int
    assert type(eff_h) is int
    assert (eff_w, eff_h) == (_DEFAULT_CAM_WIDTH, _DEFAULT_CAM_HEIGHT)


@pytest.mark.parametrize(
    ("use_kwargs", "req_index", "req_width", "req_height"),
    [
        # Keyword arguments requesting 1920x1080 on camera index 2.
        (True, 2, 1920, 1080),
        # Positional arguments requesting 800x600 on camera index 1.
        (False, 1, 800, 600),
    ],
)
def test_open_camera_explicit_args_return_effective_get_dimensions(
    monkeypatch: pytest.MonkeyPatch,
    use_kwargs: bool,
    req_index: int,
    req_width: int,
    req_height: int,
) -> None:
    """open_camera returns effective int dims read from get(), not requested dims."""
    # Simulate a camera that falls back to 640x480 despite larger requested size.
    effective_w: float = 640.0
    effective_h: float = 480.0
    created: list[_FakeCapture] = []
    # Patch cv2.VideoCapture with a fake reporting distinct effective dimensions.
    monkeypatch.setattr(
        live_mod.cv2,
        "VideoCapture",
        _make_fake_capture_factory(
            created,
            opened=True,
            effective_width=effective_w,
            effective_height=effective_h,
        ),
    )

    # Exercise both keyword and positional call forms.
    if use_kwargs:
        cap, dims = open_camera(
            index=req_index,
            width=req_width,
            height=req_height,
        )
    else:
        cap, dims = open_camera(req_index, req_width, req_height)

    # Verify single capture creation, requested index, and active (unreleased) state.
    assert len(created) == 1
    assert cap is created[0]
    assert cap.index == req_index
    assert cap.released is False

    # Verify requested width and height were passed to VideoCapture.set().
    assert cap.set_props[cv2.CAP_PROP_FRAME_WIDTH] == req_width
    assert cap.set_props[cv2.CAP_PROP_FRAME_HEIGHT] == req_height

    # Returned dimensions must be exact ints from get(), not the requested size.
    assert isinstance(dims, tuple)
    assert len(dims) == 2
    eff_w, eff_h = dims
    assert type(eff_w) is int
    assert type(eff_h) is int
    assert (eff_w, eff_h) == (640, 480)
    assert (eff_w, eff_h) != (req_width, req_height)


@pytest.mark.parametrize("camera_index", [0, 3])
def test_open_camera_unopened_releases_and_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
    camera_index: int,
) -> None:
    """When isOpened() is False, open_camera releases once and raises RuntimeError."""
    # Collect fake VideoCapture instances to confirm zero fallback attempts.
    created: list[_FakeCapture] = []
    # Patch cv2.VideoCapture with a fake whose isOpened() returns False.
    monkeypatch.setattr(
        live_mod.cv2,
        "VideoCapture",
        _make_fake_capture_factory(created, opened=False),
    )

    # Opening an unavailable camera must raise RuntimeError naming the index.
    with pytest.raises(RuntimeError) as exc_info:
        open_camera(index=camera_index)

    # Error message must include the failing camera index.
    assert str(camera_index) in str(exc_info.value)
    # Exactly one capture must be attempted (no fallback to another camera index).
    assert len(created) == 1
    assert created[0].index == camera_index
    # The failed capture must be released exactly once.
    assert created[0].released is True
    assert created[0].release_calls == 1
