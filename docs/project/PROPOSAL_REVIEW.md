# Proposal review — 幫長輩找得到也看得清 (FindSee)

- **Reviewed:** the team's Canva deck 「多媒體報告」 (14 pages, midterm version, last edited 2026-11-11), on 2026-11-20.
- **Reviewer:** Claude (Opus 5.5), for the team. Facts about third-party models were checked on 2026-11-20 (sources at
  the end); everything else is a reading of the deck.
- **Use:** each issue has an owner part from [`WORK_SPLIT.md`](WORK_SPLIT.md) and, where it needs work, a backlog row
  in [`work/BACKLOG.md`](../../work/BACKLOG.md). Decisions the team must take are in section 4.

## 繁中摘要（給組員）

1. **題目很好，模式二最成熟。** 兩個問題串成一個流程（找得到 → 看得清），模式二「影像沒問題、退化在眼睛 → 對影像預補償」的
   觀念清楚，每一步都對應一個症狀，而且就是課程的影像處理內容。
2. **模式一最大的風險：YOLO 預訓練模型認不得我們要找的東西。** COCO 80 類只有遙控器、手機、杯子、書、瓶子等，**沒有老花
   眼鏡、藥袋、鑰匙、錢包**。三條路：改用開放詞彙偵測（YOLO-World／YOLOE，用文字指定類別，Ultralytics 直接支援）、
   自己拍照標註後微調，或讓 VLM 負責這幾樣東西。建議第一條，第一週就要用實際照片測。
3. **模式一的資料流還沒定義。** YOLO 和 VLM 各做什麼、快照多久拍一次、存在哪、怎麼回答「最後一次在哪裡看到」，都要寫成
   介面（見 `ARCHITECTURE.md`）。
4. **「Whisper 對台語有很好的相容性」要改。** Whisper 的官方語言沒有台語；台語要用專門微調的模型（例如 2026 年 9 月開源的
   Breeze-ASR-26，約 2B 參數，需要 GPU）。Demo 建議先用華語，台語列為加分項。投影片的「抗躁性」應為「抗噪性」。
5. **隱私說法和 VLM 衝突。** 如果 VLM 用雲端 API，家中照片會上傳；要嘛用本地模型，要嘛只在長輩提問時上傳裁切後的
   單張圖片，並在簡報裡說清楚。
6. **模式二流程順序建議調整：** 先裁切（數位放大其實是裁切＋放大）→ 降噪 → CLAHE → 放大 → 銳化 → 最後二選一的顯示模式
   （高對比二值化或色彩預補償）。中值濾波會吃掉細筆畫，建議跟雙邊濾波／NLM 比較。
7. **評估規則要先定再量：** 調參圖和測試圖分開、模擬濾鏡參數先固定、OCR 用字元錯誤率（CER）；加一個小型可讀性測試。
8. **目前分工不平均：** 模式二被拆成兩小塊，沒有人負責整合、評估、資料和 demo。建議改成 `WORK_SPLIT.md` 的四等份。
9. **用藥安全：** 系統只「讓字看得清」，不要宣稱自動判讀劑量；若加入 OCR 朗讀，要標示「僅供參考，以藥師說明為準」。

## 1. What the proposal says

Two everyday problems of an elder at home - **not finding things** (reading glasses, drug bags, the remote) and **not
being able to read them once found** (cataract haze, low contrast, yellowed lens; AMD central scotoma) - answered by
one dual-mode system:

- **Mode 1, "find things" (外接視覺記憶):** periodic snapshots of the places items usually are (not 24-hour video, for
  load and privacy); the elder asks by voice; Whisper transcribes; YOLO detects frequent items; a VLM reasons about
  the relative position; TTS speaks the answer; the photo with the item boxed is shown.
- **Mode 2, "see clearly" (智慧放大鏡):** phone camera on text; digital zoom; per-condition presets that
  pre-compensate the image: bicubic zoom, Gaussian/median denoise, CLAHE, unsharp mask, adaptive threshold
  (dark mode), blue-channel gain. Evaluated with simulated cataract/AMD filters before and after, and OCR accuracy.
- USR link: less memory anxiety and family friction; a smaller digital divide (speak instead of type).

## 2. Strengths

- **A real, specific problem with a believable scene** (the living room, the drug bag, the appointment slip), and an
  answer to "why not a tracker?" already in the deck.
- **Mode 2's framing is correct and teachable:** the image is fine, the loss is in the eye, so the image is
  pre-compensated; every stage names the symptom it answers and how. This maps directly onto the course's image
  enhancement material.
- **Privacy-aware capture** (periodic snapshots in known places, not continuous video) is a good default and a
  natural talking point for judges.
