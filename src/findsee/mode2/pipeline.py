"""Mode 2 enhancement pipeline (Part C): ``enhance(image, preset)``.

Interface (frozen): ``work/claude-main/C-20261122T1606Z-claude-0984/LANES.md`` section 1.

Step order (review H5, ``docs/project/PROPOSAL_REVIEW.md``):

    crop (zoom) -> denoise -> CLAHE on Lab L -> bicubic upscale to input size -> unsharp mask -> display

Contract summary:

- input: ``np.ndarray``, BGR, ``uint8``, shape ``(H, W, 3)`` with ``H, W >= 8``; anything else -> ``ValueError``;
- preset: a ``Preset`` or a preset name (``str``, looked up with ``get_preset``; unknown -> ``KeyError``);
- output: a NEW ``uint8`` array with exactly the input's shape; the input is never modified;
- deterministic (same input + preset -> byte-identical output); no I/O; nothing logged above DEBUG.

Libraries: ``numpy`` and ``opencv-python`` (``cv2``) only.
"""

from __future__ import annotations

import cv2  # OpenCV: filters, colour conversion, CLAHE, resize, adaptive threshold
import numpy as np  # array type, dtype handling, rounding / clipping for color_precomp

from findsee.mode2.presets import get_preset  # name -> Preset lookup (pipeline imports presets, never the reverse)
from findsee.types import Preset  # the validated parameter dataclass

# Names exported by ``from findsee.mode2.pipeline import *``.
__all__ = ["enhance"]

# ---------------------------------------------------------------------------------------------------------------
# Fixed step parameters (module constants so tests, benchmarks and the report can cite them by name).
# ---------------------------------------------------------------------------------------------------------------

# Smallest accepted input height / width in pixels (contract: H, W >= 8).
MIN_SIDE: int = 8

# Median blur aperture in pixels (odd, 3 = 3x3 neighbourhood); light speckle removal that keeps thin strokes.
MEDIAN_KSIZE: int = 3

# Bilateral filter neighbourhood diameter in pixels.
BILATERAL_D: int = 5
# Bilateral colour sigma in 0-255 intensity units: how different two colours may be and still be averaged.
BILATERAL_SIGMA_COLOR: float = 50.0
# Bilateral spatial sigma in pixels: how far apart two pixels may be and still influence each other.
BILATERAL_SIGMA_SPACE: float = 50.0

# Fast NLM (colour) filter strength for the luminance component (higher = smoother, loses detail).
NLM_H: float = 5.0
# Fast NLM filter strength for the colour components.
NLM_H_COLOR: float = 5.0
# Fast NLM template patch size in pixels (odd).
NLM_TEMPLATE_WINDOW: int = 7
# Fast NLM search window size in pixels (odd).
NLM_SEARCH_WINDOW: int = 21

# Gaussian sigma in pixels for the unsharp-mask blur (kernel size derived by OpenCV from sigma).
UNSHARP_SIGMA: float = 1.0

# Preferred adaptive-threshold block size in pixels (odd); clamped per image in _display_binary_dark.
ADAPTIVE_BLOCK_SIZE: int = 31
# Constant subtracted from the Gaussian-weighted local mean before thresholding (0-255 intensity units).
ADAPTIVE_C: float = 10.0

# binary_dark colours (BGR): text / foreground becomes yellow, everything else black.
BINARY_FOREGROUND_BGR: tuple[int, int, int] = (0, 255, 255)
BINARY_BACKGROUND_BGR: tuple[int, int, int] = (0, 0, 0)


# ---------------------------------------------------------------------------------------------------------------
# Validation helpers.
# ---------------------------------------------------------------------------------------------------------------


def _validate_image(image: object) -> None:
    """Check that ``image`` is a BGR ``uint8`` array of shape ``(H, W, 3)`` with ``H, W >= MIN_SIDE``.

    Args:
        image: the caller's input, any object.

    Raises:
        ValueError: not an ``np.ndarray``; dtype is not ``uint8``; ``ndim != 3``; channel count != 3; or
            ``H`` or ``W`` < ``MIN_SIDE``. The message states the expected and the received value.
    """
    # Type: only numpy arrays are accepted (lists, PIL images, None ... are rejected).
    if not isinstance(image, np.ndarray):
        raise ValueError(f"image must be a numpy.ndarray; got {type(image).__name__}")
    # dtype: the pipeline is defined on 8-bit images only (no silent rescaling of float / uint16 input).
    if image.dtype != np.uint8:
        raise ValueError(f"image dtype must be uint8; got {image.dtype}")
    # Rank: exactly (H, W, C); grayscale (H, W) and batches (N, H, W, C) are rejected.
    if image.ndim != 3:
        raise ValueError(f"image must have 3 dimensions (H, W, 3); got shape {image.shape}")
    # Channels: exactly 3 (BGR); BGRA and single-channel 3-D arrays are rejected.
    if image.shape[2] != 3:
        raise ValueError(f"image must have 3 channels (BGR); got shape {image.shape}")
    # Size: both sides at least MIN_SIDE pixels.
    if image.shape[0] < MIN_SIDE or image.shape[1] < MIN_SIDE:
        raise ValueError(f"image height and width must be >= {MIN_SIDE}; got shape {image.shape}")


