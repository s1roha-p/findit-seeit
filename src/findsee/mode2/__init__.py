"""Mode 2 - smart magnifier (Part C): low-vision image pre-compensation for cataract and AMD.

Public interface (``work/claude-main/C-20261122T1606Z-claude-0984/LANES.md`` section 1):

- ``enhance(image, preset) -> np.ndarray``: BGR ``uint8`` (H, W, 3) in, BGR ``uint8`` of the same shape out.
- ``PRESETS``: the named draft presets (``"cataract"``, ``"amd"``).
- ``get_preset(name)``: preset lookup; unknown names raise ``KeyError``.
- ``make_custom(base, *, zoom=None, clahe_clip=None, sharpen_amount=None, display=None, name="custom")``: a new,
  unregistered preset for the demo's sliders (round 2, LANES.md section 2R).

The live camera path is ``findsee.mode2.live`` (``FpsMeter``, ``draw_status``, ``open_camera``, ``run_live``). It is
deliberately NOT imported here, so importing this package never needs a camera, a display or a GUI backend; import
``findsee.mode2.live`` explicitly where the live loop is wanted.

Importing this package imports ``numpy`` and ``cv2`` (through ``pipeline``); it performs no I/O.
"""

from __future__ import annotations

from findsee.mode2.pipeline import enhance  # the enhancement pipeline
from findsee.mode2.presets import PRESETS, get_preset, make_custom  # preset table, lookup, slider presets

# Names exported by ``from findsee.mode2 import *``.
__all__ = ["PRESETS", "enhance", "get_preset", "make_custom"]
