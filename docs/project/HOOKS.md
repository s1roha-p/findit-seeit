# Claude Code hooks — what the guard does, and its limits

Files: `.claude/settings.json` (hook wiring and permission lists), `.claude/hooks/guard.py` (the checks),
`.claude/hooks/selftest.py` (simulated payloads), `.claude/settings.local.example.json`. The guard is partial tool-input
checking plus reminders; it is not a sandbox, and it only sees **Claude Code's** tool calls. Codex and Gemini keep the
same rules by contract (`AGENTS.md`, `GEMINI.md`).

Change record: `change_log/2026-11-20_00-00_initial-pack.md`.

## Events

| Event | Behavior |
|---|---|
| SessionStart | Prints the rules, the role, the environment status and the reading order |
| PreToolUse Bash/PowerShell | Outside paths, env/secret references, destructive commands, installs, role scope, harness writes, environment; git rules ASK |
| PreToolUse Read/Glob/Grep | Outside paths and prohibited names |
| PreToolUse Write/Edit/MultiEdit/NotebookEdit | Outside paths, advisor scope, harness and git-related paths, artefacts, secrets in content, data/ asks |
| PostToolUse writes | Comment/docstring and change-log reminders; `print()` in package code |
| Stop | Blocks once when code was written without a `change_log/` entry and a `work/WORKBOARD.md` row |

## Rules at a glance