def _resolve_preset(preset: Preset | str) -> Preset:
    """Return a ``Preset`` from either a ``Preset`` or a preset name.

    Args:
        preset: a ``Preset`` instance (returned unchanged) or a ``str`` key of ``PRESETS``.

    Returns:
        The ``Preset`` to apply.

    Raises:
        KeyError: ``preset`` is a ``str`` that is not a known preset name (raised by ``get_preset``).
        TypeError: ``preset`` is neither a ``Preset`` nor a ``str``.
    """
    # Already a validated preset: use it as is.
    if isinstance(preset, Preset):
        return preset
    # A name: look it up (unknown names raise KeyError listing the known names).
    if isinstance(preset, str):
        return get_preset(preset)
    # Anything else is a programming error, not a bad value of the right type.
    raise TypeError(f"preset must be a Preset or a preset name (str); got {type(preset).__name__}")


# ---------------------------------------------------------------------------------------------------------------
# Pipeline steps; each takes and returns a BGR uint8 array of shape (h, w, 3) unless stated otherwise.
# ---------------------------------------------------------------------------------------------------------------


def _crop_center(img: np.ndarray, zoom: float) -> np.ndarray:
    """Centre-crop ``img`` to ``1/zoom`` of each side.

    Args:
        img: BGR ``uint8`` array, shape ``(H, W, 3)``.
        zoom: magnification ``>= 1.0``; ``1.0`` means no crop.

    Returns:
        A contiguous BGR ``uint8`` copy of shape ``(max(1, round(H / zoom)), max(1, round(W / zoom)), 3)``, or
        ``img`` itself when ``zoom == 1.0``. The window is centred; when the leftover margin is odd the extra pixel
        goes to the bottom / right side (integer floor of the top / left offset).
    """
    # zoom == 1.0 skips the crop entirely (contract).
    if zoom == 1.0:
        return img
    # Input height and width in pixels.
    h, w = img.shape[:2]
    # Crop height / width in pixels: Python round() of H/zoom and W/zoom, at least 1 pixel.
    crop_h = max(1, round(h / zoom))
    crop_w = max(1, round(w / zoom))
    # Top-left corner of the centred window (floor of half the leftover margin).
    top = (h - crop_h) // 2
    left = (w - crop_w) // 2
    # Slice the window and copy it to a contiguous buffer so OpenCV never sees a strided view.
    return np.ascontiguousarray(img[top : top + crop_h, left : left + crop_w])


def _denoise(img: np.ndarray, method: str) -> np.ndarray:
    """Apply the named denoiser.

    Args:
        img: BGR ``uint8`` array, shape ``(h, w, 3)``.
        method: one of ``findsee.types.DENOISE_METHODS``.

    Returns:
        BGR ``uint8`` array of the same shape (``img`` itself for ``"none"``).

    Raises:
        ValueError: unknown method (unreachable for a validated ``Preset``; kept as a guard).
    """
    # "none": no denoising.
    if method == "none":
        return img
    # "median": 3x3 median blur - removes salt-and-pepper speckle, cheap enough for the live path.
    if method == "median":
        return cv2.medianBlur(img, MEDIAN_KSIZE)
    # "bilateral": edge-preserving smoothing (keeps character edges while flattening paper texture).
    if method == "bilateral":
        return cv2.bilateralFilter(img, BILATERAL_D, BILATERAL_SIGMA_COLOR, BILATERAL_SIGMA_SPACE)
    # "nlm": fast non-local means for colour images - strongest and slowest of the three.
    if method == "nlm":
        return cv2.fastNlMeansDenoisingColored(
            img, None, NLM_H, NLM_H_COLOR, NLM_TEMPLATE_WINDOW, NLM_SEARCH_WINDOW
        )
    # Defensive: Preset.__post_init__ already restricts the names.
    raise ValueError(f"unknown denoise method {method!r}")


