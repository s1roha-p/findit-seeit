# CLAUDE.md — FindSee (幫長輩找得到也看得清) multimedia final project

These rules bind every MAIN agent - Claude Code, Codex and Gemini alike (`AGENTS.md`, `GEMINI.md`).

## 1. Critical instructions and authority

1. Work only inside the project root. Do not browse, read, write, or follow links into other folders. The root is
   fixed at session start; changing directory does not expand it. One exception: the user-level Claude Code folder
   (`~/.claude`, or `CLAUDE_CONFIG_DIR`) may be read, except its credential store; only this project's own folder there
   (`projects/<project slug>/`: memory, transcripts) may be written or named in a shell command.
2. NEVER access, read, create, or modify `.env` files, including `.env.*`, `.env.example`, and files ending in `.env`.
   Do not print credentials, dump the environment or store an environment copy. Non-secret variable names are listed
   in `docs/project/ENVIRONMENT.md`.
3. Develop in the project environment: the conda env `findsee`, or the project's own `.venv` (activate it, or pin it per
   command: `conda run -n findsee --no-capture-output ...`, `.venv/bin/python ...`, `uv run ...`). Project Python,
   tests, hooks and evaluations use it; record which environment produced each result. If it is not available,
   report the blocker and continue source/document work; do not install or substitute another interpreter.
4. Add detailed comments or descriptions for every edited/new code block, line, and variable, explaining purpose,
   reasoning, shapes/dtypes/units/ranges where relevant. Functions/classes need docstrings; JSON settings need
   companion documentation because JSON has no comments. Keep comments accurate and console output ASCII-safe (user
   interface text and spoken replies in Traditional Chinese are expected and fine).

The user's current instructions and existing authorization take precedence over repository guidance. Never rewrite
rules to evade an access boundary. Explicitly requested documentation/harness edits are authorized work; a tool
permission or hook restriction still has to be honored, and a refusal must be explained without bypassing it.

Hooks provide partial checks and reminders, not a sandbox. Read `docs/project/HOOKS.md` before relying on them; it
lists what the guard denies, what it asks (every git rule asks, R6) and the commands it blocks by mistake.

## 2. Project identity and scope

Team final project of *Introduction to Multimedia Technology* (多媒體技術概論). Members: 賴聲愷, 潘仲奇, 廖彥翔,
邱廷軒; parts are assigned in `docs/project/WORK_SPLIT.md` (owners to be confirmed). Topic: a dual-mode home assistant
for elders -

- **Mode 1, find things (尋物):** periodic snapshots + open-vocabulary detection + a last-seen memory; the elder asks by
  voice (ASR), a VLM phrases where the item is, TTS answers, the boxed photo is shown.
- **Mode 2, see clearly (智慧放大鏡):** image pre-compensation for cataract and AMD - crop, denoise, CLAHE, upscale,
  sharpen, high-contrast or color pre-compensated display.

Deadline: the final presentation, planned for 2026-12-17 (confirm). Deliverables: working demo, measured evaluation,
final slides (team Canva deck 「多媒體報告」, bilingual), report if required. The reviewed proposal and the open
decisions: `docs/project/PROPOSAL_REVIEW.md`. Interfaces: `docs/project/ARCHITECTURE.md`.

Work only on data collected under `docs/project/DATA_POLICY.md`. Do not collect people's photos or voices, scrape
images of people, or invent results.

## 3. Roles and ownership

**Claude Code, Codex and Gemini (Gemini CLI or Antigravity) are peer MAIN implementers.** Any of them may instead be
explicitly assigned ADVISOR in a separate session and then writes only its own `advisor/{claude,codex,gemini}/` folder.
Session roles and write scopes: `AGENTS.md`; advisor workflow: `AGENT_ADVISOR.md`.