- **An evaluation idea exists** for Mode 2 (simulated degradation before/after plus OCR), which most student projects
  lack.
- **The two modes connect** ("right after Mode 1 finds an item, magnify it"), which gives the demo a story.

## 3. Issues and recommended changes

Ranked by how much they can hurt the final demo or grade. *Owner* is the part in `WORK_SPLIT.md`.

### High

**H1. The detector cannot see most target items.** *Owner: A.* The deck's YOLO is presumably a COCO-pretrained
model. COCO's 80 classes include `remote`, `cell phone`, `cup`, `bottle`, `book`, `scissors`, `handbag`, but **not
eyeglasses, keys, wallets or medicine bags**, the items the deck's problem slide names. *Fix:* use an open-vocabulary
detector - Ultralytics ships YOLO-World and YOLOE, both of which take the class list as text at inference time
(`set_classes([...])`) - and test it on the team's own photos in week 1; keep fine-tuning a small YOLO on ~100
labelled photos per item as the fallback; let the VLM handle what neither finds. Report detection recall per item
on a held-out photo set (`EVALUATION_PROTOCOL.md`).

**H2. Mode 1's data flow is not defined.** *Owner: A (store), B (query), D (integration).* The deck lists four models
but not who does what: does YOLO find the item and the VLM describe where it is, or does the VLM search? When is a
snapshot taken, where is it kept, and how is "where did I last see it" answered when the item is not in the newest
snapshot? *Fix:* a "last-seen" memory: each snapshot is stored with its timestamp, camera/location name and
detections; a query returns the newest sighting of the asked item; the VLM is called **once, on that one image and
box**, to phrase the location ("on the coffee table, left of the TV"); TTS speaks it. Write this as the interfaces in
[`ARCHITECTURE.md`](ARCHITECTURE.md) before coding.

**H3. "Whisper handles Taiwanese well" is not supportable as written.** *Owner: B.* Whisper's published language
list has no Taiwanese Hokkien (Taigi); fine-tuned derivatives exist - MediaTek Research and NYCU's Breeze-ASR-26, a
Whisper-large-v2 derivative for Taigi open-sourced in September 2026 (about 2B parameters, GPU) - but they are a
separate model with their own error rates. *Fix:* demo in Mandarin with Whisper (or faster-whisper); list Taigi as a
stretch goal with Breeze-ASR-26; measure CER on the team's own recorded questions; change the slide text
("抗躁性" → "抗噪性" as well).

**H4. Privacy claim vs a cloud VLM, and no latency budget.** *Owner: B (decision), D (measurement).* If the VLM is a
cloud API, home photos leave the house - which contradicts the privacy slide unless it is designed for. A local VLM
on a laptop may be too slow. *Fix:* decide (section 4, D2). With a cloud API: send only the single cropped image of
the answer, only when the elder asks, and say so on the slide; never upload the periodic snapshots. Set a latency
target (for example, under 5 s from the end of the question to the start of the spoken answer) and measure median and
90th percentile.

**H5. Mode 2's pipeline order and filters need adjusting.** *Owner: C.* Upscaling first and denoising after enlarges
the noise and multiplies the work; a median filter removes thin strokes of small Chinese characters; adaptive
thresholding and color pre-compensation are mutually exclusive displays, not two consecutive steps. *Fix:* crop the
region of interest (digital zoom = crop) → denoise at native resolution (compare median, bilateral and
`fastNlMeansDenoising` on text) → CLAHE (on the L channel of Lab, so color is kept) → bicubic upscale to the display
size → unsharp mask → **one** display mode per preset: high-contrast binarized (yellow on black) **or** color
pre-compensation (blue gain with clipping control). Measure frame rate on the demo machine.

### Medium

**M1. The evaluation needs fixed rules before measuring.** *Owner: D (harness), C and A (their metrics).* Simulated
filters are a good proxy only if their parameters are fixed before tuning, and the photos used to tune the presets are
not the photos used to report. *Fix:* [`EVALUATION_PROTOCOL.md`](EVALUATION_PROTOCOL.md) - dev/test split by photo
session, versioned simulation parameters, one named OCR engine, CER on original / simulated-original /
simulated-enhanced, plus a small legibility test (smallest readable font size through the simulation, team and
classmates).

**M2. "Phone camera, live video" vs "Python + OpenCV".** *Owner: C (Mode 2), D (app).* OpenCV in Python runs on the
laptop, not on the phone. *Fix:* decide the demo platform (section 4, D4): the phone as an IP camera streaming to the
laptop, a USB webcam, or still photos taken on the phone and processed on the laptop. Say which on the slide.

