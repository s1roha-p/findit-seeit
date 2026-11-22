# Stage Brief S2: Mode 2 Synthetic CPU FPS Benchmark (Lane C2)

- **Session:** `C-20261122T1606Z-gemini-1384` (Gemini MAIN, Part C, Lane C2)
- **Stage bound:** Write ONLY `eval/bench_mode2_fps.py`. Do NOT execute Python or the benchmark. The script itself must write NO files at runtime. Stop and hand back once written and self-checked.

## Settled facts (cited)

1. **Frozen interface (`work/claude-main/C-20261122T1606Z-claude-0984/LANES.md` section 1):**
   - `findsee.mode2.presets`: `PRESETS: dict[str, Preset]` (keys `"cataract"`, `"amd"`), `get_preset(name: str) -> Preset`.
   - `findsee.mode2.pipeline.enhance(image, preset) -> np.ndarray`: takes BGR `uint8` array `(H, W, 3)` (`H, W >= 8`) and a `Preset` or preset name `str`, returns a new `uint8` array of equal shape.
2. **Evaluation protocol (`docs/project/EVALUATION_PROTOCOL.md` sections 1, 3, 4 & `LANES.md` section 0):**
   - Backlog item `B-10` (Mode 2 live-path / frame-rate benchmark at 1280x720).
   - **Tier E0** ("It runs: one example, by eye"): this script runs on synthetic 1280x720 frames (default 60 timed frames, 5 warmup frames) and writes NO files because Part D's `eval/records.py` does not exist yet (`record_id: null`, reason `"no record writer yet (Part D eval/records.py)"`).
   - E2 speed requirement in `EVALUATION_PROTOCOL.md` is median of 300 frames after 30 warm-up frames on the demo machine with a recorded `work/results/` entry; note this clearly in the JSON `"limitations"` string.
3. **Import path (`LANES.md` & user prompt):** Unlike `tests/mode2/`, `eval/bench_mode2_fps.py` may be invoked directly with `python eval/bench_mode2_fps.py`, so it **may** prepend `<repo_root>/src` to `sys.path` via `pathlib.Path(__file__).resolve().parent.parent / "src"` before importing `findsee`.
4. **Environment (`LANES.md` section 0):** No conda `findsee` or `.venv` exists on this machine. Do NOT run Python or any other interpreter (`CLAUDE.md` rule 1.3).
5. **Allowed libraries (`LANES.md` section 0):** `numpy`, `cv2` (`opencv-python`), Python stdlib (`argparse`, `dataclasses`, `json`, `os`, `pathlib`, `platform`, `sys`, `time`), and `findsee.*`. Nothing else.

## Numbered steps

1. **Read required context (do NOT read `src/` or `pyproject.toml`):**
   - `AGENTS.md`, `CLAUDE.md`, `work/claude-main/C-20261122T1606Z-claude-0984/LANES.md`, `docs/project/EVALUATION_PROTOCOL.md`, `eval/README.md`.