| Rule | Deny | Ask | Allow |
|---|---|---|---|
| 1 Project root | paths outside the root (except this project's folder in `~/.claude`) | | |
| 2 `.env`, `secrets/` | every read, write, print | | |
| 3 Environment | Python launches without conda `findsee` or the project `.venv` active or pinned | | `conda run -n findsee`, `.venv/bin/python`, `.venv\Scripts\python`, `uv run` |
| R4 Harness | `AGENT_ADVISOR.md`, `.mcp.json`, `.claude/`, `.agents/`, `.codex/`, `.gemini/` (any depth) | `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `CLAUDE.local.md` (any depth) | all of them under `FINDSEE_ALLOW_HARNESS_EDIT=1`; harness folders under `work/tmp/` |
| R5 ADVISOR | writes outside `advisor/claude/`; launching the app, tests, `eval/`, `scripts/`, `src/`, MAIN session tools | mutating git (R6) | reading; cheap checks writing `advisor/claude/tmp/` |
| R6 Git | | push, pull, merge, rebase, cherry-pick, fetch --prune, reset --hard/--merge, clean, stash, filter-*, checkout/restore/switch, branch/tag deletion, reflog expire, gc --prune, update-ref -d, `-C`/`--git-dir`/`--work-tree`, `GIT_DIR`/`GIT_WORK_TREE`, `git config` writes, `git -c`/`--config-env`, `GIT_CONFIG_*`, writes into `.git/` or `.gitmodules`, commit | status, diff, log, show, add, apply, fetch, `checkout -b`/`switch -c` (without `-f`/`-m`), `git config --get/--list` |
| R7 Artefacts / data | hand-written `models/`, `.cache/`, `runs/`, `work/models/`, weights, images, audio, video (outside `docs/`, `advisor/`) | every file-tool write under `data/` | |
| R8 System | recursive deletes, `sudo`, GPU resets, `pip`/`conda`/`uv` package changes, piping downloads into a shell | process kills, network downloads | |
| R10 Credentials | printing `*KEY*`/`*SECRET*`/`*TOKEN*`/`*PASS*` | | |

## R6: git asks

Every git or git-related command the guard recognizes asks for approval instead of being refused:

- Every git rule - the text patterns, the word rules (abbreviated options, `git.exe`,
  commands inside `bash -c`, `eval`, `trap`, `find -exec`, substitutions), the `git config` write rule, the one-off
  configuration rules and the `GIT_DIR` / `GIT_CONFIG_*` assignment rules - now produces a **confirmation** whose reason
  says what the command does and ends in `(R6)`.
- Writes into a `.git` folder (or a `.git` pointer file) and to `.gitmodules`, through the file tools or a shell
  redirect / `cp` / `mv` / `tee` / hard link, ask too. An ADVISOR is still refused such writes by its
  write scope, which is not a git rule.
- **A git confirmation never lets a line through that another rule refuses.** The git reasons are collected and asked
  only after every non-git check has passed: `git push; cat .env`, `git add . && rm -rf work/results`, `git -C /etc
  status`, `git config core.hooksPath /tmp/h`, `git push && pip install x` are all denied.
- `.claude/settings.json` lists the common git forms under `permissions.ask` (not `deny`): a settings deny would refuse
  them before the hook's ask is considered.
- Still refused in every role: a line nested more than three levels deep (`eval`, `bash -c`, `$( )`, ...), a line too
  complex to read in bounded time, and a line whose `cd`s leave too many possible folders. These are parser limits, not
  git rules; write the command out or put it in a script file.

What to approve: commits and pushes you asked for; never a `core.hooksPath`, `core.fsmonitor`, alias, pager, editor or
credential-helper value you did not ask for (each makes Git run a program); never a write into `.git/hooks/`.

## Commands the guard blocks by mistake, and how to phrase them

| Blocked command shape | Rule that fires | Phrase it as |
|---|---|---|
| Any `..` in a command, including an ellipsis `...` in an `echo` | parent-path scan | `----` as a separator; root-relative paths |
| A quoted absolute-looking fragment in inline code (`'/result.json'`) | absolute-path scan | put the code in a script file (Write tool) and pass paths as arguments |
| Any `/tmp` path, including a client's background-task output | absolute-path scan | write logs inside `work/tmp/<session>/` |
| `$HOME` or `${HOME}` | outside-variable scan | stay in the root |
| A glob followed by a path tail (`x_*/manifest.json`) | absolute-path scan | `cd` into the parent first, or `find <dir> -name manifest.json` |
| A heredoc (`<<EOF ... EOF`) | every scan applies to the body | write the file with the Write tool and run it by path |
| `cat eval/x.py` or a grep pattern with the word `python` while no environment is active | interpreter-launch check | activate or pin the environment; or use the Read / Grep tools |
| `cd <root>; ...` (the root's absolute path directly followed by `;`) | `cd` target check | leave the `cd` out (the shell starts in the root), or `cd <root> && ...` |
| An ADVISOR's `cat eval/...` or `grep ... scripts/...` | ADVISOR mention rule | use the Read / Grep tools |

## Known limits

- Only Claude Code is covered. Codex and Gemini need their own tool restrictions (`.codex/`, `.gemini/settings.json`,
  user-owned) or keep the rules by contract.
- An interpreter named by a relative path inside the project other than `.venv` (for example `venv/bin/python`) is not
  recognized as a Python launch by the environment check.
- The shell reader is a heuristic, not a full shell: commands built from variables, aliases, functions, scripts and
  programs that run git or delete files themselves are not seen; `subprocess` calls inside Python are not seen.
- Hook timeouts or a missing `python` on the launching shell can make the client treat a hook as non-blocking; check
  `/hooks` in a live session.

## Setup and validation

From the root, with the project environment active:

```bash
python .claude/hooks/selftest.py                               # MAIN
FINDSEE_AGENT_ROLE=ADVISOR python .claude/hooks/selftest.py    # ADVISOR
FINDSEE_ALLOW_HARNESS_EDIT=1 python .claude/hooks/selftest.py  # MAIN with harness edits allowed
```

Each run creates and removes a few fixture files under `.claude/state/` and `work/tmp/`; run the three one after
another, not in parallel. On 2026-11-20, in a Linux container with Python 3.13 (no Claude Code session wired), the
three runs passed with 0 failures (843 cases as MAIN and with harness edits allowed, 847 as ADVISOR; no case
skipped). Not yet verified: live wiring on the team's machines, native
Windows and macOS, and PowerShell as the hook shell. On Windows the hook command needs `python` on the PATH of the
shell Claude Code launches (the activated environment).

Main agents never set `FINDSEE_ALLOW_HARNESS_EDIT` themselves; the user may launch with it for an explicitly
authorized harness-maintenance session.
