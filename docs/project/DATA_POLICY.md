# Data policy — photos, recordings and personal information

The project photographs homes, drug bags and appointment slips, and records voices. These rules apply to every member
and every agent. The guard asks before any write under `data/` (`docs/project/HOOKS.md`, R7).

## What may be collected

- Photos of the team's own homes or a staged desk/shelf scene, taken by a team member who lives there or with the
  resident's spoken consent.
- Drug bags, slips and menus with **every personal field covered** before the photo is taken (name, ID number, birth
  date, chart number, phone, address, barcode/QR that encodes them). Prefer printed mock-ups with realistic fonts and
  layouts.
- Voice recordings of team members and of volunteers who agreed (an elder relative only with their agreement and a
  family member present). No recordings of anyone who did not agree, including people in the background.
- No photos in which a non-consenting person's face is visible; crop or retake.

## Where it lives

| Path | Content | In git? |
|---|---|---|
| `data/raw/<session>/` | original photos and recordings | **no** (`.gitignore`) |
| `data/runtime/` | snapshots and the memory store written by the app | **no** |
| `data/manifests/*.csv` | file name, session, split, sha256, consent note, size band, ground-truth text | yes |
| `tests/fixtures/` | a handful of small, fully redacted or synthetic images and clips for unit tests | yes |
| `work/results/` | numeric result records (no images of people) | yes |

Share raw data between members through the team's private drive, not the repository.

## Runtime privacy design (what the slides claim)

- Mode 1 keeps snapshots only for the retention period set in `src/findsee/config.py` (default proposal: 24 hours) and
  deletes older ones (`MemoryStore.prune`).
- If a cloud VLM is used, only the single image that answers a question is sent, only when the user asks; periodic
  snapshots never leave the machine. The slide names the provider.
- API keys live in `.env` on each member's machine; agents never read it (`CLAUDE.md` rule 2); the variable names are
  in `ENVIRONMENT.md`.

## Medication safety

Mode 2 makes text easier to see; it does not interpret prescriptions. Any OCR read-out in the app carries the label
「僅供參考，以藥師說明為準」 and is not presented as a dosage instruction.

## Removing data

A member or volunteer who withdraws consent: delete their files from `data/raw/` and the shared drive, remove their
rows from the manifests, mark affected result records as superseded (a new record), and note it in `PROGRESS.md`.
