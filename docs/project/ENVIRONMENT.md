# Environment

**Status: a proposal (2026-11-20).** Nothing here has been installed or verified. When a member sets up a machine,
record what was actually installed in the machine table below; package changes are the user's (the guard denies
`pip` / `conda` / `uv` package changes from an agent session, `CLAUDE.md` rule 5.5).

## Project environment (critical instruction 3)

Either form satisfies the guard:

- conda env **`findsee`** (activate it before launching the agent, or pin per command: `conda run -n findsee
  --no-capture-output python ...`);
- a virtual environment **inside the project folder**, `.venv/` (activate it, or run `.venv/bin/python ...` /
  `.venv\Scripts\python ...` on Windows, or `uv run ...`).

Proposed Python: **3.11** (a version with wheels for every package below on Windows, macOS and Linux; confirm when
installing).

## Proposed packages (by part)

| Part | Packages (names only; pin the versions you install in `requirements.txt`) |
|---|---|
| all | `numpy`, `opencv-python`, `pillow`, `pytest` |
| A | `ultralytics` (YOLO / YOLO-World / YOLOE), `torch` + `torchvision` (CPU or the CUDA build matching the machine) |
| B | `faster-whisper` or `openai-whisper`, `sounddevice` or the UI's recorder, one TTS package, the VLM provider's SDK if a cloud VLM is chosen |
| C | `opencv-python` (CLAHE, filters, adaptive threshold) |
| D | `gradio` or `streamlit`; one OCR engine with Traditional Chinese support for `eval/ocr.py` |

Example set-up commands for the user to run (not run by an agent):

```bash
conda create -n findsee python=3.11
conda activate findsee
pip install numpy opencv-python pillow pytest ultralytics faster-whisper gradio
pip freeze > requirements.txt   # then trim to the packages above and commit
```

## Caches and weights (inside the project, git-ignored)

| What | Where | How |
|---|---|---|
| YOLO / YOLO-World / YOLOE weights | `models/` | pass the path to Ultralytics explicitly |
| Whisper / faster-whisper models | `models/whisper/` | `download_root` / model path argument |
| Hugging Face cache | `.cache/huggingface/` | `HF_HOME` |
| PyTorch hub cache | `.cache/torch/` | `TORCH_HOME` |
| Ultralytics run outputs | `runs/` | default; never commit |

Downloading weights is the user's decision (the guard asks before `curl` / `wget`); a library fetching its own weights
on first use is fine once the user has approved that model.

## Environment variable names (values live in `.env`, which agents never read)

| Name | Purpose |
|---|---|
| `FINDSEE_VLM_PROVIDER` | `cloud` or `local` (review decision D2) |
| `FINDSEE_VLM_MODEL` | the VLM model name |
| `GEMINI_API_KEY` / `OPENAI_API_KEY` | the cloud VLM key, whichever provider is chosen |
| `FINDSEE_DATA_DIR` | optional override of `data/` |
| `HF_HOME`, `TORCH_HOME` | caches above |

## Agent launch variables

| Name | Effect |
|---|---|
| `FINDSEE_AGENT_ROLE=ADVISOR` | Claude session as ADVISOR: writes only `advisor/claude/` (guard R5) |
| `FINDSEE_ALLOW_HARNESS_EDIT=1` | the user permits harness edits for one session (guard R4); never set by an agent |

## Machines

| Member / part | OS | CPU | GPU (VRAM) | Env form | Python | Verified on |
|---|---|---|---|---|---|---|
| *TBD* | | | | | | |
