# Architecture and interfaces (planned)

**Status: a plan, written 2026-11-20 before any code exists.** It fixes the module layout and the function contracts
between the four parts of [`WORK_SPLIT.md`](WORK_SPLIT.md) so they can be built in parallel. Verify a path or symbol in
the source before relying on it; when the code and this file disagree, follow the code and correct this file
(`CLAUDE.md` rule 5.13).

## Data flow

```
Mode 1 (find)                                                   Mode 2 (see)
camera ──► capture (A) ──► detect (A) ──► MemoryStore (A)       camera / photo ──► enhance(image, preset) (C)
                                              │                                         │
mic ──► asr (B) ──► intent (B) ──► last_seen(item) (A)                                  ▼
                                              │                                   display (D)
                                              ▼                                         ▲
                              describe_location (B, VLM, one call)                      │
                                              │                 "放大看" handoff (D): crop of the sighting box
                                              ▼                                         │
                                 tts (B) ──► speaker; boxed photo ──► app (D) ─────────┘
```

## Package layout

```
src/findsee/
  __init__.py
  config.py            # paths (data/, models/, .cache/), item list, presets file; reads env var NAMES only
  types.py             # the dataclasses below (shared by every part)
  mode1/               # Part A
    capture.py         # take_snapshot()
    detect.py          # Detector.detect()
    memory.py          # MemoryStore
  voice/               # Part B
    asr.py             # transcribe()
    intent.py          # parse_query()
    describe.py        # describe_location()  (VLM)
    tts.py             # speak()
  mode2/               # Part C
    pipeline.py        # enhance()
    presets.py         # Preset, PRESETS
  app/                 # Part D
    main.py            # Gradio / Streamlit entry point
eval/                  # Part D (harness) + each part's evaluation script
  simulate.py          # cataract / AMD simulation filters (versioned parameters)
  ocr.py               # one named OCR engine
  records.py           # result record writer (work/results/)
  eval_mode1_detect.py, eval_voice.py, eval_mode2_ocr.py
tests/                 # pytest; fixtures are small, consented, committed images/audio under tests/fixtures/
```

## Shared types (`src/findsee/types.py`)

| Type | Fields | Notes |
|---|---|---|
| `Snapshot` | `path: Path`, `taken_at: datetime` (UTC), `location: str` (e.g. "客廳"), `camera_id: str` | image file under `data/runtime/snapshots/` (git-ignored) |
| `Detection` | `label: str`, `score: float` (0-1), `box: tuple[int, int, int, int]` (x1, y1, x2, y2, pixels) | label from the item list in `config.py` |
| `Sighting` | `snapshot: Snapshot`, `detection: Detection` | what `last_seen` returns |
| `Transcript` | `text: str`, `language: str` ("zh"), `audio_seconds: float`, `asr_seconds: float` | |
| `Query` | `item: str \| None`, `raw_text: str` | `item` is None when no known item was named |
| `Preset` | `name: str`, `zoom: float`, `denoise: str`, `clahe_clip: float`, `clahe_tile: int`, `sharpen_amount: float`, `display: str` ("binary_dark" \| "color_precomp" \| "plain"), `blue_gain: float` | stored in `src/findsee/mode2/presets.py` |

## Function contracts

| Part | Function | Input → output | Rules |
|---|---|---|---|
| A | `take_snapshot(camera_id, location) -> Snapshot` | camera → saved JPEG | never overwrites; filename `<UTC stamp>_<camera>.jpg` |
| A | `Detector(items).detect(image) -> list[Detection]` | BGR `uint8` HxWx3 → detections | the item list is text (open-vocabulary); score threshold in `config.py` |
| A | `MemoryStore.record(snapshot, detections)`; `.last_seen(item) -> Sighting \| None`; `.prune(older_than)` | | newest sighting wins; retention per `DATA_POLICY.md` |
| B | `transcribe(audio_path, language="zh") -> Transcript` | 16 kHz mono WAV → text | model name and size recorded with every result |
| B | `parse_query(text) -> Query` | text → item | synonyms table in `voice/intent.py` |
| B | `describe_location(sighting) -> str` | one image + one box → short zh-TW sentence | one VLM call per question; only the crop/annotated image is sent (review H4) |
| B | `speak(text, out_path) -> Path` | text → audio file | zh-TW voice; rate slower than default |
| C | `enhance(image, preset) -> image` | BGR `uint8` HxWx3 → BGR `uint8` (display size) | pure function, no I/O; deterministic for a given input and preset |
| D | `app.main` | wires the above; Mode 1 → Mode 2 handoff passes `sighting` crop + the user's preset | |

## Evaluation contracts

- `eval/simulate.py`: `simulate(image, condition, params_version) -> image`; parameters live in a versioned table in the
  same file; a record names the version.
- `eval/ocr.py`: `read_text(image) -> str` with one fixed engine and language setting, named in each record.
- `eval/records.py`: `write_record(dict) -> Path` under `work/results/`, refusing to overwrite (records are immutable).
