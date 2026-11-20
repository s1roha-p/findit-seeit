# eval/ — evaluation harness

Rules: `docs/project/EVALUATION_PROTOCOL.md`. Shared pieces (Part D): `simulate.py` (cataract / AMD simulation, versioned
parameters), `ocr.py` (one named OCR engine), `records.py` (immutable records in `work/results/`). Each part's script:
`eval_mode1_detect.py` (A), `eval_voice.py` (B), `eval_mode2_ocr.py` (C). Every script takes `--split dev|test` and
reads the manifest in `data/manifests/`.