**M3. The Mode 1 → Mode 2 handoff is a sentence, not a feature.** *Owner: D.* *Fix:* after a Mode 1 answer, offer
"放大看" which opens Mode 2 on the found item's crop with the user's preset.

**M4. The current split is uneven and leaves gaps.** *Owner: all.* The deck's split gives Mode 1 two heavy parts
(YOLO + snapshots; Whisper + VLM + TTS) and splits Mode 2 into two small parts (CLAHE; unsharp mask + color), while
nobody owns integration, the evaluation harness, test data, the demo or the final slides. *Fix:* the four parts in
[`WORK_SPLIT.md`](WORK_SPLIT.md) (unassigned until the team confirms).

**M5. Medication safety and personal data.** *Owner: D (policy), C (UI text).* A magnifier that makes a dosage
legible is helpful; one that reads a dosage aloud can be wrong. Drug bags and appointment slips carry names and ID
numbers. *Fix:* Mode 2 enhances images only; any OCR read-out is labelled "僅供參考，以藥師說明為準"; test photos are
taken with consent and personal fields covered ([`DATA_POLICY.md`](DATA_POLICY.md)).

### Low

**L1. The USR link needs a stakeholder and an outcome.** Name a concrete partner or setting (a community care
station, a team member's grandparent who agrees to try it) and one thing that will be observed (for example, time to
find three items with and without the system; the smallest drug-bag text read correctly with and without Mode 2).

**L2. Wording on the slides.** 「抗躁性」→「抗噪性」; 「模型介紹」→「系統設計」 (Mode 2 is a pipeline, not a model);
「VLM+TTS 雙模態模型」 describes two separate models (the VLM is the multimodal one); the expected-benefit slide should
state what the demo will measure (L1) rather than general benefits.

**L3. Name the snapshot cadence and storage.** "定期快照" needs a number (for example, one frame every 5 minutes per
camera, only while motion is detected) and a retention rule (for example, keep the last 24 hours), both of which also
answer the privacy question.

## 4. Decisions for the team (with a recommended default)

| ID | Decision | Options | Recommended default | Decide by |
|---|---|---|---|---|
| D1 | Mode 1 detector | open-vocabulary (YOLO-World / YOLOE) · fine-tuned YOLO · VLM only | open-vocabulary first, fine-tune as fallback | week 1, after testing on own photos |
| D2 | VLM placement | cloud API · local small VLM | cloud API for the demo, crop-only and query-only upload, named on the slide | week 1 |
| D3 | ASR language | Mandarin (Whisper / faster-whisper) · Taigi (Breeze-ASR-26) | Mandarin; Taigi as stretch if a GPU is available | week 1 |
| D4 | Demo platform | phone as IP camera → laptop · USB webcam · still photos | one fixed USB/phone camera for Mode 1; phone photos or stream for Mode 2 | week 1 |
| D5 | TTS | online neural voice · offline engine | online neural zh-TW voice, offline engine as fallback | week 2 |
| D6 | UI | Gradio · Streamlit · desktop window | Gradio or Streamlit (fastest for a demo) | week 1 |

## 5. Scope for the final demo

- **Must:** Mode 1 end to end on one fixed scene (ask by voice → spoken answer + boxed photo) for at least three items;
  Mode 2 with two presets (cataract, AMD) on drug bag / slip / menu photos; the Mode 1 → Mode 2 handoff; measured
  numbers from `EVALUATION_PROTOCOL.md` on the slides.
- **Should:** live Mode 2 on a camera stream; latency under the target; a five-minute legibility test with simulated
  degradation.
- **Could:** Taigi questions; motion-triggered snapshots; a field try with one elder (with consent).

## 6. Changes for the final deck (brief)

1. Problem slides: keep; add the snapshot cadence/retention (L3) and the privacy design (H4).
2. Mode 1: replace the model list with the data-flow figure from `ARCHITECTURE.md`; state the detector decision (H1)
   and the language decision (H3).
3. Mode 2: reorder the pipeline (H5); show one before/after per preset with the simulated view.
4. Evaluation: one slide of measured numbers (CER, recall, latency) with dataset sizes.
5. Team: the four parts with owners; USR slide with the stakeholder and outcome (L1).

## Sources

- Ultralytics YOLO-World and YOLOE documentation (open-vocabulary detection, `set_classes`): docs.ultralytics.com,
  read 2026-11-20.
- Breeze-ASR-26 / BreezeASR-Taigi (Whisper derivative for Taiwanese Hokkien, about 2B parameters; open-sourced by
  NYCU and MediaTek, September 2026) and the Breeze Taigi paper (arXiv 2603.19259): read 2026-11-20.
- COCO's 80 class names: the standard COCO detection label set (no eyeglasses, keys, wallets or medicine bags).