2. **Write `eval/bench_mode2_fps.py`:**
   - Compute repository root and `src/` path using `pathlib.Path(__file__).resolve().parent.parent / "src"` and insert at index 0 of `sys.path` if not already present, before importing `findsee.mode2.pipeline.enhance` and `findsee.mode2.presets.PRESETS`, `get_preset`.
   - `parse_args(argv: list[str] | None = None) -> argparse.Namespace`:
     - `--preset`: `default="both"`, `choices=("both", *sorted(PRESETS.keys()))`.
     - `--frames`: `type=int`, `default=60` (validate `>= 1`, call `parser.error(...)` if `< 1`).
     - `--warmup`: `type=int`, `default=5` (validate `>= 0`, call `parser.error(...)` if `< 0`).
     - `--width`: `type=int`, `default=1280` (validate `>= 8`, call `parser.error(...)` if `< 8`).
     - `--height`: `type=int`, `default=720` (validate `>= 8`, call `parser.error(...)` if `< 8`).
   - `build_synthetic_frame(width: int, height: int, seed: int = 0) -> np.ndarray`:
     - Build an in-memory `(height, width, 3)` BGR `uint8` light card (`(235, 235, 235)`) with dark border marks and centered dark ASCII text (`(20, 20, 20)`) drawn via `cv2.putText` plus seeded Gaussian noise (`np.random.default_rng(seed)`, `sigma=4.0`, clipped to `[0, 255]` `uint8`).
     - Must NOT open a camera (`cv2.VideoCapture`), read/write image files, or use photos of people.
   - `benchmark_preset(frame: np.ndarray, preset_name: str, warmup: int, frames: int) -> dict[str, object]`:
     - Resolve `preset = get_preset(preset_name)`.
     - Execute `warmup` untimed calls to `enhance(frame, preset)`.
     - Execute `frames` timed calls using `time.perf_counter()` around each `enhance(frame, preset)` call, collecting elapsed milliseconds in a list.
     - Outside the timed region (e.g., on the last output frame), validate `last_out.shape == frame.shape` and `last_out.dtype == np.uint8`.
     - Compute `median_ms = float(np.median(timings_ms))`, `p90_ms = float(np.percentile(timings_ms, 90))`, and `fps = (1000.0 / median_ms) if median_ms > 0.0 else None`.
     - Return dictionary with `preset: preset_name`, `preset_config: dataclasses.asdict(preset)`, `median_ms`, `p90_ms`, `fps`.
   - `main(argv: list[str] | None = None) -> int`:
     - Parse CLI args, build synthetic frame `(height, width, 3)`, resolve target preset names (`list(sorted(PRESETS.keys()))` when `args.preset == "both"` else `[args.preset]`).
     - Benchmark each selected preset and assemble summary JSON dict:
       - `"backlog_id": "B-10"`
       - `"tier": "E0"`
       - `"record_id": None`
       - `"record_id_reason": "no record writer yet (Part D eval/records.py)"`
       - `"synthetic": True`
       - `"frame_shape": [args.height, args.width, 3]`
       - `"frames": args.frames`
       - `"warmup": args.warmup`
       - `"platform": platform.platform()`
       - `"machine": platform.machine()`
       - `"cpu_count": os.cpu_count()`
       - `"python_version": platform.python_version()`
       - `"numpy_version": np.__version__`
       - `"cv2_version": cv2.__version__`
       - `"cv2_num_threads": int(cv2.getNumThreads())`
       - `"results": results_by_preset`
       - `"limitations": "E0 synthetic CPU microbenchmark only (no camera, no disk record writer); E2 protocol requires 300 frames after 30 warmup on the demo machine with eval/records.py."`
     - Print `json.dumps(summary, indent=2, ensure_ascii=True)` to stdout (ASCII-only).
     - Write NO files to disk. Return `0`.
   - Include `if __name__ == "__main__": raise SystemExit(main())`.
3. **Self-check before hand-back:**
   - Read every line of `eval/bench_mode2_fps.py` and verify:
     - All CLI arguments, defaults, and JSON fields match the specification.
     - No files written at runtime, no camera usage, no non-ASCII characters anywhere.
     - Valid Python 3.11+ syntax, valid `cv2` / `numpy` / stdlib API usage.
     - `CLAUDE.md` rule 1.4 comment discipline: module docstring, docstrings on every function, detailed comments on every code block, line, and variable.

## Must-nots

- Do NOT read or write `src/**`, `pyproject.toml`, `tests/**`, `PROGRESS.md`, `work/BACKLOG.md`, `docs/**`, `work/WORKBOARD.md`, `LANES.md`, `change_log/**`, `data/**`, or any harness files.
- Do NOT run Python or any interpreter.
- Do NOT run mutating git commands.
- Do NOT install or download anything, read `.env` files, or launch sub-agents.
- Do NOT create outside artifacts or leave scratch files behind.

## Hand-back format

Return a concise summary listing:
1. File created and CLI/JSON fields implemented.
2. Verification checklist against `LANES.md` section 1 and `EVALUATION_PROTOCOL.md`.
3. Confirmation of "not run: no project environment", zero disk writes at runtime, no `src/` reads, and comment-discipline self-check.
4. Any contract edge cases or ambiguities noticed.
