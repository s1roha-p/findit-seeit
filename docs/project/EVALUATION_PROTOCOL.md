# Evaluation protocol

The single source of truth for evidence tiers, data splits, metrics and result records. `CLAUDE.md` section 6 and the
advisors point here; do not copy a second set of rules elsewhere.

## 1. Evidence tiers

| Tier | Meaning | Allowed wording |
|---|---|---|
| **E0** | It runs: one example, by eye | "works on an example" |
| **E1** | Measured on the **dev** set, parameters may still be tuned, one run | "on our dev photos, ..." (progress notes only) |
| **E2** | Measured once on the **test** set with parameters frozen before the test set was opened; a baseline measured the same way; repeated where the result is stochastic | numbers on slides and in the report |

A number on a slide or in the report must be E2 and cite its record id. Missing values are `null` with a reason, never
0.

## 2. Data and splits

- Photos and recordings are split **by session** (one room, one day, one person = one session), not by file, so near
  duplicates never sit on both sides. Dev ≈ 60 %, test ≈ 40 % of sessions.
- The split is written once into `data/manifests/split.csv` (file, session, split, sha256) and not changed after the
  first E2 run; a later change creates `split_v2.csv` and new records.
- Tuning (presets, thresholds, prompts) uses dev only. The test set is opened once per frozen configuration.
- Consent and redaction rules: [`DATA_POLICY.md`](DATA_POLICY.md).

## 3. Metrics

**Mode 2 (Part C, harness by D)**
- Text set: drug bags, appointment slips, menus, price tags; personal fields covered; 3 font-size bands (small,
  medium, large) labelled in the manifest; ground-truth text typed once per photo.
- Conditions: `cataract` and `amd` simulation (`eval/simulate.py`, versioned parameters fixed before tuning).
- Arms per photo: original; simulate(original); simulate(enhance(original, preset)).
- Metric: **character error rate (CER)** from one named OCR engine and language setting, per arm, per size band;
  report median and the share of photos where enhancement lowers CER. OCR is a proxy for legibility, not for a human
  eye - say so on the slide.
- Human check: a legibility test (6-10 readers, smallest correctly read line through the simulation, with and without
  enhancement, order alternated between readers).
- Speed: frames per second of `enhance` at 1280x720 on the demo machine (median of 300 frames after 30 warm-up frames).

**Mode 1 (Parts A and B)**
- Detection recall and precision per item on test snapshots (IoU ≥ 0.5 counts as found), with the detector name,
  model file and score threshold.
- Last-seen accuracy: share of scripted queries whose answered location matches the ground truth.
- ASR: CER on recorded questions (Mandarin; Taigi separately if attempted), model name and size recorded.
- Intent accuracy: share of transcripts mapped to the right item (from the true transcript and from the ASR output).
- Latency: end of question → start of spoken answer, median and p90 over ≥ 20 queries, with the share of each stage
  (ASR, lookup, VLM, TTS) and whether the VLM was cloud or local.

## 4. Result records

One JSON file per run under `work/results/`, named `<UTC stamp>_<part>_<slug>.json`, never overwritten (a correction
is a new record that cites the old one). Fields:

```json
{
  "id": "20261205T101500Z_C_mode2-ocr-cataract",
  "part": "C",
  "tier": "E2",
  "git_commit": "<sha of the code that ran>",
  "machine": "<os, cpu, gpu or none>",
  "environment": "conda findsee | .venv, python <version>, key package versions",
  "dataset": {"manifest": "data/manifests/split.csv", "manifest_sha256": "...", "split": "test", "n": 48},
  "config": {"preset": "cataract", "simulate_version": "v1", "ocr_engine": "<name and language>"},
  "metrics": {"cer_original_sim": 0.41, "cer_enhanced_sim": 0.22, "improved_share": 0.83},
  "runs": 1,
  "limitations": "OCR proxy; simulated degradation only; 48 photos from 6 sessions",
  "command": "python eval/eval_mode2_ocr.py --split test --preset cataract"
}
```

(The numbers above are placeholders showing the format, not results.)

## 5. What an evaluation run must not do

- Tune on the test set, or re-run the test set until a number looks good (every run is kept and listed).
- Mix simulation versions, OCR engines or splits in one comparison.
- Quote the best of several runs; report all runs or their median.
- Use personal data without the consent recorded in the manifest.
