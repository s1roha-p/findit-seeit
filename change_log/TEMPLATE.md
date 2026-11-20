# <YYYY-MM-DD_HH-MM_slug> — <one-line title>

Copy this file to `change_log/YYYY-MM-DD_HH-MM_<slug>.md` when you START a change under `src/ tests/ eval/ scripts/
requirements/` or a root code file (`main.py`, `app.py`, `pyproject.toml`, `requirements.txt`, `environment.yml`), or a
harness change; fill it in as you go. One entry per logical change. The Stop hook blocks a Claude MAIN session whose
recorded tool writes touched code without both a `change_log/` entry and a `work/WORKBOARD.md` row.

- **Status:** WIP | STAGED | DONE | REVERTED
- **Agent / part:** claude | codex | gemini / A | B | C | D
- **Backlog id:** B-NN (and review id if any)
- **Commit(s):** <sha, or "uncommitted - user commits">
- **Baseline:** <record id it is compared against, or "none">

## Files
- `path/to/file.py` — <what changed in one line>

## What and why
<2-8 lines: the mechanism, the problem it solves, why this way. Link the backlog row.>

## Evidence
| what | before | after | record ids | tier | split, n |
|---|---|---|---|---|---|
| | | | | | |

## Interfaces touched
<functions or types from `docs/project/ARCHITECTURE.md` that changed, and who agreed; or "none">

## Rollback
<exact steps: revert the commit or restore the files; what depends on it>

## Platform coverage
<Windows / macOS / Linux: pass | fail | untested; GPU / CPU>

## Comment discipline
<confirm every added/changed block, line and variable is commented and docstrings exist>

## Notes / follow-ups
<anomalies, things for the advisors, what the user must decide>
