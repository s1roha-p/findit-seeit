# Workboard — MAIN file and device ownership

Re-read before editing. Claim bounded paths plus device/compute scope, session ID, UTC start, ETA and log/result path.
Do not overwrite another session's edits. Advisors read only. A Markdown row is coordination metadata, not a lock:
members work on their own clones, so a claim reaches the others only once it is pushed to `main` (or posted in the
team chat for a same-day task).

**Rules.**
- One claim per session; release it in place: `(released <UTC>)` in the first cell and the outcome with the record path
  at the end of the last cell. Released rows stay until a coordinated archive cut (`work/archive/WORKBOARD_<date>.md`).
- Files of another part are claimed only with that part's owner's agreement (`docs/project/WORK_SPLIT.md`).
- One evaluation run per device at a time; a demo machine is claimed for rehearsals (`Host / device` column).
- Session ID: `<part>-<UTC stamp>-<agent>-<4 hex>`, e.g. `C-20261122T0930Z-gemini-3f9a`.

## Active claims

| UTC start | Session / agent / part | Item (and why) | Files it may write | Host / device | ETA | Log / result |
|---|---|---|---|---|---|---|
| 2026-11-22T16:06Z (released 2026-11-22T16:38Z) | `C-20261122T1606Z-claude-0984` / Claude MAIN (lead) / C | Lane C1: Part C `enhance()` + presets (B-08), parallel-orchestrator trial on branch `part-c/dual-orch-test` | lane C1 set in `work/claude-main/C-20261122T1606Z-claude-0984/LANES.md`; `PROGRESS.md`, `work/BACKLOG.md`, `docs/project/ORCHESTRATION_METHOD.md` | this Windows machine; no compute (no project env) | 2026-11-22T18:00Z | `work/claude-main/C-20261122T1606Z-claude-0984/` Released by the lead after integration: 182 tests pass in conda `findsee` (E0), evidence `work/claude-main/C-20261122T1606Z-claude-0984/evidence/`. |
| 2026-11-22T16:06Z (released 2026-11-22T16:38Z) | `C-20261122T1606Z-gemini-1384` / Gemini MAIN / C | Lane C2: Part C contract tests + fps benchmark script (B-08, B-10), same trial | lane C2 set in the LANES file above | this Windows machine; no compute (no project env) | 2026-11-22T18:00Z | `work/gemini-main/C-20261122T1606Z-gemini-1384/` (STAGED: `HANDBACK.md`, `change_log/2026-11-22_16-06_part-c-lane-c2-tests.md`; not run: no project env) Released by the lead after integration: 182 tests pass in conda `findsee` (E0), evidence `work/claude-main/C-20261122T1606Z-claude-0984/evidence/`. |
| 2026-11-22T16:22Z (released 2026-11-22T16:38Z) | `C-20261122T1621Z-gemini-1777` / Gemini MAIN / C | Lane C2 round 2: tests for `make_custom` and `live.py` (B-10), in parallel with C1 round 2 | `tests/mode2/test_custom_preset.py`, `tests/mode2/test_live.py` (LANES section 2R) | this Windows machine; no compute (no project env) | 2026-11-22T18:00Z | `work/gemini-main/C-20261122T1621Z-gemini-1777/` (STAGED: `HANDBACK.md`, `change_log/2026-11-22_16-21_part-c-lane-c2-round2-tests.md`; not run: no project env) Released by the lead after integration: 182 tests pass in conda `findsee` (E0), evidence `work/claude-main/C-20261122T1606Z-claude-0984/evidence/`. |
