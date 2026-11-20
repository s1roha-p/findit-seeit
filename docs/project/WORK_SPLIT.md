# Work split — four parts (owners not yet assigned)

The team has not confirmed who does what, so the work is divided into four parts of similar size; each member takes
one part and fills in the owner column. Each part owns code, an evaluation, a demo segment and its slides, so every
member presents something they built. Interfaces between parts are fixed in [`ARCHITECTURE.md`](ARCHITECTURE.md);
change an interface only by agreement of the parts it connects (and a line in `PROGRESS.md`).

| Part | Name | Owner | Code | Evaluation it reports |
|---|---|---|---|---|
| **A** | Mode 1 vision and memory · 尋物視覺與記憶 | *TBD* | `src/findsee/mode1/` | detection recall per item; last-seen accuracy |
| **B** | Voice and reasoning · 語音互動與推理 | *TBD* | `src/findsee/voice/` | ASR CER; location-answer correctness; latency |
| **C** | Mode 2 low-vision enhancement · 低視能影像增強 | *TBD* | `src/findsee/mode2/` | OCR CER through simulated degradation; frame rate |
| **D** | Integration, evaluation and deliverables · 整合、評估與成果 | *TBD* | `src/findsee/app/`, `eval/` | harness and records; legibility test; end-to-end demo |

How the deck's earlier split maps here: "YOLO + desk snapshots" → A; "Whisper + location description + TTS" → B;
"histogram equalization / CLAHE" and "unsharp mask + cataract color correction" → C (one part, the whole pipeline);
"test images" → D (data collection and the harness), which also takes integration, the demo and the final deck.

## Part A — Mode 1 vision and memory

**Goal:** given periodic snapshots of a room, know where each target item was last seen.

- Capture: snapshot from a fixed camera (USB webcam or phone as IP camera), on a timer; optional motion trigger.
- Detection: open-vocabulary detector (YOLO-World / YOLOE) with the target list (老花眼鏡, 藥袋, 遙控器, 鑰匙, 錢包,
  手機, 杯子); week-1 test on own photos; fallback plan (fine-tune or VLM) if recall is poor (review H1).
- Memory store: every snapshot with timestamp, location name and detections (SQLite or JSON lines); `last_seen(item)`;
  retention rule (review L3).
- Output for B and D: the sighting (image path, box, time, location) and an annotated image with the box drawn.

**Deliverables:** `src/findsee/mode1/` (capture, detect, memory), tests with fixed images, `eval/eval_mode1_detect.py`
records (recall per item on the test photos), a 2-minute demo segment and 2 slides.

**Done when:** E1 recall per item on the dev photos is recorded; `last_seen` answers correctly for the scripted demo
scene; snapshots older than the retention limit are removed by the store.

## Part B — Voice and reasoning

**Goal:** turn a spoken question into a spoken answer about where the item is.

- ASR: Whisper / faster-whisper in Mandarin (review H3); measure CER on 30+ recorded questions spoken slowly, with
  background TV noise; Taigi (Breeze-ASR-26) only as a stretch goal.
- Intent: map the transcript to an item name, with synonyms (眼鏡/老花眼鏡, 藥/藥袋/藥包, 遙控/遙控器) and "I can't
  find ..." phrasings; unknown items get a polite fallback answer.
- Location description: one VLM call on the sighting image and box (review H2) with a fixed prompt that asks for a
  relative position in short Traditional Chinese ("在客廳茶几上，電視遙控器左邊"); record the decision on cloud vs
  local and the privacy rule (review H4).
- TTS: zh-TW voice; slow, clear speech; a fallback engine.
- Latency: measure end of question → start of speech (median, p90) and the share of each stage.

**Deliverables:** `src/findsee/voice/` (asr, intent, describe, tts), tests with recorded audio fixtures,
`eval/eval_voice.py` records (CER, intent accuracy, latency), the VLM prompt in the repository, a 2-minute demo segment
and 2 slides.

