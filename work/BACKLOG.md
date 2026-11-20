# Backlog — open items, decisions and their evidence

One row per item; refresh the status cell in place (status, tier, record ids) rather than appending. Sources:
`docs/project/PROPOSAL_REVIEW.md` (review ids H1-H5, M1-M5, L1-L3; decisions D1-D6) and `docs/project/WORK_SPLIT.md`.
Status: OPEN · DOING · DONE · DROPPED (with the reason).

## Decisions (the team decides; record the answer and the date)

| ID | Decision | Recommended default | Part | Status / answer |
|---|---|---|---|---|
| D1 | Mode 1 detector: open-vocabulary (YOLO-World / YOLOE) · fine-tuned YOLO · VLM only | open-vocabulary first, test on own photos | A | OPEN |
| D2 | VLM: cloud API · local small VLM; what is uploaded | cloud, crop-only, query-only, named on the slide | B | OPEN |
| D3 | ASR language: Mandarin (Whisper) · Taigi (Breeze-ASR-26) | Mandarin; Taigi stretch | B | OPEN |
| D4 | Demo platform and cameras | fixed USB/phone camera for Mode 1; phone photos or stream for Mode 2 | D | OPEN |
| D5 | TTS engine | online zh-TW neural voice + offline fallback | B | OPEN |
| D6 | UI framework | Gradio or Streamlit | D | OPEN |
| D7 | Part owners | members choose A-D | all | OPEN |
| D8 | Final presentation date and demo freeze | 12/17 presentation, 12/14 freeze (confirm) | all | OPEN |

## Work items

| ID | Item | Review | Part | Status |
|---|---|---|---|---|
| B-01 | Test open-vocabulary detection on 20+ own photos of the target items; recall per item (E1) | H1 | A | OPEN |
| B-02 | Fallback plan if B-01 recall is poor: label ~100 photos per weak item and fine-tune, or VLM search | H1 | A | OPEN |
| B-03 | Memory store with `last_seen` and retention; snapshot cadence decided | H2, L3 | A | OPEN |
| B-04 | Record 30+ Mandarin test questions (slow speech, TV noise); ASR CER (E1) | H3 | B | OPEN |
| B-05 | Intent synonyms table and unknown-item answer | H2 | B | OPEN |
| B-06 | VLM location prompt (one call per question, zh-TW, short); privacy rule written on the slide | H2, H4 | B | OPEN |
| B-07 | Latency budget measured end to end (median, p90, stage shares) | H4 | B, D | OPEN |
| B-08 | Mode 2 pipeline in the reviewed order; `enhance(image, preset)` with `cataract` and `amd` presets | H5 | C | OPEN |
| B-09 | Denoiser comparison on small characters (median / bilateral / NLM) by CER | H5 | C | OPEN |
| B-10 | Live Mode 2 on a camera stream; fps at 720p | M2 | C | OPEN |
| B-11 | Simulation filters (cataract, AMD) with versioned parameters; OCR runner; record writer | M1 | D | OPEN |
| B-12 | Data collection with consent and redaction; manifests; session split written once | M1, M5 | D | OPEN |
| B-13 | App shell with both modes and the "放大看" handoff | M3 | D | OPEN |
| B-14 | Legibility test (6-10 readers) | M1 | D | OPEN |
| B-15 | USR stakeholder and observed outcome; benefit slide rewritten | L1, L2 | D | OPEN |
| B-16 | Fix deck wording (抗躁性 → 抗噪性, 模型介紹 → 系統設計, VLM+TTS wording) | L2 | D | OPEN |
| B-17 | Medication disclaimer in the app wherever OCR text is shown | M5 | C, D | OPEN |
| B-18 | Taigi questions with Breeze-ASR-26 (stretch, needs a GPU) | H3 | B | OPEN |

## Research commissions (proposed; the user commissions each pass)

| ID | Advisor | Form | Question or scope | Status |
|---|---|---|---|---|
| V-1 | Claude Mythos | Vulnerability review | The guard's R6 (git asks): can it let through a line that a non-git rule should refuse; are `.git/` confirmations clear (`RESEARCH_ADVISOR.md` section 7) | proposed |
| R-1 | Claude Mythos | Adversarial review | Part C's `enhance()` / presets and Part D's simulation and OCR harness, before the first E2 run | proposed, after B-08 and B-11 |
| T-1 | Codex Astra | Statistical design | What the test set, readers and queries can distinguish; paired decision rules; how much data to collect (`RESEARCH_ADVISOR_CODEX.md` section 7) | proposed, before B-12's collection |
| T-2 | Codex Astra | Knowledge synthesis | Low-vision literature on pre-compensation for cataract and AMD, as hypotheses for the presets | proposed |
