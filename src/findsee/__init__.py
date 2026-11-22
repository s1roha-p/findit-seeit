"""FindSee - a dual-mode home assistant for elders (multimedia final project).

Sub-packages (ownership per docs/project/WORK_SPLIT.md and interfaces per docs/project/ARCHITECTURE.md):

- ``findsee.mode1`` (Part A): snapshots, open-vocabulary detection, last-seen memory.
- ``findsee.voice`` (Part B): ASR, intent parsing, VLM phrasing, TTS.
- ``findsee.mode2`` (Part C): low-vision image enhancement (``enhance(image, preset)``).
- ``findsee.app`` (Part D): the demo application wiring the parts together.
- ``findsee.types``: dataclasses shared across parts.

This top-level module intentionally imports nothing, so ``import findsee`` has no side effects and does not pull
in heavy optional dependencies (OpenCV, model libraries) until a sub-package is imported explicitly.
"""

# Nothing is re-exported at the top level; import from the sub-packages directly (e.g. ``findsee.mode2``).
__all__: list[str] = []