def _clahe_lab_l(img: np.ndarray, clip: float, tile: int) -> np.ndarray:
    """Apply CLAHE to the L channel of the Lab colour space, leaving a and b untouched.

    Args:
        img: BGR ``uint8`` array, shape ``(h, w, 3)``.
        clip: CLAHE clip limit ``> 0``.
        tile: requested tile grid size ``>= 1`` (grid ``tile x tile``).

    Returns:
        BGR ``uint8`` array of the same shape.

    Note:
        The effective grid is ``min(tile, h, w)`` per side, so a heavily zoomed small crop (e.g. a 3 x 3 pixel crop
        of an 8 x 8 input at zoom 3) never asks OpenCV for tiles smaller than one pixel. For every crop at least
        ``tile`` pixels on each side this equals the requested ``tile``.
    """
    # Crop height and width in pixels.
    h, w = img.shape[:2]
    # Effective tile grid per side: the requested grid, clamped to the crop size (>= 1 since h, w >= 1).
    grid_h = min(tile, h)
    grid_w = min(tile, w)
    # BGR -> Lab (8-bit: L in 0-255), so contrast is equalised on lightness only and hues are not shifted.
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    # Split into the lightness and the two chroma planes, each uint8 (h, w).
    l_chan, a_chan, b_chan = cv2.split(lab)
    # A fresh CLAHE object per call (no shared mutable state between calls / threads). tileGridSize is (width, height).
    clahe = cv2.createCLAHE(clipLimit=float(clip), tileGridSize=(grid_w, grid_h))
    # Equalise the lightness plane locally.
    l_eq = clahe.apply(l_chan)
    # Re-assemble Lab and convert back to BGR uint8.
    return cv2.cvtColor(cv2.merge((l_eq, a_chan, b_chan)), cv2.COLOR_LAB2BGR)


def _upscale_to(img: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    """Bicubic resize of ``img`` to exactly ``(out_h, out_w)``.

    Args:
        img: BGR ``uint8`` array, shape ``(h, w, 3)``.
        out_h: target height in pixels (the INPUT image's height).
        out_w: target width in pixels (the INPUT image's width).

    Returns:
        BGR ``uint8`` array of shape ``(out_h, out_w, 3)``.
    """
    # cv2.resize takes dsize as (width, height); INTER_CUBIC = bicubic interpolation (saturated to uint8).
    return cv2.resize(img, (out_w, out_h), interpolation=cv2.INTER_CUBIC)


def _unsharp_mask(img: np.ndarray, amount: float) -> np.ndarray:
    """Sharpen with an unsharp mask: ``(1 + amount) * img - amount * GaussianBlur(img, sigma=UNSHARP_SIGMA)``.

    Args:
        img: BGR ``uint8`` array, shape ``(h, w, 3)``.
        amount: detail weight ``>= 0``; ``0`` returns ``img`` unchanged.

    Returns:
        BGR ``uint8`` array of the same shape; ``cv2.addWeighted`` rounds and saturates to 0-255.
    """
    # amount == 0 means sharpening is off (contract); skip the work.
    if amount == 0:
        return img
    # Gaussian blur with kernel size derived from sigma ((0, 0) lets OpenCV choose it); sigmaY defaults to sigmaX.
    blur = cv2.GaussianBlur(img, (0, 0), UNSHARP_SIGMA)
    # img * (1 + amount) + blur * (-amount) + 0, computed by OpenCV with saturation to uint8.
    return cv2.addWeighted(img, 1.0 + float(amount), blur, -float(amount), 0)


def _adaptive_block_size(h: int, w: int) -> int:
    """Return the adaptive-threshold block size for an ``h x w`` image.

    Args:
        h: image height in pixels (``>= 3`` assumed; the pipeline guarantees ``>= MIN_SIDE``).
        w: image width in pixels.

    Returns:
        ``ADAPTIVE_BLOCK_SIZE`` clamped to the largest odd value ``<= min(h, w)``, and never below 3.
    """
    # Largest odd number not exceeding the shorter side.
    largest_odd = min(h, w) if min(h, w) % 2 == 1 else min(h, w) - 1
    # Preferred size, clamped down to the image, then up to OpenCV's minimum of 3 (odd and > 1).
    return max(3, min(ADAPTIVE_BLOCK_SIZE, largest_odd))


def _display_binary_dark(img: np.ndarray) -> np.ndarray:
    """Binarise so that dark text becomes yellow ``(0, 255, 255)`` on black ``(0, 0, 0)``.

    Args:
        img: BGR ``uint8`` array, shape ``(H, W, 3)``.

    Returns:
        BGR ``uint8`` array of the same shape in which every pixel is exactly ``BINARY_FOREGROUND_BGR`` or
        ``BINARY_BACKGROUND_BGR``.
    """
    # Image height and width in pixels.
    h, w = img.shape[:2]
    # Grayscale uint8 (h, w) for thresholding.
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Inverted Gaussian adaptive threshold: pixels darker than their local weighted mean minus ADAPTIVE_C become 255
    # (foreground = dark ink), all others 0. Output: uint8 (h, w), values exactly {0, 255}.
    mask = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        _adaptive_block_size(h, w),
        ADAPTIVE_C,
    )
    # Start from an all-black (background) image of the input shape.
    out = np.empty_like(img)
    out[...] = BINARY_BACKGROUND_BGR
    # Paint the foreground (dark text) yellow.
    out[mask == 255] = BINARY_FOREGROUND_BGR
    return out


