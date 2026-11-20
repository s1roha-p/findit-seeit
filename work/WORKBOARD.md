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