**Done when:** E1 CER and latency are recorded; the scripted demo questions are answered correctly three times in a
row.

## Part C — Mode 2 low-vision enhancement

**Goal:** make small print legible for cataract and AMD through image pre-compensation.

- The pipeline in the reviewed order (review H5): crop → denoise → CLAHE (Lab L channel) → bicubic upscale → unsharp
  mask → display mode (high-contrast binarized yellow-on-black, or blue-gain color pre-compensation).
- Presets: `cataract`, `amd`, plus manual sliders (zoom, contrast, sharpen) for the demo.
- Live path: camera stream at a usable frame rate on the demo machine (measure fps at 720p).
- Filter choice evidence: median vs bilateral vs NLM on small-character photos (CER and a visual sample).

**Deliverables:** `src/findsee/mode2/` (`enhance(image, preset)` and the presets), tests (shape, dtype, range,
idempotent presets), results from D's harness for each preset, a 2-minute demo segment and 2 slides (before /
simulated / enhanced-simulated).

**Done when:** E2 numbers for both presets on the test photos exist (from D's harness) and the live path runs at the
measured fps.

## Part D — Integration, evaluation and deliverables

**Goal:** one working app, honest numbers, and the final presentation.

- App: Gradio or Streamlit shell with Mode 1 (record or type a question, show the boxed photo, play the answer) and
  Mode 2 (upload or stream, choose a preset), and the handoff button "放大看" (review M3).
- Evaluation harness (`eval/`): the simulation filters (cataract: blur, contrast loss, yellowing, glare veil; AMD:
  central scotoma) with versioned parameters; the OCR runner (one named engine); the record writer; the dev/test
  split rules ([`EVALUATION_PROTOCOL.md`](EVALUATION_PROTOCOL.md)).
- Data: the photo and audio collection plan with consent and redaction ([`DATA_POLICY.md`](DATA_POLICY.md)); the
  manifests (`data/manifests/*.csv` with sha256).
- Legibility test: 6-10 people read lines of decreasing size through the simulation, with and without Mode 2.
- Deliverables: demo script and a recorded backup video, the final deck (assembling every part's slides), the
  USR slide (review L1), the written report if the course asks for one.

**Deliverables:** `src/findsee/app/`, `eval/` (simulate, ocr, records), the manifests, the demo video, the final
deck.

**Done when:** the full demo runs from a clean clone with the documented commands; every number on the slides cites a
record in `work/results/`.

## Shared rules

- **Branches:** `part-a/<topic>`, `part-b/<topic>`, `part-c/<topic>`, `part-d/<topic>`; merge to `main` by pull request
  reviewed by one other member. Agents may create branches; pushes, merges and other publishing git commands ask the
  owner first (`docs/project/HOOKS.md`, R6).
- **Interfaces first:** each part writes its functions' signatures and a stub that returns a fixed example in week 1,
  so D can integrate early and the others can test against stubs.
- **Every part writes its own slides and records its own demo clip;** D assembles and keeps one visual style.
- **Weekly check-in:** each owner adds a `PROGRESS.md` entry (what works, numbers with record ids, blockers).

## Timeline (to the 12/17 presentation; confirm the date)

| Week | Dates | A | B | C | D |
|---|---|---|---|---|---|
| 1 | 11/21-11/27 | detector test on own photos (D1); capture stub | ASR test on own recordings (D3); stubs | pipeline v1, presets drafted | repo + env (D6); data plan; harness skeleton; stubs integrated |
| 2 | 11/28-12/04 | memory store; `last_seen`; recall E1 | intent + VLM prompt (D2) + TTS (D5); latency E1 | filter comparison; live path; fps | simulation filters + OCR runner; test photos collected |
| 3 | 12/05-12/11 | integrated in app; E2 recall | integrated; E2 CER, latency | E2 OCR for both presets | handoff; legibility test; draft deck |
| 4 | 12/12-12/17 | fixes | fixes | fixes | freeze 12/14; rehearsals; backup video; final deck |