def _display_color_precomp(img: np.ndarray, blue_gain: float) -> np.ndarray:
    """Multiply the blue channel by ``blue_gain``; leave green and red untouched.

    Args:
        img: BGR ``uint8`` array, shape ``(H, W, 3)`` (the ``plain`` result).
        blue_gain: gain ``>= 1.0``.

    Returns:
        A new BGR ``uint8`` array: channel 0 = ``clip(rint(float32(img[..., 0]) * blue_gain), 0, 255)``; channels 1
        and 2 identical to ``img``. Because ``blue_gain >= 1``, ``out[..., 0] >= img[..., 0]`` elementwise.
    """
    # Copy so channels 1 and 2 stay byte-identical to the plain result and the plain array is not altered.
    out = img.copy()
    # Blue channel as float32 (H, W), scaled by the gain.
    blue = img[..., 0].astype(np.float32) * np.float32(blue_gain)
    # Round half to even (np.rint), clip to the uint8 range, convert back to uint8.
    out[..., 0] = np.clip(np.rint(blue), 0, 255).astype(np.uint8)
    return out


# ---------------------------------------------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------------------------------------------


def enhance(image: np.ndarray, preset: Preset | str) -> np.ndarray:
    """Enhance an image for low-vision display (cataract / AMD pre-compensation).

    Steps, in order (review H5): centre crop by ``preset.zoom`` -> ``preset.denoise`` -> CLAHE on the Lab L channel
    -> bicubic upscale back to the input size -> unsharp mask -> ``preset.display`` mode. ``zoom == 1.0`` skips the
    crop and the upscale; ``sharpen_amount == 0`` skips the unsharp mask.

    Args:
        image: BGR ``uint8`` array, shape ``(H, W, 3)``, ``H, W >= 8``. Never modified.
        preset: a ``Preset`` or a preset name (``"cataract"``, ``"amd"``).

    Returns:
        A new BGR ``uint8`` array with exactly ``image.shape``. Deterministic for a given input and preset.

    Raises:
        ValueError: ``image`` is not an ``ndarray``, not ``uint8``, not 3-D, not 3-channel, or smaller than 8 px on a
            side.
        KeyError: ``preset`` is an unknown preset name.
        TypeError: ``preset`` is neither a ``Preset`` nor a ``str``.
    """
    # Reject malformed input before any work.
    _validate_image(image)
    # Resolve a name to its Preset (KeyError for unknown names).
    p = _resolve_preset(preset)
    # Input height and width in pixels; the output has exactly this size.
    in_h, in_w = image.shape[:2]
    # Work on a private contiguous copy so no step (or a strided view) can ever touch the caller's array.
    img = np.ascontiguousarray(image).copy()

    # 1. Crop the centre 1/zoom of each side (skipped at zoom 1.0).
    img = _crop_center(img, p.zoom)
    # 2. Denoise the (smaller) crop - cheaper than denoising the full frame.
    img = _denoise(img, p.denoise)
    # 3. Local contrast enhancement on lightness only.
    img = _clahe_lab_l(img, p.clahe_clip, p.clahe_tile)
    # 4. Bicubic upscale back to the input size (skipped at zoom 1.0, where the size is already the input size).
    if p.zoom != 1.0:
        img = _upscale_to(img, in_h, in_w)
    # 5. Unsharp mask after the upscale, so it sharpens the edges the interpolation softened (skipped at amount 0).
    img = _unsharp_mask(img, p.sharpen_amount)

    # 6. Display mode.
    if p.display == "binary_dark":
        # Yellow-on-black binarised text.
        img = _display_binary_dark(img)
    elif p.display == "color_precomp":
        # Blue-gain colour pre-compensation of the plain result.
        img = _display_color_precomp(img, p.blue_gain)
    # "plain": the BGR result of steps 1-5 as is.

    # Defensive guarantee of the contract (shape and dtype); a failure here is a pipeline bug, not a user error.
    assert img.shape == image.shape and img.dtype == np.uint8, (img.shape, img.dtype)
    # A new array in every path: img was built from a copy, so it never aliases the caller's image.
    return img