Research advisors: a Claude ADVISOR session on Mythos, the **Claude Mythos RESEARCH ADVISOR**, takes commissioned
diagnosis, mechanism, design and adversarial-review questions and the critical vulnerability jobs (untrusted weight
files, personal data or keys leaving the machine, destruction of the team's work, the guard itself) - charter
`docs/project/RESEARCH_ADVISOR.md`, write scope `advisor/claude/`. A Codex ADVISOR session on Astra, the **Codex Astra
RESEARCH ADVISOR**, takes commissioned theory jobs - statistical design of the evaluation, derivations, literature
synthesis, critiques of reasoning - and reviews no code - charter `docs/project/RESEARCH_ADVISOR_CODEX.md`, write scope
`advisor/codex/`. Both keep the ADVISOR contract in full and run nothing; MAIN checks their numbers, runs what existing
authorization covers and answers in their ledgers.

Each human member owns one part (`WORK_SPLIT.md`); an agent works on the part its human assigns and touches another
part's files only through the interfaces in `ARCHITECTURE.md` or with that owner's agreement. MAINs claim files and
compute on `work/WORKBOARD.md`, re-read shared files immediately before editing, and preserve other sessions' work. A
workboard row is coordination metadata, not a lock.

Document review: advisors also review the project documents and open each improvement as a ledger entry; MAIN verifies
and applies or rejects it; entries that touch autonomy, authority, limits, permissions, acceptance gates, defaults or
user-written text are marked `Decision: USER`.

## 4. Where work lives

| Path | Purpose |
|---|---|
| `src/findsee/` | the package: `mode1/` (A), `voice/` (B), `mode2/` (C), `app/` (D), shared `types.py`, `config.py` |
| `tests/` | pytest; small consented or synthetic fixtures in `tests/fixtures/` |
| `eval/` | evaluation harness and each part's evaluation script (`EVALUATION_PROTOCOL.md`) |
| `scripts/` | helper scripts (data manifests, exports) |
| `data/` | `raw/` and `runtime/` git-ignored; `manifests/` tracked; every write asks (privacy) |
| `models/`, `.cache/`, `runs/` | downloaded weights, library caches, Ultralytics outputs; git-ignored; never hand-written |
| `work/WORKBOARD.md`, `work/BACKLOG.md`, `PROGRESS.md` | active ownership, open items and decisions, narrative |
| `work/results/` | immutable evaluation records (JSON) |
| `work/<agent>-main/<session>/` | a MAIN session's notes, briefs and stage records (`claude-main`, `codex-main`, `gemini-main`) |
| `work/tmp/<session>/` | session scratch; removed once its evidence is saved |
| `change_log/` | one record per logical code/harness change, including failures and rollback |
| `docs/project/` | review, split, architecture, protocol, environment, data policy, hooks, orchestration, research charters |
| `advisor/` | the three advisors' folders |

## 5. Implementation rules

1. Build to the interfaces in `ARCHITECTURE.md`; stubs first, so other parts can integrate early.
2. Measure before claiming: a number goes on a slide only at E2 with a record id (`EVALUATION_PROTOCOL.md`).
3. Change one thing at a time when comparing (a preset, a model, a prompt); keep the baseline record.
4. Never overwrite a member's data, weights, results or another part's files; never commit `data/raw/`, weights or
   media of people.
5. Never install/update dependencies, download weights, change drivers, or run another environment without the user's
   authorization. Prepare the exact command and continue independent work.
6. Record all attempts, errors and timeouts in the session record; no selective deletion of results.
7. Cross-platform Python (members may use Windows, macOS or Linux): `pathlib`, explicit UTF-8, CSV `newline=""`,
   argument-list `subprocess`, `sys.executable`, `time.perf_counter()`; no `shell=True`, no case-only file names.
8. Capability-dependent features (GPU, camera, microphone) are probed on the real device; distinguish unsupported
   from broken; never catch every error and silently switch to a fallback - report requested and effective options.
9. Package code logs through `logging`; scripts and evaluation tools may print.
10. Medication safety and privacy: Mode 2 enhances images and does not interpret prescriptions; follow
    `DATA_POLICY.md` for anything recorded or uploaded.
11. Git (R6): read-only git and new branches (`part-a/<topic>` ...) need no approval. Every other git command the
    guard knows - push, pull, merge, rebase, reset --hard, clean, stash, checkout/switch/restore, ref deletion, `git
    config` writes, one-off `-c` values, `-C`/`--git-dir`, writes into `.git/` or `.gitmodules`, commits - **asks the
    user**; do not try to phrase around a confirmation. Commit only when the user asked for it; commit messages carry
    no attribution lines. **Plan commits before making them:** one commit per logical change (code, its tests, docs,
    coordination records), ordered so each commit still imports and passes its tests; show the plan (commit, files,
    message) before running it. Split only where it pays: each extra commit costs one more user confirmation (R6) and
    tool call, and buys a separate review and revert. Merge parts when a file holds several changes (no interactive
    staging here), when a part is too small to review alone, or when the parts only make sense together.
12. Harness/role documents may be edited for an authorized task. The guard asks the user to confirm each Write / Edit
    of `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` and `CLAUDE.local.md` (any depth). `AGENT_ADVISOR.md`, `.mcp.json` and the
    `.claude/`, `.agents/`, `.codex/`, `.gemini/` folders stay denied unless the user launches with
    `FINDSEE_ALLOW_HARNESS_EDIT=1`; otherwise deliver those changes as a patch the user applies (`git apply`), checked
    first with `git apply --check` and the guard self-test. Do not self-set permission variables.
13. Documentation vs code: when a document and the existing code disagree, follow the code, point out each
    inconsistency in your final reply, and correct the document (harness documents through rule 12's route). This
    covers what documents say about the code, not the user's instructions in section 1.

## 6. Evidence standard

`docs/project/EVALUATION_PROTOCOL.md` is the single source of truth for tiers (E0-E2), splits, metrics and result
records. Every claim names its record id, code commit, dataset split and size, machine and limitations. Missing
metrics are `null` with a reason, never zero. No invented results.

## 7. Acceptance gates

- **Merged to `main`:** the part's tests pass; the interface in `ARCHITECTURE.md` holds; a `change_log/` entry exists;
  one other member reviewed the pull request.
- **Feature done:** E1 numbers recorded; works in the app's demo path.
- **On a slide:** E2 record with the protocol's fields.
- **Demo freeze (2026-12-14, proposed):** only fixes after the freeze; every fix re-runs the demo script.

## 8. Session protocol

Start: read `AGENTS.md` and this file (Gemini: `GEMINI.md` first), the newest `PROGRESS.md` entries, the workboard,
the backlog, relevant change logs and open advisor advice. Confirm which part the session works on; claim it.

During: stub → implement → test → evaluate (E0/E1) → record → integrate. Keep updates short.

End: record what changed and why, evidence or its absence, platform coverage, next action and blockers; remove the
session's scratch; release the claim. Use UTC ISO-8601 for new timestamps and filesystem-safe UTC stamps in file names.

## 9. Environment

Run from the project root with the project environment active or pinned per command (section 1, rule 3). Do not
hard-code a home-directory interpreter. Validate package versions and device access before evaluation work.
`docs/project/ENVIRONMENT.md` holds the proposed stack, caches, variable names and the machine table.

## 10. When user input is needed

Use existing authorization first. Otherwise prepare a concrete proposal for installs, downloads, new personal data,
scope or interface changes that affect another part, destructive actions, and git publication; record the reason and
continue independent work. Do not ask again for an action already authorized.

## 11. Quick reference

- `/session-start`, `/checkpoint`, `/check-advice`, `/eval`: MAIN workflows (Claude commands; the same steps are
  `.agents/skills/main-*` for Codex and `.agents/workflows/*` for Gemini).
- `/advisor-*`: only in a session already assigned ADVISOR; `/advisor-research` only in one commissioned for research.
- `conda activate findsee` or `source .venv/bin/activate` (Windows: `.venv\Scripts\activate`).
- `python .claude/hooks/selftest.py` (project environment active): guard simulation tests; also with
  `FINDSEE_AGENT_ROLE=ADVISOR` and `FINDSEE_ALLOW_HARNESS_EDIT=1`.
