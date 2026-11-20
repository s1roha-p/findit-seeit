#!/usr/bin/env python3
"""guard.py - Claude Code hooks for the FindSee final project (找得到也看得清 / "find it, see it").

Standard library only, Python 3.8+. ASCII-only output. Every git rule asks for a confirmation instead of refusing
(R6). This docstring and docs/project/HOOKS.md describe the behaviour.

Wired from `.claude/settings.json` as `python "${CLAUDE_PROJECT_DIR}/.claude/hooks/guard.py" <event> || exit 2`;
the current working directory is the project root:

    session-start   # SessionStart
    pre-bash        # PreToolUse   matcher: Bash|PowerShell
    pre-read        # PreToolUse   matcher: Read|Glob|Grep
    pre-write       # PreToolUse   matcher: Write|Edit|MultiEdit|NotebookEdit
    post-write      # PostToolUse  matcher: Write|Edit|MultiEdit|NotebookEdit
    stop            # Stop

CRITICAL AI SYSTEM INSTRUCTIONS checked or reminded here (subject to user authority):
    1. Work only inside the project folder.                                       (deny)
       Exception: the user-level Claude Code folder (~/.claude, or CLAUDE_CONFIG_DIR) - read anywhere except the
       credential store; write only this project's own folder there (projects/<project slug>/). Shell commands may
       use only that project folder; `cd` into it stays denied.
    2. Never access, read, or modify any `.env` file.                              (deny)
    3. Python runs in the project environment: conda env `findsee`, or the project's own `.venv`
       (deny when neither is active in the launching shell nor pinned in the command).
    4. Detailed comments on every edited code block / line / variable.             (post-write reminder)

Other project rules enforced here:
    R3  `secrets/` is never read or written.
    R4  Role / harness files, at any depth. The three MAIN entry files CLAUDE.md, AGENTS.md and GEMINI.md, and
        CLAUDE.local.md, ask the user to confirm each Write / Edit (Gemini is a MAIN like Claude and Codex). AGENT_ADVISOR.md, .mcp.json and anything in a .claude, .agents, .codex or .gemini folder are
        denied unless the user launches with FINDSEE_ALLOW_HARNESS_EDIT=1. Under work/tmp/ the content of those
        folders is exempt (harness patches are prepared on a copy there); a harness file name keeps its class.
    R5  FINDSEE_AGENT_ROLE=ADVISOR limits writes to advisor/claude/ and refuses launches of the app, tests,
        eval/ and scripts/ tools and of MAIN session tools (work/claude-main/, work/codex-main/, work/gemini-main/).
    R6  Git: every git rule ASKS instead of denying - push; pull / merge / rebase / cherry-pick /
        fetch --prune; reset --hard / --merge; clean / stash / filter-branch / filter-repo; checkout / restore /
        switch (a new branch with -b / -c stays allowed without asking, unless forced); branch / tag deletion,
        reflog expire, gc --prune, update-ref -d; -C / --git-dir / --work-tree and GIT_DIR / GIT_WORK_TREE; `git
        config` write forms; one-off `git -c` / `--config-env` values and GIT_CONFIG_* assignments; writes into a
        .git folder or a .gitmodules file; commits; an ADVISOR's mutating git. A git confirmation is raised only
        after every non-git check has passed, so a line that also breaks another rule (an outside path, a .env
        file, a recursive rm, an install, ...) is still denied.
    R7  Model / data artefacts (models/, .cache/, runs/, weights, media files) are never written by hand; a write
        under data/ asks (privacy: photos and voice of real people need consent).
    R8  No package installs, no GPU resets, no privilege escalation, no recursive deletes; process kills and network
        downloads ask.
    R10 Credentials are never printed (echo/printenv/$env: of *KEY*/*SECRET*/*TOKEN*/*PASS*).
    R11 Sessions that changed code must leave a change_log/ entry and a work/WORKBOARD.md row (Stop hook).

Pre-tool parsing/handler failures exit 2 to block the attempted action; a line nested past the parsers' limits or
too complex to read in bounded time is refused in every role. These checks are not a complete shell or filesystem
sandbox. Run selftest.py in the project environment after a hook edit.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys

# --------------------------------------------------------------------------------------------
# Environment
# --------------------------------------------------------------------------------------------
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # pylint:disable=broad-except
        pass

EVENT = sys.argv[1] if len(sys.argv) > 1 else ""
# Anchor trust to this hook's installation, not a caller-supplied working directory.
PROJECT = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))
TOOL_CWD = PROJECT  # Updated from a validated event cwd before resolving relative tool paths.
TOOL_NAME = ""  # str: the event's tool ("Bash", "PowerShell"), set by `pre_bash`.
PROJECT_NC = os.path.normcase(PROJECT)
ROLE = (os.environ.get("FINDSEE_AGENT_ROLE") or "MAIN").strip().upper()
HARNESS_EDIT = os.environ.get("FINDSEE_ALLOW_HARNESS_EDIT", "").strip() == "1"
ADVISOR_DIR = "advisor/claude"
STATE_DIR = os.path.join(PROJECT, ".claude", "state")

# Claude Code keeps it at ~/.claude unless CLAUDE_CONFIG_DIR names another folder; resolved once, like PROJECT, so a
# link cannot widen it later.
CLAUDE_HOME = os.path.realpath(os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude"))
CLAUDE_HOME_NC = os.path.normcase(CLAUDE_HOME)  # Case-normalised form for the containment test.
# This project's own folder inside it, named the way Claude Code names per-project folders: the project's absolute path
# with every character other than a letter or digit replaced by "-". Lower case, "/"-terminated, relative to
# CLAUDE_HOME: the only part of the folder an agent may write, or name in a shell command.
CLAUDE_HOME_OWN = "projects/" + re.sub(r"[^A-Za-z0-9]", "-", PROJECT).lower() + "/"
# The same folder as an absolute path with its real spelling (the comparison above is case-insensitive);
# used only in messages, so a path with capitals is shown as it is on disk.
CLAUDE_HOME_OWN_PATH = os.path.join(CLAUDE_HOME, "projects", re.sub(r"[^A-Za-z0-9]", "-", PROJECT))
# Never accessible, read or write: the Claude Code credential store (.credentials.json, and any other
# credentials* file), matched on the path relative to CLAUDE_HOME.
CLAUDE_HOME_SECRET_RE = re.compile(r"(^|/)\.?credentials[^/]*$", re.I)

# Critical instruction 3: all Python work happens in the project environment. The hook process inherits the environment
# Claude Code was launched from, so CONDA_DEFAULT_ENV / VIRTUAL_ENV provide a reminder; this is not interpreter
# attestation. Two forms are accepted: the conda env `findsee` (docs/project/ENVIRONMENT.md), or a virtual environment
# that lives inside the project folder (`.venv`, as `python -m venv .venv` or `uv venv` makes it), so team members on
# Windows or macOS without conda can work too.
CONDA_ENVS = ("findsee",)  # tuple[str, ...]: the accepted conda env names.
CONDA_ENV = CONDA_ENVS[0]  # The name used in messages and examples.
_ACTIVE_ENV = (os.environ.get("CONDA_DEFAULT_ENV") or "").strip()  # str: the conda env active at launch, or "".
_VIRTUAL_ENV = (os.environ.get("VIRTUAL_ENV") or "").strip()  # str: the venv active at launch, or "".
# bool: True when the active venv lives inside the project folder (links resolved, case folded as _inside folds).
_VENV_IN_ROOT = bool(_VIRTUAL_ENV) and os.path.normcase(os.path.realpath(_VIRTUAL_ENV)).startswith(PROJECT_NC + os.sep)
# bool: an accepted environment is active in the launching shell (a reminder, not attestation).
VENV_ACTIVE = _ACTIVE_ENV.lower() in {name.lower() for name in CONDA_ENVS} or _VENV_IN_ROOT
# Regex alternation of the accepted conda env names, for the per-command pin check below.
_ENV_ALT = "(" + "|".join(re.escape(name) for name in CONDA_ENVS) + ")"
# The accepted environments as text for messages.
_ENV_TEXT = " or ".join("conda env `%s`" % name for name in CONDA_ENVS) + " or the project's `.venv`"

HARNESS_FILES = {"claude.md", "agents.md", "agent_advisor.md", "gemini.md"}  # set[str]: root harness files.
HARNESS_DIRS = (".claude/", ".agents/", ".codex/", ".gemini/")  # tuple[str, ...]: root harness folders.
# set[str]: harness files whose Write / Edit asks the user instead of being denied. Root-level paths in lower case, as
# `_rel` returns.
HARNESS_ASK_FILES = {"claude.md", "agents.md", "gemini.md"}
# Harness names count at any depth inside the project, not only at the root, because a client can read instructions,
# settings, skills, tool servers or Git hooks from a sub-folder. All names are lower case, so the match folds case (a
# case-insensitive file system sees `claude.md` as CLAUDE.md). set[str]: file names that are harness files wherever they
# sit. CLAUDE.local.md is a personal instruction file; .mcp.json names tool servers the client starts (commands);
# .gitmodules names the sub-module URLs and paths Git clones and checks out.
HARNESS_NAMES_ANY_DEPTH = HARNESS_FILES | {"claude.local.md", ".mcp.json", ".gitmodules"}
# set[str]: the subset that asks instead of denying: the instruction files the user reads and approves as a diff, and -
# R6, git-related - .gitmodules. Everything else in the set above is denied.
HARNESS_ASK_NAMES_ANY_DEPTH = HARNESS_ASK_FILES | {"claude.local.md", ".gitmodules"}
# set[str]: folder names whose whole content is harness, at any depth, and denied: the agents' settings, hooks,
# commands, skills and workflows (.claude, .agents, .codex, .gemini).
HARNESS_DIR_NAMES = {name.rstrip("/") for name in HARNESS_DIRS}
# set[str]: git folder names: a write into the repository's .git folder (or a `.git` pointer file of a sub-module or
# work tree) ASKS instead of being denied. Hooks (.git/hooks/) and the configuration (.git/config) can make Git run
# programs, so the confirmation says so.
GIT_DIR_NAMES = {".git"}
# set[str]: the git-related file names, for the confirmation's wording (`_is_git_path`).
GIT_FILE_NAMES = {".gitmodules"}
# tuple[str, ...]: root-relative prefixes (lower case) the any-depth rule does not apply to at all: "~claude/" is the
# pseudo path `_check_claude_home` returns for this project's own folder in the user-level Claude folder.
HARNESS_EXEMPT_PREFIXES = ("~claude/",)
# str: the session scratch (root-relative, lower case). Under it the folder names in HARNESS_SCRATCH_DIR_NAMES are
# not harness paths, because harness patches are prepared on a copy there (`<scratch>/tree/.claude/hooks/guard.py`);
# a harness *file name* under it keeps its class (CLAUDE.md, AGENTS.md, GEMINI.md, CLAUDE.local.md and .gitmodules
# ask; AGENT_ADVISOR.md and .mcp.json are denied), since a client may read a nested instruction file wherever a
# session works.
HARNESS_SCRATCH_PREFIX = "work/tmp/"
# set[str]: the harness folder names exempt under HARNESS_SCRATCH_PREFIX. Only a folder's content is exempt: a `.git`
# pointer file there (a file, not a folder) asks (`_harness_class`).
HARNESS_SCRATCH_DIR_NAMES = {".claude", ".agents", ".codex", ".gemini", ".git"}

# tuple[str, ...]: root-relative folders holding project code (the Stop hook's change_log / workboard check and the
# comment reminder): the package, tests, the evaluation harness, helper scripts and pinned requirements.
CODE_PREFIXES = ("src/", "tests/", "eval/", "scripts/", "requirements/")
# set[str]: root-level files that are code or dependency definitions.
CODE_FILES = {"main.py", "app.py", "setup.py", "pyproject.toml", "requirements.txt", "environment.yml"}

# tuple[str, ...]: artefact folders, never written by hand: downloaded weights (models/), library caches (.cache/),
# Ultralytics' training / prediction outputs (runs/) and disposable per-run models (work/models/).
ARTEFACT_PREFIXES = ("models/", ".cache/", "runs/", "work/models/")
# re.Pattern: artefact file types - model weights and arrays, images, audio and video.
ARTEFACT_EXT_RE = re.compile(r"\.(h5|hdf5|keras|pb|pt|pth|safetensors|gguf|engine|npz|npy|joblib|pkl|pickle|onnx|"
                             r"tflite|ckpt|png|jpg|jpeg|webp|bmp|heic|wav|mp3|m4a|flac|ogg|mp4|mkv|avi|mov|gif)$",
                             re.I)
# tuple[str, ...]: folders whose writes ask instead of being allowed silently: data/ holds test photos and recordings
# of real people (consent, privacy - docs/project/DATA_POLICY.md).
ASK_PREFIXES = ("data/",)
# any source-like file, wherever it lives, gets the comment-discipline reminder after a write
_CODE_EXT_RE = re.compile(r"\.(py|pyi|ipynb|sh|ps1|bat|cmd|js|ts|cu|c|cc|cpp|h|hpp|json|yaml|yml|ini|toml)$", re.I)

ENV_FILE_RE = re.compile(r"(^|[\\/])[^\\/]*\.env($|\.|[\\/])", re.I)  # All env variants, no example exception.
SECRETS_RE = re.compile(r"(^|[\\/])secrets([\\/]|$)", re.I)
SECRET_CONTENT_RE = re.compile(
    r"(api[_-]?key|secret[_-]?key|passphrase|password|access[_-]?token|auth[_-]?token|"
    r"webhook[_-]?url)\s*[:=]\s*[\"'][A-Za-z0-9+/=_\-\.]{16,}", re.I)


# --------------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------------
def _read_input() -> dict:
    """Parse an object payload; malformed/empty input must reach the blocking error handler."""
    raw = sys.stdin.read()  # Hook event JSON is the only input; never read a transcript or env file.
    data = json.loads(raw)  # Parsing errors are handled by main, rather than converted into allow.
    if not isinstance(data, dict):  # Arrays/scalars are not valid hook event objects.
        raise ValueError("Hook input must be a JSON object")
    return data


def _deny(reason: str, event: str = "PreToolUse") -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": event,
        "permissionDecision": "deny",
        "permissionDecisionReason": "BLOCKED: " + reason}}))
    sys.exit(0)


def _ask(reason: str, event: str = "PreToolUse") -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": event,
        "permissionDecision": "ask",
        "permissionDecisionReason": "CONFIRM: " + reason}}))
    sys.exit(0)


def _to_abs(path: str, resolve: bool = True, base: str | None = None) -> str | None:
    """Resolve a path string (posix, windows or git-bash style) to an absolute real path.

    resolve=False returns the lexical absolute path instead (normalised, links not followed), so a link whose own name
    is a harness path can be judged by that name as well as by its target. base is the folder a relative path is taken
    from; None means the event's validated cwd, TOOL_CWD, as before."""
    path = path.strip().strip("\"'")
    if not path:
        return None
    match = re.match(r"^/([A-Za-z])(/|$)", path)          # git-bash /c/Users/... on Windows
    if match and os.name == "nt":
        path = match.group(1).upper() + ":" + path[2:]
    if path.startswith("~"):
        path = os.path.expanduser(path)
    if not os.path.isabs(path):
        path = os.path.join(TOOL_CWD if base is None else base, path)
    try:
        # Real path (links followed) by default; the lexical form only when a caller asks for it.
        return os.path.realpath(path) if resolve else os.path.normpath(path)
    except Exception:  # pylint:disable=broad-except
        return None


def _inside(abs_path: str) -> bool:
    ncase = os.path.normcase(abs_path)
    return ncase == PROJECT_NC or ncase.startswith(PROJECT_NC + os.sep)


def _rel(abs_path: str) -> str:
    return os.path.relpath(abs_path, PROJECT).replace("\\", "/")


def _in_claude_home(abs_path: str) -> bool:
    """True when `abs_path` (absolute, links resolved) is CLAUDE_HOME or inside it."""
    ncase = os.path.normcase(abs_path)
    return ncase == CLAUDE_HOME_NC or ncase.startswith(CLAUDE_HOME_NC + os.sep)


def _claude_home_rel(abs_path: str) -> str:
    """`abs_path` relative to CLAUDE_HOME: "/" separators, lower case, "" for the folder itself."""
    rel = os.path.relpath(abs_path, CLAUDE_HOME).replace("\\", "/")  # e.g. "projects/<slug>/memory/x.md"
    return "" if rel == "." else rel.lower()


def _check_claude_home(abs_path: str, verb: str) -> str:
    """The CLAUDE_HOME exception to rule 1 for one file-tool path; denies (exits) or returns a pseudo path.

    Read / Glob / Grep may use any path there except the credential store. Write / Edit may use only
    CLAUDE_HOME_OWN: the user-level settings, instructions, hooks, agents, commands and skills stay
    user-owned, as `.claude/` in the project is (R4), and other projects' folders are not this session's.
    FINDSEE_ALLOW_HARNESS_EDIT does not widen this (it never permits outside access). The returned
    "~claude/<relative path>" matches no project rule prefix (harness, artefact, advisor, config), so the
    project-relative checks that follow in pre_write neither misfire on it nor grant anything; an ADVISOR
    is still limited to advisor/claude/ by its scope check."""
    rel = _claude_home_rel(abs_path)  # Relative to CLAUDE_HOME, lower case.
    if CLAUDE_HOME_SECRET_RE.search(rel):
        _deny("%s is the Claude Code credential store. Credentials are never read, copied or edited by "
              "an agent." % abs_path)
    if verb == "write" and not (rel + "/").startswith(CLAUDE_HOME_OWN):
        _deny("Writes in the user-level Claude folder are limited to this project's own folder (%s). Its "
              "settings, instructions, hooks, agents, commands and skills are user-owned, and other "
              "projects' folders are not this session's." % CLAUDE_HOME_OWN_PATH)
    return "~claude/" + rel


def _is_harness(rel: str) -> bool:
    """True for the root harness set; used now only to word a message for a nested path."""
    low = rel.lower()
    return low in HARNESS_FILES or low.startswith(HARNESS_DIRS)


def _harness_class(rel: str) -> str | None:
    """The R4 / R6 class of one project-relative path: "ask", "deny" or None (not a harness path).

    Any path segment equal to a HARNESS_DIR_NAMES name (a .claude / .agents / .codex / .gemini folder at any depth) is
    "deny"; otherwise a segment equal to a GIT_DIR_NAMES name (a .git folder, or a .git pointer file) is "ask";
    otherwise a last segment in HARNESS_ASK_NAMES_ANY_DEPTH is "ask" and one in HARNESS_NAMES_ANY_DEPTH is "deny". Under
    HARNESS_SCRATCH_PREFIX (work/tmp/) the folder names in HARNESS_SCRATCH_DIR_NAMES do not count as containing folders,
    while the file names keep their class and a last segment ".git" (a pointer file) asks. Paths under
    HARNESS_EXEMPT_PREFIXES, and paths that leave the project ("..", which the outside-path rules judge), are None. Case
    is folded, as in `_is_harness`."""
    low = rel.replace("\\", "/").lower()  # str: "/" separators, lower case.
    if not low or low.startswith(HARNESS_EXEMPT_PREFIXES) or low == ".." or low.startswith("../"):
        return None
    parts = [part for part in low.split("/") if part and part != "."]  # list[str]: the path's segments.
    if not parts:  # The project root itself.
        return None
    # bool: inside the session scratch, where the harness and git folder names do not count as containing folders.
    in_scratch = (low + "/").startswith(HARNESS_SCRATCH_PREFIX)
    exempt = HARNESS_SCRATCH_DIR_NAMES if in_scratch else set()  # set[str]: folder names that do not count here.
    if any(part in HARNESS_DIR_NAMES - exempt for part in parts):
        return "deny"
    if any(part in GIT_DIR_NAMES - exempt for part in parts):
        return "ask"  # R6: a .git folder's content (or a pointer file) - git-related, so the user confirms.
    # A path ending in ".git" in the scratch is a sub-module's or work tree's pointer file (or the folder entry
    # itself), not the content of an exempt folder: git-related, so it asks as a .git path elsewhere does.
    if in_scratch and parts[-1] == ".git":
        return "ask"
    if parts[-1] in HARNESS_ASK_NAMES_ANY_DEPTH:
        return "ask"
    if parts[-1] in HARNESS_NAMES_ANY_DEPTH:
        return "deny"
    return None


def _is_git_path(rel: str) -> bool:
    """True when a project-relative path (str) is git-related for R6: inside a .git folder (or a .git pointer file)
    or a .gitmodules file, at any depth. Used to word the confirmation; the class comes from `_harness_class`."""
    parts = [part for part in rel.replace("\\", "/").lower().split("/") if part and part != "."]  # list[str].
    return any(part in GIT_DIR_NAMES for part in parts) or bool(parts and parts[-1] in GIT_FILE_NAMES)


def _stricter(first: str | None, second: str | None) -> str | None:
    """The stricter of two `_harness_class` results: "deny" over "ask" over None."""
    order = {None: 0, "ask": 1, "deny": 2}  # dict: rank of each class.
    return first if order[first] >= order[second] else second


def _path_harness_class(path: str, base: str | None = None) -> tuple[str | None, str]:
    """Returns (class, project-relative path shown in messages). The resolved path (links followed) decides as it does for
    every other rule, so a link to a harness file is the harness file; the lexical path (the name as written, links not
    followed) is judged too, so a link named like a harness path - `lib/.claude` pointing into the exempt scratch, say -
    is not let through by its target. A form that is outside the project counts for neither (the outside-path rules
    judge it); base is the folder a relative path is taken from (None = TOOL_CWD)."""
    result: str | None = None  # The stricter class so far.
    shown = ""  # str: the project-relative path of the form that gave the class.
    for resolve in (True, False):
        abs_path = _to_abs(path, resolve=resolve, base=base)  # str | None: resolved or lexical absolute path.
        if abs_path is None or not _inside(abs_path):
            continue
        rel = _rel(abs_path)  # str: project-relative, "/" separators.
        found = _harness_class(rel)  # str | None: this form's class.
        if _stricter(result, found) != result:
            result, shown = found, rel
    return result, shown


def _harness_rule_note(rel: str) -> str:
    """The rule tag added to a message about a nested or git-related harness path (root files keep their message)."""
    if _is_git_path(rel):
        # R6: git-related paths ask; the tag names what such a write can do.
        return (" (R6, git-related path: writes into .git/ or .gitmodules ask instead of being denied. "
                ".git/hooks/ and .git/config can make Git run programs on later git commands; approve only a change "
                "you asked for.)")
    if _is_harness(rel):
        return ""
    # The tag names the rule, so a refused or asked write explains itself without the reader opening this file.
    return (" (R4 at any depth: CLAUDE.md, AGENTS.md, GEMINI.md and CLAUDE.local.md ask; AGENT_ADVISOR.md, .mcp.json "
            "and .claude/, .agents/, .codex/, .gemini/ are denied; under work/tmp/ the content of those folders and "
            "of .git/ is exempt)")


def _is_code(rel: str) -> bool:
    low = rel.lower()
    return low in CODE_FILES or low.startswith(CODE_PREFIXES)


def _session_state_path(data: dict) -> str | None:
    sid = str(data.get("session_id") or "").strip()
    if not sid or not re.match(r"^[A-Za-z0-9_\-]+$", sid):
        return None
    return os.path.join(STATE_DIR, sid + ".paths")


def _state_add(data: dict, rel: str) -> None:
    path = _session_state_path(data)
    if path is None:
        return
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(rel + "\n")
    except Exception:  # pylint:disable=broad-except
        pass


def _state_read(data: dict) -> list[str]:
    path = _session_state_path(data)
    if path is None or not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return [line.strip() for line in fh if line.strip()]
    except Exception:  # pylint:disable=broad-except
        return []


# --------------------------------------------------------------------------------------------
# Shared file checks
# --------------------------------------------------------------------------------------------
def _check_file_common(file_path: str, verb: str) -> str:
    """Rules 1-3 for a single path. Returns the project-relative path (deny exits)."""
    if ENV_FILE_RE.search(file_path):
        _deny("Cannot %s .env files. Credentials are never accessed by an agent "
              "(including example files)." % verb)
    if SECRETS_RE.search(file_path):
        _deny("Cannot %s anything under a secrets/ directory." % verb)
    abs_path = _to_abs(file_path)
    if abs_path is None:
        return file_path
    if not _inside(abs_path):
        # The user-level Claude folder is the one allowed outside location (see _check_claude_home).
        if _in_claude_home(abs_path):
            return _check_claude_home(abs_path, verb)
        _deny("Cannot %s outside the project directory (%s). Rule 1: work only inside the "
              "current working folder." % (verb, PROJECT))
    # A harmless-looking in-root link must not alias a forbidden secret path.
    if ENV_FILE_RE.search(abs_path) or SECRETS_RE.search(abs_path):
        _deny("Resolved path targets a prohibited environment file or secrets directory.")
    return _rel(abs_path)


# --------------------------------------------------------------------------------------------
# PreToolUse: Read | Glob | Grep
# --------------------------------------------------------------------------------------------
def pre_read(data: dict) -> None:
    tool_input = data.get("tool_input") or {}
    for key in ("file_path", "path", "notebook_path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            _check_file_common(value, "read")
    pattern = tool_input.get("pattern")
    if isinstance(pattern, str) and ENV_FILE_RE.search(pattern):
        _deny("Cannot search for .env files.")
    sys.exit(0)


# --------------------------------------------------------------------------------------------
# PreToolUse: Write | Edit | MultiEdit | NotebookEdit
# --------------------------------------------------------------------------------------------
def pre_write(data: dict) -> None:
    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or tool_input.get("path")
    if not isinstance(file_path, str) or not file_path.strip():
        sys.exit(0)
    rel = _check_file_common(file_path, "write")
    low = rel.lower()

    # R5 advisor role scope
    if ROLE == "ADVISOR":
        if not low.startswith(ADVISOR_DIR + "/"):
            _deny("This session is an ADVISOR (FINDSEE_AGENT_ROLE=ADVISOR). Write scope is %s/ only "
                  "(advice.md, analysis.md, reports/, memory/, tmp/). Point code or config "
                  "changes to a MAIN agent through a ledger entry." % ADVISOR_DIR)

    # R4 harness files. CLAUDE.md and AGENTS.md are confirmed by the user per edit (HARNESS_ASK_FILES); that
    # confirmation is raised only after the artefact and secret-content denials below, so a write that must be denied is
    # never offered for approval. Every other harness file is denied as before. The class is decided at any depth, on
    # the resolved path and on the path as written (`_path_harness_class`); the root's files keep their classes and
    # messages. `harness_rel` is the form that decided, shown in the message.
    harness_ask = False  # True when this write is a confirmable CLAUDE.md / AGENTS.md / CLAUDE.local.md edit.
    harness_cls, harness_rel = _path_harness_class(file_path)  # (str | None, str): class and the path it came from.
    if rel.startswith("~claude/"):  # This project's user-level folder: its own rules ran.
        harness_cls = None
    if harness_cls is not None and ROLE == "ADVISOR":
        # An ADVISOR is denied on every harness file; its scope check denies the root's, and this denies a harness name
        # inside advisor/claude/ itself, whatever FINDSEE_ALLOW_HARNESS_EDIT says.
        _deny("%s is a role/harness or git-related file owned by the user; an ADVISOR proposes such changes "
              "through a ledger entry.%s" % (harness_rel, _harness_rule_note(harness_rel)))
    if harness_cls is not None and not HARNESS_EDIT:
        if harness_cls == "ask":
            harness_ask = True
        else:
            _deny("%s is a role/harness file owned by the user. Propose the change in chat or as a patch "
                  "the user applies; the user re-launches with FINDSEE_ALLOW_HARNESS_EDIT=1 to permit an "
                  "explicitly requested edit.%s" % (harness_rel, _harness_rule_note(harness_rel)))

    # R7 artefacts
    if low.startswith(ARTEFACT_PREFIXES) or ARTEFACT_EXT_RE.search(low):
        if not low.startswith("docs/") and not low.startswith("advisor/"):
            _deny("%s looks like a model/data artefact (weights, arrays, images, audio, video). Artefacts are "
                  "produced by the tools that own them (downloads, Ultralytics, eval/ scripts), never written by "
                  "hand; never overwrite downloaded or trained weights." % rel)

    # Secrets in content
    content = ""
    for key in ("content", "new_string", "new_str", "new_source"):
        value = tool_input.get(key)
        if isinstance(value, str):
            content += value + "\n"
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for edit in edits:
            if isinstance(edit, dict) and isinstance(edit.get("new_string"), str):
                content += edit["new_string"] + "\n"
    if content and SECRET_CONTENT_RE.search(content):
        _deny("Hard-coded credential detected in the content. Read secrets from environment "
              "variables at runtime; never write them into files.")

    # R4 / R6 confirmation (decided above), now that every deny check has passed: an entry file (CLAUDE.md,
    # AGENTS.md, GEMINI.md, CLAUDE.local.md) or a git-related path (.git/, .gitmodules).
    if harness_ask:
        kind = ("a git-related role/harness file owned by the user" if _is_git_path(harness_rel)
                else "a role/harness file owned by the user")  # str.
        _ask("%s is %s. Approve only an edit you asked for in this session; refuse to leave the file unchanged.%s"
             % (harness_rel, kind, _harness_rule_note(harness_rel)))

    # R7: data/ holds photos and recordings of real people - confirm rather than write silently.
    if low.startswith(ASK_PREFIXES):
        _ask("%s is under data/, which holds test photos and voice recordings of real people. Confirm the data is "
             "consented and belongs in the project (docs/project/DATA_POLICY.md); prefer a manifest or a README "
             "change over adding personal data." % rel)
    sys.exit(0)


# --------------------------------------------------------------------------------------------
# PreToolUse: Bash
# --------------------------------------------------------------------------------------------
# `~` is in the look-behind set so the tail of a `~/...` path (matched whole by _HOME_RE) is not also
# taken as a separate absolute path: `~/.claude/x` must not yield a second candidate `/.claude/x`.
_POSIX_ABS_RE = re.compile(r"(?<![\w:./\\\-~])(/(?:[\w.\-%$]+/?)+)")
_WIN_ABS_RE = re.compile(r"(?<![\w])([A-Za-z]:[\\/][^\s'\"<>|;&]*)")
_HOME_RE = re.compile(r"(?<![\w])(~[\\/][^\s'\"<>|;&]*|~$)")
_PARENT_RE = re.compile(r"(?<![\w.])(\.\.(?:[\\/][^\s'\"<>|;&]*)?)")
# interpreter launches that must run inside the project venv (critical instruction 3)
_PY_INVOKE_RE = re.compile(r"(^|[\s;&|(`])(python[0-9.]*|pythonw|pytest|py|streamlit|gradio|"
                           r"(eval|scripts)[\\/][\w\-]+\.py)(\.exe)?(\s|$)", re.I)
# ways a command can pin the env explicitly even when the shell has not activated it
_VENV_PINNED_RE = re.compile(r"(conda\s+run\s+(-n|--name)\s+" + _ENV_ALT + r"\b|"
                             r"conda\s+activate\s+" + _ENV_ALT + r"\b|"
                             r"envs[\\/]" + _ENV_ALT + r"[\\/]|"
                             # The project's own venv, by its interpreter path (POSIX bin/, Windows Scripts\),
                             # relative to the root as the outside-path rules require, or through `uv run`, which
                             # runs in the project's .venv.
                             r"(^|[\s;&|(\"'])(\.[\\/])?\.venv[\\/](bin|Scripts)[\\/]|"
                             r"(^|[\s;&|(])uv\s+run\b)", re.I)
_OUTSIDE_VARS_RE = re.compile(r"(\$HOME\b|\$env:(USERPROFILE|APPDATA|LOCALAPPDATA|HOMEPATH|TEMP|TMP)\b|"
                              r"%(USERPROFILE|APPDATA|LOCALAPPDATA|HOMEPATH|TEMP|TMP)%|\$\{HOME\})", re.I)

# The one recognizer of a git command name, shared by every git rule. Two forms of the same recognizer:
# - text (regex fragment, used by _DENY_PATTERNS, _ASK_PATTERNS and _ADVISOR_BASH_DENY, all matched with re.I): `git` or
#   `git.exe` at a word start - also the end of a path (`/usr/bin/git`, `./tools/git.exe`, an escaped-space path
#   `/mnt/c/Program\ Files/Git/cmd/git.exe`) - or, followed by a closing quote, a quoted path or a quoted `git.exe`
#   (`"/mnt/c/Program Files/Git/cmd/git.exe"`, `"git.exe"`). A quoted bare `"git"` is not read as a command name: a grep
#   pattern such as `grep -n "git" f` would otherwise become an ADVISOR git command. Every text the old `\bgit` matched
#   is still matched the same way (the first alternative without `.exe` is exactly `\bgit`), so no verdict of an earlier
#   rule moves except for these spellings. The caller appends the rest (`\s+push\b`, ...).
_GIT_NAME_RE = r"(?:\bgit(?:\.exe)?|(?<=[\\/])git(?:\.exe)?[\"']|\bgit\.exe[\"'])"
# - word (a command word with its quotes removed, as the shell parsers below see it): the last path segment is `git` or
#   `git.exe`, case folded ("\\" read as "/"). Used by `_git_invocations`, so the `git config` write rule and the
#   one-off rules read the same names.
_GIT_NAME_WORD_RE = re.compile(r"^git(?:\.exe)?$", re.I)


def _is_git_word(word: str) -> bool:
    """True when a command word (str, quotes removed) names git: `git` / `git.exe`, any case, with or without a path."""
    return _GIT_NAME_WORD_RE.match(os.path.basename(word.replace("\\", "/"))) is not None


# The reasons of the destructive rules below, named once, because each rule is now judged twice - by its text pattern in
# _DENY_PATTERNS (unchanged, first) and by the word rules of `_destructive_command` (each simple command's words) - and
# both must give the same reason. The texts are the reasons the patterns always had, byte for byte.
_REASON_RM = "Recursive rm is not allowed; delete specific files only, and never models/ or work/results/."  # str.
_REASON_RMDIR = "Recursive directory removal is not allowed."  # str: rmdir / rd with /s (cmd) or -r.
_REASON_REMOVE_ITEM = "Recursive Remove-Item is not allowed."  # str: PowerShell's Remove-Item (and its alias ri).
_REASON_DEL = "Recursive/quiet del is not allowed."  # str: cmd's del / erase with /s or /q.
# R6: the git reasons are confirmations, not refusals. Each says what the command does to the shared repository so the
# user can approve or refuse it.
_REASON_PUSH = ("git push is the user's call. It publishes commits to the remote: approve only a push you asked "
                "for (R6).")  # str: git push.
# str: git pull / merge / rebase / cherry-pick / fetch --prune.
_REASON_MERGE = ("No merges/pulls/rebases without your approval (R6): git pull/merge/rebase/cherry-pick (or fetch "
                 "--prune) rewrites the shared working tree or its branches, which other agents may be using.")
# str: git reset --hard / --merge.
_REASON_RESET = ("git reset --hard destroys uncommitted work (--merge too), possibly another agent's: approve with "
                 "care (R6).")
# str: git clean / stash / filter-branch / -repo.
_REASON_TREE = ("Working-tree-altering git commands (clean/stash/filter-branch/filter-repo) remove or rewrite files "
                "or history: approve only if you asked for it (R6).")
# str: git checkout / restore / switch without a new-branch option.
_REASON_CHECKOUT = ("git checkout/restore/switch alter the shared working tree (another agent may have edits). "
                    "Creating a new branch (-b/-c) needs no approval; approve a switch or restore you asked for (R6).")
# str: branch / tag deletion, reflog expire, gc --prune, update-ref -d.
_REASON_REFS = ("Destructive git ref operations (branch/tag delete, reflog expire, gc --prune, update-ref -d) need "
                "your approval (R6).")
# str: git -C / --git-dir / --work-tree.
_REASON_GIT_DIR = ("git must run on this repository only. This command points it at another repository or work "
                   "tree (-C / --git-dir / --work-tree / GIT_DIR / GIT_WORK_TREE): approve only if you asked for it "
                   "(R6); paths outside the project stay denied.")

_DENY_PATTERNS: list[tuple[str, str]] = [
    # GPU resets / system
    (r"nvidia-smi\b.*(\s-r\b|--gpu-reset|\s-c\s|--compute-mode)", "No GPU resets or mode changes."),
    (r"(^|[\s;&|])(shutdown|reboot|Restart-Computer|Stop-Computer|diskpart|format)\b", "System commands are out of scope."),
    (r"(^|[\s;&|])(sudo|runas)\b", "No privilege escalation."),
    (r"chmod\s+(-R\s+)?777|icacls\b.*\/grant\b", "No permission blow-ups."),
    # destructive file operations. The reasons are the _REASON_* names above (same texts); each pattern is unchanged,
    # and the word rules of `_destructive_command` see the spellings the patterns miss.
    (r"(^|[\s;&|])rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r|-r\b|-R\b|--recursive)", _REASON_RM),
    (r"(^|[\s;&|])(rmdir|rd)\s+(/s|-r)", _REASON_RMDIR),
    (r"Remove-Item\b.*(-Recurse|-r\b)", _REASON_REMOVE_ITEM),
    (r"(^|[\s;&|])del\s+.*(/s|/q)", _REASON_DEL),
    # environment
    (r"(^|[\s;&|])(pip[0-9.]*|python[0-9.]*\s+-m\s+pip|uv\s+pip|pipx)\s+(install|uninstall|download)\b", "Package changes are the user's: tell them exactly what to run and why (conda env `findsee` or the project's `.venv`; docs/project/ENVIRONMENT.md)."),
    (r"(^|[\s;&|])uv\s+(add|remove|sync|lock)\b", "Package changes are the user's: tell them exactly what to run and why (docs/project/ENVIRONMENT.md)."),
    (r"(^|[\s;&|])(conda|mamba|micromamba)\s+(install|remove|uninstall|update|upgrade|create|env)\b", "Conda environment changes are the user's."),
    (r"(^|[\s;&|])(poetry\s+add|npm\s+install\s+-g)\b", "Package changes are the user's."),
    (r"python[0-9.]*(\.exe)?\s+(\S*[\\/])?(setup\.py|update_deps\.py)\b", "setup.py / update_deps.py install packages; the user runs them."),
    # remote code execution
    (r"(curl|wget|Invoke-WebRequest|iwr|irm|Invoke-RestMethod)\b.*\|\s*(bash|sh|zsh|iex|Invoke-Expression|python)", "Piping downloads into an interpreter is not allowed."),
    (r"\b(iex|Invoke-Expression)\s*\(?\s*\(?\s*(New-Object\s+Net\.WebClient|iwr|irm|Invoke)", "Remote code execution is not allowed."),
]
# Each begins with the shared command-name recognizer _GIT_NAME_RE (`git` / `git.exe`, behind a path or quoted); the
# patterns are unchanged, and the word rules of `_destructive_command(kind="git")`, `_forced_branch_creation` and
# `_git_word_rules` see the spellings the patterns miss. Judged after every non-git deny check (see `_pre_bash_checks`).
_GIT_ASK_PATTERNS: list[tuple[str, str]] = [
    (_GIT_NAME_RE + r"\s+push\b", _REASON_PUSH),
    (_GIT_NAME_RE + r"\s+(pull|merge|rebase|fetch\s+.*--prune|cherry-pick)\b", _REASON_MERGE),
    (_GIT_NAME_RE + r"\s+reset\s+(--hard|--merge)\b", _REASON_RESET),
    (_GIT_NAME_RE + r"\s+(clean|stash|filter-branch|filter-repo)\b", _REASON_TREE),
    (_GIT_NAME_RE + r"\s+(checkout|restore|switch)\b(?!.*\s-b\b)(?!.*\s-c\b)(?!.*--orphan)", _REASON_CHECKOUT),
    (_GIT_NAME_RE + r"\s+(branch\s+-[dD]|tag\s+-d|reflog\s+expire|gc\s+--prune|update-ref\s+-d)\b", _REASON_REFS),
    (_GIT_NAME_RE + r"\s+(-C|--git-dir|--work-tree)\s", _REASON_GIT_DIR),
]
_ASK_PATTERNS: list[tuple[str, str]] = [
    # Process kills ask instead of deny. The rule of CLAUDE.md 5.7 still applies: only a positively identified own
    # process (PID plus start time), never the other agent's run or a live server; the confirmation makes that the
    # user's call each time.
    (r"(^|[\s;&|])(taskkill|Stop-Process|pkill|killall)\b", "Process kill requested. Confirm the target is "
     "yours (PID and start time verified) and not the other agent's run or a live server."),
    (r"(^|[\s;&|])kill\s+(-\S+\s+)?\d+", "Process kill requested. Confirm the PID is your own verified "
     "process, not the other agent's run or a live server."),
    (r"(^|[\s;&|])(curl|wget|Invoke-WebRequest|iwr|irm|Invoke-RestMethod|Start-BitsTransfer)\b", "Network download from an agent session. Model weights are fetched by their libraries (Ultralytics, Whisper, Hugging Face) into models/ or .cache/; confirm this download is intended."),
    # The shared git command-name recognizer (was `\bgit`), so `git.exe commit` asks as `git commit` does.
    (_GIT_NAME_RE + r"\s+commit\b",
     "Commits are normally the user's call; confirm the user asked for this commit in this session (R6)."),
]
_CRED_RE = re.compile(
    r"(\$env:\w*(KEY|SECRET|TOKEN|PASS)\w*|%\w*(KEY|SECRET|TOKEN|PASS)\w*%|\$\{?\w*(KEY|SECRET|TOKEN|PASS)\w*\}?|"
    r"(printenv|Get-ChildItem\s+Env|gci\s+Env|Get-Item\s+Env)|"
    r"\b(echo|printf|env|set|type|cat|Get-Content|gc)\b[^|]*\b\w*(API_KEY|SECRET|TOKEN|PASSPHRASE|PASSWORD)\w*|"
    r"os\.environ\b[^\n]*(KEY|SECRET|TOKEN|PASS))", re.I)
# read-only process / GPU inspection an ADVISOR may always run, even when its arguments name a project tool
_ADVISOR_READONLY_RE = re.compile(r"^(pgrep|ps|pstree|nvidia-smi|top|htop|free|df|uptime|Get-CimInstance|tasklist)\b", re.I)
# R5: what an ADVISOR never runs - the app, the tests, the evaluation harness, helper scripts and the package (by
# mention: a path under eval/ or scripts/, the package module, a test runner or a UI server).
_ADVISOR_BASH_DENY = re.compile(
    r"(pytest|streamlit|gradio|\bmain\.py|\bapp\.py|setup\.py|(^|[\s;&|(\"'])(eval|scripts)[\\/]|"
    r"-m\s+findsee\b)", re.I)
# R5 / R6: an ADVISOR's mutating git (anything but status / diff / log / show / rev-parse / ls-files / blame) ASKS
# instead of being denied, as every other git rule does. The shared recognizer _GIT_NAME_RE reads `git` and `git.exe`
# alike.
_ADVISOR_GIT_RE = re.compile(_GIT_NAME_RE + r"\s+(?!(status|diff|log|show|rev-parse|ls-files|blame)\b)", re.I)


def _cmd_tokens(command: str) -> list[str]:
    try:
        return [tok.strip("\"'") for tok in shlex.split(command.replace("\\", "\\\\"), posix=True)]
    except Exception:  # pylint:disable=broad-except
        return [tok.strip("\"'") for tok in command.split()]


def _check_path_candidates(command: str) -> None:
    """Rule 1 for shell commands: any absolute / home / parent path must resolve inside the project, or
    inside this project's own folder in the user-level Claude folder (CLAUDE_HOME_OWN; never the
    credential store). `cd` / `pushd` still may not leave the project (checked last): every later
    relative path is judged from the project root."""
    # Do not exempt /tmp, system trees, executables-as-data or installed conda package sources.
    candidates: list[str] = []
    for regex in (_WIN_ABS_RE, _HOME_RE, _PARENT_RE, _POSIX_ABS_RE):
        candidates.extend(match.group(1) for match in regex.finditer(command))
    for cand in candidates:
        raw = cand.rstrip(";&|,)")
        if "://" in raw:
            continue
        if raw == "/dev/null":
            continue                                    # is a sink, not a filesystem location
        if re.match(r"^/[A-Za-z]{1,2}$", raw):            # cmd/PowerShell switches: /s /d /i /si
            continue
        if "%" in raw or "$" in raw:                        # unresolved variables: judged below
            continue
        if re.match(r"^[A-Za-z]:[\\/]", raw) and os.name != "nt":
            _deny("`%s` is a Windows absolute path outside this (non-Windows) project directory." % raw)
        abs_path = _to_abs(raw)
        if abs_path is None:
            continue
        if not _inside(abs_path) and _in_claude_home(abs_path):
            # The user-level Claude folder. A shell command can read or write, and the hook cannot tell which, so a
            # shell may name only this project's own folder there (never the credential store); the rest of the folder
            # is read with Read / Glob / Grep.
            rel = _claude_home_rel(abs_path)  # Relative to CLAUDE_HOME, lower case.
            if CLAUDE_HOME_SECRET_RE.search(rel):
                _deny("`%s` is the Claude Code credential store. Credentials are never read, copied or "
                      "edited by an agent." % raw)
            if not (rel + "/").startswith(CLAUDE_HOME_OWN):
                _deny("`%s`: shell commands may use only this project's own folder in the user-level "
                      "Claude folder (%s). Read other parts of it with the Read / Glob / Grep tools."
                      % (raw, CLAUDE_HOME_OWN_PATH))
            continue
        if not _inside(abs_path):
            _deny("`%s` resolves outside the project directory. Rule 1: all reads and writes stay "
                  "inside the current working folder (%s)." % (raw, PROJECT))
    if re.search(r"(^|[\s;&|])(ls|dir|tree|du|find|Get-ChildItem|gci|cd|pushd|rm|cat|type|Get-Item|"
                 r"Get-Content|Set-Location|sl)\b(\s+-\S+)*\s+[/\\](\s|$)", command, re.I):
        _deny("A bare `/` or `\\` (filesystem root) is outside the project directory.")
    if _OUTSIDE_VARS_RE.search(command):
        _deny("Home / profile / temp environment variables point outside the project. Use paths "
              "inside the working folder.")
    for match in re.finditer(r"(?:^|[\s;&|])(cd|pushd|Set-Location|sl|chdir)\s+(?:/d\s+)?(\S+)", command, re.I):
        target = match.group(2).strip("\"'")
        if target in ("-", "."):
            continue
        abs_path = _to_abs(target)
        if abs_path is not None and not _inside(abs_path):
            _deny("cd/pushd to `%s` leaves the project directory." % target)


# Shell writes by path to a harness path. A heuristic over the command text, not a parser: it sees a target only where
# the command names it literally (see `_shell_write_targets`). Command separators: "||", "&&", ";", a newline, a "|" not
# following ">" (">|" is a redirect), and an "&" that is not part of a redirect ("2>&1", "&>file", "<&3").
_SHELL_SEP_RE = re.compile(r"\|\||&&|;|\n|(?<!>)\||(?<![<>])&(?![>&])")
# Output redirects ">", ">>", ">|", "2>", "&>": group 1 is the target word; a "&1"-style duplication has no target
# because "&" cannot start it.
_REDIRECT_OUT_RE = re.compile(r"(?:\d|&)?>{1,2}\|?\s*([^\s|&;<>()]+)")
# Input redirects and heredoc markers ("< f", "<<EOF", "<<<word"), removed before the words are read.
_REDIRECT_IN_RE = re.compile(r"\d?<{1,3}-?\s*[^\s|&;<>()]+")
# Words that run the next word as the command (an assignment "X=y" is skipped as well).
_SHELL_PREFIX_WORDS = {"command", "builtin", "exec", "nohup", "time", "env", "nice"}
# Commands whose every operand is written, created, moved away or removed.
_WRITE_ALL_OPERANDS = {"tee", "touch", "rm", "unlink", "truncate", "mkdir", "rmdir", "chmod", "chown", "shred",
                       "mv", "move", "del", "erase", "set-content", "add-content", "out-file", "new-item",
                       "remove-item", "clear-content", "move-item"}
# Commands whose last operand (or the -t / --target-directory / -Destination value) is the written target.
_WRITE_LAST_OPERAND = {"cp", "ln", "install", "rsync", "copy", "copy-item"}
# Options whose next word is the target folder of a _WRITE_LAST_OPERAND command (lower case).
_TARGET_OPTIONS = {"-t", "--target-directory", "-destination"}
# The folder-changing commands followed within one command line.
_CD_WORDS = {"cd", "pushd", "set-location", "sl", "chdir"}


def _shell_write_targets(command: str) -> list[tuple[str, str]]:
    """The literal write targets of a shell command, as (word, folder it is relative to) pairs.

    Seen: output redirects (in each simple command and, as a fallback for `bash -c "..."` text, anywhere in the line),
    the operands of the commands in _WRITE_ALL_OPERANDS, the last operand or -t value of _WRITE_LAST_OPERAND, `dd of=`,
    and `sed -i` / `perl -i` operands. A `cd` earlier in the same line moves the folder later relative words are taken
    from. Not seen: what a program writes by itself (Python, git, a script), paths built from variables, globs or
    command substitution, and the commands an `xargs` / `find -exec` / `bash -c` runs (redirects aside). The targets of
    the word reader `_word_write_targets` are added at the end - each simple command read as the shell reads its words,
    which sees `>&file`, prefix words' options, timeout / xargs / stdbuf, sub-shells and groups, substitutions, eval,
    `bash -c`, an attached / clustered `-t`, a folder destination, `sed -Ei` / `perl -pi` / `--in-place`, quotes and
    backslashes inside a word, and `cd -` / `pushd` / `popd`; this text reader is kept as it was, so every target it saw
    is still judged."""
    targets = [(match.group(1), TOOL_CWD) for match in _REDIRECT_OUT_RE.finditer(command)]  # Whole-line fallback.
    cwd = TOOL_CWD  # str: the folder relative words are taken from; moved by `cd`.
    for segment in _SHELL_SEP_RE.split(command):
        targets += [(match.group(1), cwd) for match in _REDIRECT_OUT_RE.finditer(segment)]
        words = _cmd_tokens(_REDIRECT_IN_RE.sub(" ", _REDIRECT_OUT_RE.sub(" ", segment)))  # list[str]: redirects gone.
        while words and (re.match(r"^[A-Za-z_]\w*=", words[0]) or words[0].lower() in _SHELL_PREFIX_WORDS):
            words = words[1:]  # Drop assignments and prefix words: the next word is the command.
        if not words:
            continue
        name = re.sub(r"\.exe$", "", os.path.basename(words[0].replace("\\", "/")).lower())  # str: command name.
        args = words[1:]  # list[str]: the command's words after its name.
        if name in _CD_WORDS:
            target = next((arg for arg in args if not arg.startswith("-") or arg == "-"), None)  # str | None.
            moved = _to_abs(target, base=cwd) if target and target != "-" else None  # str | None: the new folder.
            if moved is not None and _inside(moved):  # A cd out of the project is denied by the outside-path rule.
                cwd = moved
            continue
        operands: list[str] = []  # Words that are not options.
        flagged: list[str] = []  # Values of the target-folder options.
        options_done = False  # True after "--".
        take_value = False  # True when the previous word was a target-folder option.
        for arg in args:
            if take_value:
                flagged.append(arg)
                take_value = False
            elif not options_done and arg == "--":
                options_done = True
            elif not options_done and arg.startswith("-") and len(arg) > 1:
                low_arg = arg.lower()  # str: the option, case folded (PowerShell options are case-insensitive).
                if low_arg in _TARGET_OPTIONS:
                    take_value = True
                elif low_arg.startswith("--target-directory="):
                    flagged.append(arg.split("=", 1)[1])
            else:
                operands.append(arg)
        if name in _WRITE_ALL_OPERANDS or (name in ("sed", "perl") and any(a.startswith("-i") for a in args)):
            written = operands + flagged  # Every operand is written.
        elif name in _WRITE_LAST_OPERAND:
            written = flagged or operands[-1:]  # The -t folder, else the last operand (the sources are only read).
        elif name == "dd":
            written = [arg[3:] for arg in args if arg.startswith("of=")]  # dd's output file.
        else:
            written = []
        targets += [(word, cwd) for word in written]
    # The word reader's targets are added to this reader's (which is unchanged above, so no target it found is lost):
    # the families of spellings this text reader cannot see (`_word_write_targets`).
    targets += _word_write_targets(command)
    # And the targets judged from the folders the shell may really be in, so a `cd` that may fail, or that runs in a
    # pipeline, a background job, a sub-shell or a substitution, hides nothing.
    targets += [(word, folder) for word, folder, _name in _real_folder_records(command)]
    return targets


def _shell_harness_class(command: str) -> tuple[str | None, str]:
    """A word holding a variable, a glob or a substitution ($ % * ? ` { [) is skipped: it cannot be resolved from the text.
    Targets outside the project are skipped too (the outside-path rules judge them)."""
    result: str | None = None  # str | None: the stricter class so far.
    shown = ""  # str: the project-relative path that gave it.
    for word, cwd in _shell_write_targets(command):
        word = word.strip("\"'").rstrip(";&|,)")  # The bare word.
        if not word or any(ch in word for ch in "$%*?`{["):
            continue
        found, rel = _path_harness_class(word, base=cwd)  # (str | None, str): resolved and lexical forms judged.
        if _stricter(result, found) != result:
            result, shown = found, rel
    return result, shown


# The write forms of `git config` are denied in a shell command. Git writes .git/config (or ~/.gitconfig,
# /etc/gitconfig, a -f file) itself, so the path rules above never see it, and a configuration value can make Git run a
# command later (core.hooksPath, core.fsmonitor, aliases starting with "!", filters, credential helpers). A heuristic
# over the command text, not a parser, as the rest. set[str]: `git config` options that write (the classic option form);
# any one of them makes the command a write.
_GIT_CONFIG_WRITE_OPTIONS = {"--add", "--unset", "--unset-all", "--replace-all", "--rename-section",
                             "--remove-section", "-e", "--edit"}
# set[str]: `git config` options that make the command a read (the classic option form).
_GIT_CONFIG_READ_OPTIONS = {"--get", "--get-all", "--get-regexp", "--get-urlmatch", "-l", "--list", "--get-color",
                            "--get-colorbool"}
# set[str]: the sub-command form of newer Git (`git config set|unset|... <name>`): the write sub-commands.
_GIT_CONFIG_WRITE_COMMANDS = {"set", "unset", "rename-section", "remove-section", "edit"}
# set[str]: the read sub-commands of that form.
_GIT_CONFIG_READ_COMMANDS = {"get", "list"}
# set[str]: `git config` options whose value is the next word when written without "=" (so the value is not counted
# as a name or a value of the configuration entry itself).
_GIT_CONFIG_VALUE_OPTIONS = {"-f", "--file", "--blob", "--type", "--default", "--comment", "--value", "--url"}
# set[str]: git's own options (before the sub-command) whose value is the next word when written without "=".
_GIT_GLOBAL_VALUE_OPTIONS = {"-c", "-C", "--git-dir", "--work-tree", "--namespace", "--config-env", "--super-prefix"}
# set[str]: shell words that put the next word in command position (keywords, grouping) besides _SHELL_PREFIX_WORDS.
_SHELL_LEAD_WORDS = {"if", "then", "elif", "else", "do", "while", "until", "!", "{", "("}
# set[str]: shells whose `-c <script>` argument is itself a command line (judged again, one level deeper).
_SHELL_NAMES = {"bash", "sh", "zsh", "dash", "ksh"}


class _NestedTooDeep(Exception):
    """Raised by a parser of this file that judges nested command lines again (`$(...)`, backticks, `eval`, a shell's `-c`
    script) when the nesting goes past its limit of three levels. Until this step such a parser returned without a
    verdict there, so `eval eval eval eval git config core.hooksPath <path>` passed; `pre_bash` now refuses the line
    (`_deny`), in every role and launch state."""


class _StepBudgetExceeded(Exception):
    """Raised at the entry of one of the three scans `_param_span_end`, `_arith_end` and `_substitution_end` when the
    characters they have walked for this event (`_scan_steps`) are past the event's budget (`_scan_limit`, set by
    `_scan_budget_reset`). Those scans start again at every unclosed `${` / `$(` / `((`, so a crafted line costs up to
    the cube of its length; the budget makes the guard's work linear in the line and refuses the rest, by a count that
    is the same on every machine. Deliberately NOT a ValueError (nor a subclass of one): the readers catch ValueError
    (an unclosed quote) and read on, which would swallow the overrun; this class passes through every such clause to
    `pre_bash`, which refuses the line (`_deny`) in every role and launch state."""


# int: the budget's fixed part, in characters walked by the three scans. 8 times the largest count S of any command line
# under 1,000 characters in the project's corpus, the sweep texts and the self-test's cases, rounded up to a power of
# two: 8 x 3,072 = 24,576 -> 2**15 = 32,768.
_STEP_FLOOR = 2 ** 15
# int: the budget's part per character of the command line.
_STEP_FACTOR = 2 ** 10
_scan_steps = 0  # int: characters the three scans have walked in this event (reset by `_scan_budget_reset`).
_scan_limit = _STEP_FLOOR  # int: this event's budget, `_STEP_FLOOR + _STEP_FACTOR * len(command)`.


def _scan_budget_reset(command: object) -> None:
    """Start the step budget of one event: the counter to zero and the limit to `_STEP_FLOOR + _STEP_FACTOR * len(command)`
    (characters; a command that is not a string counts as empty). Called where `pre_bash` starts - the only hook entry
    that reaches the three scans."""
    global _scan_steps, _scan_limit  # The module's counter and limit: one event per process.
    _scan_steps = 0  # Nothing walked yet in this event.
    _scan_limit = _STEP_FLOOR + _STEP_FACTOR * (len(command) if isinstance(command, str) else 0)  # Linear in n.


def _scan_budget_enter() -> None:
    """The budget's check at the entry of each of the three scans: past the limit, raise `_StepBudgetExceeded`. The
    overshoot is at most one scan (one text's length)."""
    if _scan_steps > _scan_limit:  # Past this event's budget: no further scan starts.
        raise _StepBudgetExceeded()


def _scan_budget_add(text: str, start: int, end: int) -> int:
    """Count one finished scan and return its answer `end` unchanged (int): the distance from `start` to where it stopped -
    `end`, or the text's end when the answer is -1 (no close found) - is added to `_scan_steps`. A nested scan counts
    itself; the caller's distance includes the span it skipped."""
    global _scan_steps  # The module's counter.
    _scan_steps += max(0, (end if end >= 0 else len(text)) - start)  # Characters walked, never negative.
    return end  # The scan's own answer, untouched.


class _TooManyFolders(Exception):
    """Raised by `_folder_set_check` when the set of folders `_real_folder_records` keeps for one point of a line (the
    folders the shell may be in after `cd`s that may have failed) passes `_FOLDER_SET_LIMIT`. Each `cd` to a missing
    folder followed by `;` keeps the folder before beside the new one, so the set doubles per such `cd`. Deliberately
    NOT a ValueError or an OSError (nor a subclass of one): the readers catch those and read on, which would swallow the
    overrun; this class passes through every such clause to `pre_bash`, which refuses the line (`_deny`) in every role
    and launch state with `_REASON_FOLDER_SET`."""


# int: the largest number of folders `_real_folder_records` keeps for one point of a line. Six `cd`s to missing folders
# joined by `;` stay allowed by this bound (64 folders); a seventh is refused.
_FOLDER_SET_LIMIT = 64


def _folder_set_check(folders: list[str]) -> list[str]:
    """Return `folders` (list[str], the folders the shell may be in) unchanged, or raise `_TooManyFolders` when they number
    more than `_FOLDER_SET_LIMIT`. A count, the same on every machine."""
    if len(folders) > _FOLDER_SET_LIMIT:  # Past the bound: no further folder is resolved for this line.
        raise _TooManyFolders()
    return folders  # Within the bound: the set as it was.


# int: the bound on the folder reader's WORK in one event - the sum, over every simple command `_real_folder_records`
# finishes (its own commands, a `cd`, a command with redirects only; every walk of the event: both readings, four walks
# for a MAIN and five for an ADVISOR), of `len(cwds) - 1`, the folders beyond the first it is judged or resolved from.
# The set's bound caps the folders, not the time: six missing `cd`s followed by `cp a b; about 0.14 ms per unit). A line
# judged from one folder adds nothing, whatever its length. Six missing `cd`s and `true` add 960 as MAIN and 1,200 as
# ADVISOR (allowed); `cd <missing>; ` and 200 short commands 1,600 / 2,000 (allowed); six missing `cd`s and `cp a b; ` 8
# times 4,488 / 5,610 (refused). What it does NOT bound: it counts the commands the folder reader FINISHES, once each.
# It does not count the commands such a command runs - a shell's `-c` script, a `find`'s `-exec` list, a script fed to a
# shell, `eval`, a `trap` handler, a `function` / `coproc` body - which `finish` reads and judges again from every
# folder, nor a command's words, which are read from every folder. So with many possible folders such a line is still
# slow: six missing `cd`s, then `bash -c` with 125 / 250 / 500 commands, allowed in 9.16 / 17.83 / 35.56 s (0.10 / 0.17
# / 0.30 s); the `find -exec` form 8.64 / 17.18 / 34.29 s; a fed script 4.63 / 9.10 / 18.16 s; one inner command of
# 2,000 operands 20.05 s and of 8,000 no answer in 60 s (0.36 / 1.43 s); one command of the line with 2,000 operands
# 18.19 s, of 8,000 no answer in 60 s (0.61 / 2.35 s).
_FOLDER_WORK_LIMIT = 4096
_folder_work = 0  # int: this event's folder work so far (reset by `_folder_work_reset` from `pre_bash`).


def _folder_work_reset() -> None:
    """Start the folder-work count of one event: the counter to zero. Called where `pre_bash` starts, beside
    `_scan_budget_reset`."""
    global _folder_work  # The module's counter: one event per process.
    _folder_work = 0  # Nothing judged beyond a first folder yet.


def _folder_work_add(folders: list[str]) -> None:
    """Count one finished command judged from `folders` (list[str]): add `len(folders) - 1` and raise `_TooManyFolders`
    when the event's total passes `_FOLDER_WORK_LIMIT` (the same refusal and reason as the set's)."""
    global _folder_work  # The module's counter.
    _folder_work += max(0, len(folders) - 1)  # The folders beyond the first; one folder adds nothing.
    if _folder_work > _FOLDER_WORK_LIMIT:  # Past the bound: no further command is judged for this line.
        raise _TooManyFolders()


def _git_config_args_write(args: list[str]) -> bool:
    """True when the words after `git config` (list[str]) are a write form.

    A write option anywhere, or a write sub-command first, is a write; a read option or read sub-command is a read;
    otherwise two or more names/values (`git config <name> <value>`) are a write and one name is a read. Options
    with a value (-f FILE, --type T, ...) skip that value; the scope options (--global, --system, --local,
    --worktree, -f) do not change the class, so `--global user.name x` is a write and `--global --list` a read. An
    unknown option counts for neither, which errs towards a write when its value is taken for a name."""
    positional: list[str] = []  # Words that are not options: names, values or a sub-command.
    is_read = False  # True once a read option is seen.
    index = 0  # int: position in args.
    while index < len(args):
        arg = args[index]  # str: the word at this position.
        if arg == "--":  # Everything after is a name or value.
            positional.extend(args[index + 1:])
            break
        if arg.startswith("-") and len(arg) > 1:
            name = arg.split("=", 1)[0]  # str: the option without an "=value" part.
            if name in _GIT_CONFIG_WRITE_OPTIONS:
                return True
            if name in _GIT_CONFIG_READ_OPTIONS:
                is_read = True
            elif name in _GIT_CONFIG_VALUE_OPTIONS and "=" not in arg:
                index += 1  # The next word is this option's value.
        else:
            positional.append(arg)
        index += 1
    if positional and positional[0] in _GIT_CONFIG_WRITE_COMMANDS:
        return True
    if is_read or (positional and positional[0] in _GIT_CONFIG_READ_COMMANDS):
        return False
    return len(positional) >= 2


def _git_invocations(command: str, depth: int = 0):
    """Yield the words (list[str], quotes removed, `git` first) of every git command seen in a shell command, in order.

    Seen: each simple command split at, &&, ||, |, & and newlines; assignments and the prefix words of
    _SHELL_PREFIX_WORDS / _SHELL_LEAD_WORDS before `git` (env, command, nohup, if, a sub-shell's "(", ...); `git.exe`;
    and, judged again up to three levels deep, `$(...)`, `<(...)`, backticks, `eval ...` and the `-c` script of bash /
    sh / zsh / dash / ksh. Inner command lines come first, then `-c` scripts, then the line's own simple commands. Not
    seen: a command run by `xargs`, `find -exec`, `nice -n N`, an alias or a function, a script file, a program (Python
    `subprocess`), and a variable holding `git`."""
    if depth > 3:  # Nested deeper than any form a command is expected to hold: refused.
        raise _NestedTooDeep()
    # list[str]: the inner command lines of substitutions and backticks, each judged on its own.
    inner = re.findall(r"[$<>]\(([^()]*)\)", command) + re.findall(r"`([^`]*)`", command)
    for text in inner:
        yield from _git_invocations(text, depth + 1)
    tokens = _cmd_tokens(command)  # list[str]: the whole line's words, quotes removed.
    # `bash -c "<script>"` (also -lc, -ec ...): judge the script. The loop paired EVERY shell word with every later
    # `-c`, so `bash -c ` written k times made about k * k / 2 calls; the scripts after the FIRST shell word are every
    # script any shell word reaches (each later shell word's are a tail of them), in the same order, so one pass from
    # the first shell word yields the same scripts, the same first one and the same order of first appearances - only
    # the repeats are gone (each caller takes the first match: `_git_config_write`, `_git_oneoff_config`,
    # `_git_oneoff_any`, and `_git_word_rules` returns at the first invocation that breaks a rule).
    first_shell = next((index for index, word in enumerate(tokens)
                        if os.path.basename(word.replace("\\", "/")).lower() in _SHELL_NAMES), None)  # int | None.
    if first_shell is not None:
        for later in range(first_shell + 1, len(tokens) - 1):  # The words after it, as the old loop read them.
            if not re.match(r"^-[A-Za-z]*c[A-Za-z]*$", tokens[later]):
                continue
            yield from _git_invocations(tokens[later + 1], depth + 1)
    for segment in _SHELL_SEP_RE.split(command):
        # list[str]: the simple command's words, a sub-shell's or group's brackets stripped, empty words dropped.
        words = [w for w in (tok.lstrip("({").rstrip(")}") for tok in _cmd_tokens(segment)) if w]
        while words and (re.match(r"^[A-Za-z_]\w*=", words[0]) or words[0].lower() in _SHELL_PREFIX_WORDS
                         or words[0].lower() in _SHELL_LEAD_WORDS or words[0].startswith("-")):
            words = words[1:]  # Assignments, prefix words, keywords and a prefix word's options ("env -i").
        if not words:
            continue
        name = re.sub(r"\.exe$", "", os.path.basename(words[0].replace("\\", "/")).lower())  # str: command name.
        if name == "eval":  # `eval <words>` runs its words as a command line.
            yield from _git_invocations(" ".join(words[1:]), depth + 1)
            continue
        if _is_git_word(words[0]):  # The shared recognizer (`git` / `git.exe`, any case, behind a path).
            yield words


def _git_config_write(command: str) -> str:
    """The first `git config` write form in a shell command (str, the words as written), or "" when there is none.

    The git commands are those `_git_invocations` sees; git's own options before `config` (-c name=value, --no-pager,
    ...) are skipped. Not seen, besides that parser's limits: other Git commands that write configuration as a side
    effect (`git remote add`, `git submodule add`, `git init`, `git clone`, ...) and a variable holding `config`."""
    for words in _git_invocations(command):
        index = 1  # int: position after `git`; git's own options are skipped.
        while index < len(words) and words[index].startswith("-"):
            option = words[index]  # str: one of git's own options.
            index += 2 if option in _GIT_GLOBAL_VALUE_OPTIONS and "=" not in option else 1
        if index < len(words) and words[index] == "config" and _git_config_args_write(words[index + 1:]):
            return " ".join(words)
    return ""


# A one-off configuration value on git's own command line - `git -c <name>[=<value>]` or `--config-env=<name>=<envvar>`
# - whose name makes Git run a program or rewrite a command is denied by name, in every role and launch state (no
# override): core.hooksPath (the folder Git runs hooks from), core.fsmonitor (a monitor command `git status` starts) and
# alias.* (an alias starting with "!" is a shell command). Names are matched case-folded, as Git folds section and key
# names. These three names keep this rule and its message.
_GIT_ONEOFF_RUN_RE = re.compile(r"^(core\.hookspath|core\.fsmonitor|alias\..+)$")


def _git_oneoff_options(command: str):
    """Yield every one-off configuration option on git's command line as (text as written, name case folded).

    The git commands are those `_git_invocations` sees. git's own options before the sub-command are read: `-c
    <name>[=<value>]`, `-c<name>=<value>` (without the space; recalled from Git's source not to be accepted - it is
    judged all the same), `--config-env=<name>=<envvar>` and `--config-env <name>=<envvar>`; any other option is skipped
    with its value. A `-c` / `--config-env` at the end of the line (no value) is yielded with the name "". Not seen,
    besides that parser's limits: an option after the sub-command (`git clone -c` / `--config` writes the new
    repository's configuration; `git commit -c` / `git log -c` are those commands' own options), a value written to a
    configuration file by other means, and the environment forms (judged apart, `_git_config_env_assignment`)."""
    for words in _git_invocations(command):
        index = 1  # int: position after `git`.
        while index < len(words) and words[index].startswith("-"):
            option = words[index]  # str: one of git's own options.
            value = None  # str | None: the "<name>[=<value>]" text this option sets, None for another option.
            step = 1  # int: words this option takes (2 with a separate value).
            if option in ("-c", "--config-env"):
                value = words[index + 1] if index + 1 < len(words) else ""
                step = 2
            elif option.startswith("--config-env="):
                value = option[len("--config-env="):]
            elif option.startswith("-c") and not option.startswith("--"):  # "-c<name>=<value>"; "-C" is not "-c".
                value = option[2:]
            elif option in _GIT_GLOBAL_VALUE_OPTIONS and "=" not in option:
                step = 2  # -C <dir>, --git-dir <dir>, ...: skip the value.
            if value is not None:
                # (str, str): the option as written (with a separate value) and its configuration name, case folded.
                yield option + (" " + value if step == 2 else ""), value.split("=", 1)[0].strip().lower()
            index += step


def _git_oneoff_config(command: str) -> str:
    """The first one-off configuration option naming core.hooksPath, core.fsmonitor or alias.* (str, as written), or "".

    The options `_git_oneoff_options` reads, filtered by _GIT_ONEOFF_RUN_RE; this rule runs before the general one
    (`_git_oneoff_any`), so these three names keep their own message."""
    for text, name in _git_oneoff_options(command):
        if _GIT_ONEOFF_RUN_RE.match(name):
            return text
    return ""


# Every one-off configuration value on git's command line is refused whatever the name, in every role and launch state
# (no override) - the list of names that make Git run a program (core.sshCommand, core.pager, core.editor,
# credential.helper, diff.external, gpg.program, filters, include.path ...) is long and would always be incomplete, and
# no project procedure uses a one-off value. Git also reads one-off configuration from the environment: GIT_CONFIG_COUNT
# with GIT_CONFIG_KEY_<n> / GIT_CONFIG_VALUE_<n>, and GIT_CONFIG_PARAMETERS (what `-c` itself passes to Git's child
# processes); an assignment of one of them on a command line is refused the same way. So is an assignment of
# GIT_CONFIG_GLOBAL or GIT_CONFIG_SYSTEM
# - one rule, two names more, in exactly the forms below: each points Git at another configuration file (in place of the
#   user's or the system's), and that file can set any name a one-off `git -c` could. Other GIT_ variables
#   (GIT_CONFIG_NOSYSTEM, GIT_PAGER, GIT_EDITOR, GIT_SSH_COMMAND, ...) are not part of either decision and keep their
#   verdicts. The variable names, matched on an assignment word "NAME=..." (case folded: native Windows does not tell
#   case apart).
_GIT_CONFIG_ENV_RE = re.compile(r"^GIT_CONFIG_(COUNT|PARAMETERS|GLOBAL|SYSTEM|KEY_\d+|VALUE_\d+)=", re.I)
# PowerShell's form, `$env:NAME = value`, anywhere in the text (the guard also judges the PowerShell tool's commands).
_GIT_CONFIG_PS_ENV_RE = re.compile(r"\$env:(GIT_CONFIG_(?:COUNT|PARAMETERS|GLOBAL|SYSTEM|KEY_\d+|VALUE_\d+))\s*=",
                                   re.I)
# The two configuration-file names inside a hit of either pattern above (the hit as written: "NAME=value" or "$env:NAME
# ="), so the refusal can name the rule that applies.
_GIT_CONFIG_FILE_ENV_RE = re.compile(r"^(?:\$env:)?GIT_CONFIG_(GLOBAL|SYSTEM)\s*=", re.I)
# set[str]: shell built-ins whose operands are assignments that export or declare a variable.
_EXPORT_WORDS = {"export", "declare", "typeset", "local", "readonly"}
# set[str]: `env` options whose value is the next word (`env -u NAME`, `env -C DIR`).
_ENV_VALUE_OPTIONS = {"-u", "--unset", "-C", "--chdir"}


def _git_oneoff_any(command: str) -> str:
    """The first one-off configuration option on git's command line, whatever its name (str, as written), or "".

    Every option `_git_oneoff_options` reads."""
    for text, _name in _git_oneoff_options(command):
        return text
    return ""


def _git_config_env_assignment(command: str, depth: int = 0) -> str:
    """The first assignment of GIT_CONFIG_COUNT / _KEY_<n> / _VALUE_<n> / _PARAMETERS in a command line (str), or "".

    Seen, per simple command (split outside quotes by `_split_unquoted`, so a grep pattern or an echo text holding the
    name is not an assignment): assignments in command position - a prefix before a command (`NAME=v git status`) or a
    bare one (`NAME=v; export NAME`) - also after the prefix words of _SHELL_PREFIX_WORDS / _SHELL_LEAD_WORDS with their
    options (`env NAME=v`, `env -u X NAME=v`, `nohup`, `if`, a sub-shell's "("); the operands of export / declare /
    typeset / local / readonly (`export NAME=v`, `declare -x NAME=v`); PowerShell's `$env:NAME = v`; and, judged again
    up to three levels deep, `$(...)`, `<(...)`, backticks, `eval ...` and the `-c` script of bash / sh / zsh / dash /
    ksh. Not seen: a name built from a variable or a substitution, an assignment made by a script or a program (Python
    `os.environ`, a sourced file), `set` / `setx` of cmd.exe, PowerShell's `Set-Item env:` /
    `[Environment]:SetEnvironmentVariable`, and `xargs` / `find -exec` / `nice -n N` before `env`."""
    if depth > 3:  # Nested deeper than any form a command is expected to hold: refused.
        raise _NestedTooDeep()
    found = _GIT_CONFIG_PS_ENV_RE.search(command)  # re.Match | None: PowerShell's `$env:NAME =` form.
    if found:
        return found.group(0)
    # list[str]: the inner command lines of substitutions and backticks, each judged on its own.
    inner = re.findall(r"[$<>]\(([^()]*)\)", command) + re.findall(r"`([^`]*)`", command)
    for text in inner:
        hit = _git_config_env_assignment(text, depth + 1)  # str: an assignment found inside, or "".
        if hit:
            return hit
    tokens = _cmd_tokens(command)  # list[str]: the whole line's words, quotes removed.
    for index, word in enumerate(tokens):  # `bash -c "<script>"` (also -lc, -ec ...): judge the script.
        if os.path.basename(word.replace("\\", "/")).lower() in _SHELL_NAMES:
            for later in range(index + 1, len(tokens) - 1):
                if re.match(r"^-[A-Za-z]*c[A-Za-z]*$", tokens[later]):
                    hit = _git_config_env_assignment(tokens[later + 1], depth + 1)  # str: a hit in the script.
                    if hit:
                        return hit
    for _sep, segment in _split_unquoted(command):
        # list[str]: the simple command's words, a sub-shell's or group's brackets stripped, empty words dropped.
        words = [w for w in (tok.lstrip("({").rstrip(")}") for tok in _cmd_tokens(segment)) if w]
        index = 0  # int: position in words; walks the words that come before the command itself.
        while index < len(words):
            word = words[index]  # str: one word in command position or before it.
            if _GIT_CONFIG_ENV_RE.match(word):
                return word
            if re.match(r"^[A-Za-z_]\w*=", word) or word.lower() in _SHELL_PREFIX_WORDS \
                    or word.lower() in _SHELL_LEAD_WORDS:
                index += 1  # Another assignment, a prefix word or a keyword: the command comes later.
                continue
            if word.startswith("-") and index > 0:  # A prefix word's option; `env -u NAME` takes a value.
                index += 2 if word in _ENV_VALUE_OPTIONS else 1
                continue
            break
        if index < len(words) and words[index].lower() == "eval":  # `eval <words>` runs its words as a command line.
            hit = _git_config_env_assignment(" ".join(words[index + 1:]), depth + 1)  # str: a hit in the eval text.
            if hit:
                return hit
        if index < len(words) and words[index].lower() in _EXPORT_WORDS:  # export / declare ...: every operand.
            hit = next((w for w in words[index + 1:] if _GIT_CONFIG_ENV_RE.match(w)), "")  # str: the assignment.
            if hit:
                return hit
    return ""


# - the shortest unambiguous abbreviations of the long options the destructive rules read, from each sub-command's own
#   option list: `git reset` has no other option starting `--h`, so `--h` is `--hard` (`--m` is ambiguous between
#   --mixed and --merge, which Git refuses, and refusing it costs nothing); `git branch` / `git tag` have no other
#   `--d...` option; `git gc` no other `--p...`; `git fetch` has --prefetch, --progress, --prune and --prune-tags, so
#   `--pru` is the shortest;
# - git's own options that take the next word as their value and are missing from _GIT_GLOBAL_VALUE_OPTIONS (the
#   installed Git 2.40.1's `git -h` lists none beyond it.
# - an assignment of GIT_DIR or GIT_WORK_TREE - in front of a command, bare, behind env, or exported (export / declare /
#   ...), or PowerShell's `$env:NAME =` - points git at another repository or work tree, as `--git-dir` / `--work-tree`
#   do ("this repository only", _REASON_GIT_DIR). It is refused whether or not git follows on the line (a script started
#   later on the line runs git with it; no project procedure sets them).
_GIT_MORE_VALUE_OPTIONS = {"--attr-source"}  # set[str]: git's own options whose value is the next word.
# re.Pattern: an assignment word of GIT_DIR / GIT_WORK_TREE (case folded: native Windows does not tell case apart).
_GIT_REPO_ENV_RE = re.compile(r"^(GIT_DIR|GIT_WORK_TREE)=", re.I)
# re.Pattern: PowerShell's form `$env:GIT_DIR = ...` anywhere in the text.
_GIT_REPO_PS_ENV_RE = re.compile(r"\$env:(GIT_DIR|GIT_WORK_TREE)\s*=", re.I)


def _git_reread(args: list[str]) -> list[str]:
    """git's words after `git` (list[str]) with every option of _GIT_MORE_VALUE_OPTIONS joined to its value
    (`--attr-source HEAD` -> `--attr-source=HEAD`), so the readers that skip git's own options find the sub-command."""
    out: list[str] = []  # list[str]: the words, re-read.
    index = 0  # int: position in args; only git's own options (before the sub-command) are re-read.
    while index < len(args) and args[index].startswith("-"):
        option = args[index]  # str: one of git's own options.
        if option in _GIT_MORE_VALUE_OPTIONS and index + 1 < len(args):
            out.append(option + "=" + args[index + 1])  # The option and its value as one word.
            index += 2
            continue
        if option in _GIT_GLOBAL_VALUE_OPTIONS and "=" not in option and index + 1 < len(args):
            out += args[index:index + 2]  # An option of the existing set keeps its separate value.
            index += 2
            continue
        out.append(option)
        index += 1
    return out + args[index:]


def _git_abbreviated_destructive(args: list[str]) -> str:
    """The reason (str) of a destructive git rule broken by an abbreviated long option, or "": `reset --h` / `--m...`,
    `branch --d...`, `tag --d...`, `gc --p...`, `fetch --pru...` (see the lengths above). `args` are git's words after
    `git`, git's own options skipped as `_git_destructive` skips them."""
    index = 0  # int: position in args.
    while index < len(args) and args[index].startswith("-"):
        index += 2 if args[index] in _GIT_GLOBAL_VALUE_OPTIONS and "=" not in args[index] else 1
    if index >= len(args):
        return ""
    sub = args[index].lower()  # str: the sub-command, case folded.
    lowered = []  # list[str]: its option words before "--", case folded.
    for arg in args[index + 1:]:
        if arg == "--":
            break
        if arg.startswith("--"):
            lowered.append(arg.lower())
    if sub == "reset" and any(_long_option_prefix(low, ("--hard", "--merge"), 3) for low in lowered):
        return _REASON_RESET
    if sub in ("branch", "tag") and any(_long_option_prefix(low, ("--delete",), 3) for low in lowered):
        return _REASON_REFS
    if sub == "gc" and any(_long_option_prefix(low, ("--prune",), 3) for low in lowered):
        return _REASON_REFS
    if sub == "fetch" and any(_long_option_prefix(low, ("--prune", "--prune-tags"), 5) for low in lowered):
        return _REASON_MERGE
    return ""


def _git_repo_env_assignment(command: str) -> str:
    """The first assignment of GIT_DIR or GIT_WORK_TREE in a command line (str, as written), or "".

    Seen on the word reader's simple commands (`_simple_commands`): an assignment in command position - bare, in front
    of a command, or behind the prefix words of _LAUNCH_PREFIX_WORDS with their options (`env GIT_DIR=x git ...`) - the
    operands of export / declare / typeset / local / readonly, and PowerShell's `$env:NAME =`. A word that is an
    argument of another command (`grep -n "GIT_DIR=" f`, `echo GIT_DIR=x`) is no assignment."""
    found = _GIT_REPO_PS_ENV_RE.search(command)  # re.Match | None: PowerShell's form.
    if found:
        return found.group(0)
    for words, _targets in _simple_commands(command):
        index = 0  # int: position in words; walks the words in front of the command word.
        prefix = ""  # str: the last prefix word passed ("" before any), whose options are skipped.
        while index < len(words):
            word = words[index]  # str: one word in command position or in front of it.
            low = word.lower()  # str: the same, case folded.
            if _GIT_REPO_ENV_RE.match(word):
                return word
            if re.match(r"^[A-Za-z_]\w*=", word) or low in _SHELL_LEAD_WORDS:
                index += 1  # Another assignment or a keyword: the command comes later.
                continue
            if low in _LAUNCH_PREFIX_WORDS:
                prefix, index = low, index + 1  # A prefix word: its options and the command follow.
                continue
            if prefix and word.startswith("-"):  # A prefix word's option, with its value when it takes one.
                index += 2 if "=" not in word and word in _PREFIX_VALUE_OPTIONS.get(prefix, ()) else 1
                continue
            if prefix and re.match(r"^\d+(\.\d+)?[smhd]?$", word):
                index += 1  # A prefix word's number ("timeout 60").
                continue
            break
        if index < len(words) and words[index].lower() in _EXPORT_WORDS:  # export / declare ...: every operand.
            hit = next((w for w in words[index + 1:] if _GIT_REPO_ENV_RE.match(w)), "")  # str: the assignment.
            if hit:
                return hit
    return ""


def _git_word_rules(command: str) -> str:
    """The git commands are those the word reader sees (`_simple_commands`, the prefix words taken off) and, for the two
    configuration rules only, those of `_git_invocations` too. Each has its words re-read (`_git_reread`); a word-reader
    command is judged by the destructive rules of `_git_destructive` and the abbreviations of
    `_git_abbreviated_destructive`; last, an assignment of GIT_DIR / GIT_WORK_TREE."""
    invocations: list[tuple[list[str], bool]] = []  # list[(words, judged by the destructive rules too)].
    for words, _targets in _simple_commands(command):
        bare, _cwd = _strip_command_prefix(words, TOOL_CWD)  # list[str]: from the command word on.
        if bare and _is_git_word(bare[0]):
            invocations.append((bare, True))
    invocations += [(words, False) for words in _git_invocations(command)]
    for words, destructive in invocations:
        args = _git_reread(words[1:])  # list[str]: the words after `git`, value options joined to their values.
        reason = (_git_destructive(args) or _git_abbreviated_destructive(args)) if destructive else ""  # str.
        if reason:
            return reason
        index = 0  # int: position in args; git's own options are read for one-off values and skipped.
        while index < len(args) and args[index].startswith("-"):
            option = args[index]  # str: one of git's own options.
            if option in ("-c", "--config-env") or option.startswith("--config-env=") or (
                    option.startswith("-c") and not option.startswith("--")):
                return ("`%s` gives git a one-off configuration value; names such as core.hooksPath, core.pager, "
                        "credential.helper or an alias make Git run a program. Approve only if you asked for it (R6)."
                        % option)
            index += 2 if option in _GIT_GLOBAL_VALUE_OPTIONS and "=" not in option else 1
        if index < len(args) and args[index] == "config" and _git_config_args_write(args[index + 1:]):
            return ("`%s` changes Git's configuration (hooks path, fsmonitor, aliases and filters can make Git run "
                    "commands). Approve only a configuration change you asked for (R6)." % " ".join(words)[:200])
    assignment = _git_repo_env_assignment(command)  # str: a GIT_DIR / GIT_WORK_TREE assignment, or "".
    if assignment:
        return _REASON_GIT_DIR + (" `%s` points git at another repository or work tree." % assignment[:200])
    return ""


# An ADVISOR session is refused when it *launches* a script that lies under a MAIN session folder - work/claude-main/ or
# work/codex-main/ (MAIN's installer, cleanup, publish and claim tools, a runner's probes). A heuristic over the command
# text, not a parser. A MAIN is not judged by it. tuple[str, ...]: root-relative folder prefixes (lower case,
# "/"-terminated) whose scripts an ADVISOR may not run.
_MAIN_SESSION_PREFIXES = ("work/claude-main/", "work/codex-main/", "work/gemini-main/")
# The dotted module form of the same folders: a hyphenated folder still runs that way, matched case-insensitively.
_MAIN_SESSION_MODULE_RE = re.compile(r"^work\.(claude|codex|gemini)-main(\.|$)", re.I)
# The mention rule itself is unchanged and decides first. tuple[str, ...]: those folders, root-relative, lower case,
# "/"-terminated.
_HARNESS_LAUNCH_PREFIXES = ("eval/", "scripts/", "src/")  # FindSee: the eval harness, helper scripts, the package.
# Their dotted module form, matched case-insensitively.
_HARNESS_MODULE_RE = re.compile(r"^(eval|scripts|src|findsee)(\.|$)", re.I)  # Their module forms, and the package.
# Set[str]: the exempt scripts, root-relative, lower case; set[str]: their module names, lower case. FindSee has no
# mandatory process-check script, so nothing is exempt.
_ADVISOR_EXEMPT_SCRIPTS: set = set()
_ADVISOR_EXEMPT_MODULES: set = set()
# dict[str, tuple]: the folder sets the detector is run for, by kind - "main" and "harness" - each (prefixes, module
# regex).
_LAUNCH_FOLDER_SETS = {"main": (_MAIN_SESSION_PREFIXES, _MAIN_SESSION_MODULE_RE),
                       "harness": (_HARNESS_LAUNCH_PREFIXES, _HARNESS_MODULE_RE)}
# Python spellings (lower case, ".exe" removed before the match): python, python3, python3.13, pythonw, py.
_PYTHON_NAMES_RE = re.compile(r"^(python[0-9.]*|pythonw|py)$")
# set[str]: other interpreters whose first operand is a script file; their inline-code options are below.
_SCRIPT_INTERPRETERS = {"node", "perl", "ruby"}
# set[str]: node / perl / ruby options that give the program inline (then no operand is a script).
_INLINE_CODE_OPTIONS = {"-e", "-E", "--eval", "-p", "--print"}
# set[str]: PowerShell hosts: `-File <script>` runs a script, `-Command <text>` a command line (judged again).
_POWERSHELL_NAMES = {"pwsh", "powershell"}
# set[str]: words that, like _SHELL_PREFIX_WORDS, run a later word as the command; their options and numbers
# ("nice -n 5", "timeout 60") are skipped too.
_LAUNCH_PREFIX_WORDS = _SHELL_PREFIX_WORDS | {"timeout", "xargs", "stdbuf"}
# An input redirect "< file" (not a heredoc "<<", a here-string "<<<", "<(" or "<&"): group 1 is the file.
_REDIRECT_STDIN_RE = re.compile(r"(?<![<&])<(?![<(&])\s*([^\s|&;<>()]+)")
# set[str]: commands whose operands, piped into an interpreter that reads its program from standard input, are the
# program (`cat <script> | python -`).
_PIPE_SOURCE_WORDS = {"cat", "type", "get-content", "gc"}
# `-m <module>` is also resolved against the folder the command runs in and the PYTHONPATH entries written on the
# command line (_module_launch below). frozenset[str]: the standard-library top-level module names of the interpreter
# that runs the guard (`sys.stdlib_module_names`, Python 3.10+; empty before) and its built-in modules. A dotted name
# whose first segment is one of them is never counted, so an ADVISOR's `python -m json.tool <record>` stays allowed even
# from a folder of either kind. On Python 3.8 / 3.9 only the built-in names are known, so such a read from inside those
# folders is refused there (the safe side); from the project root it is not.
_STDLIB_TOP_NAMES = frozenset(getattr(sys, "stdlib_module_names", ())) | frozenset(sys.builtin_module_names)
# An assignment word of PYTHONPATH ("PYTHONPATH=<value>"), case folded as the GIT_CONFIG_ names are (native Windows does
# not tell case apart); group 1 is the value as written (quotes already removed by the shell parser).
_PYTHONPATH_ASSIGN_RE = re.compile(r"^PYTHONPATH=(.*)$", re.I | re.S)


def _split_unquoted(command: str) -> list[tuple[str, str]]:
    """The simple commands of a command line as (separator before it, text) pairs, split outside quotes only.

    Separators as _SHELL_SEP_RE: ";", a newline, "&&", "||", a "|" not after ">" (">|" is a redirect) and an "&" that
    is not part of a redirect ("2>&1", "&>", "<&"). Unlike that regex, a separator inside '...' or "..." or after a
    backslash does not split, so a grep pattern holding "; python work/claude-main/x.py" is not read as a launch. The
    first pair's separator is ""."""
    parts: list[tuple[str, str]] = []  # The pairs found so far.
    sep = ""  # str: the separator before the current simple command.
    start = 0  # int: where the current simple command begins.
    quote = ""  # str: the open quote character, "" outside quotes.
    index = 0  # int: the scan position.
    while index < len(command):
        char = command[index]  # str: the character at the scan position.
        if quote:  # Inside quotes nothing splits; a backslash escapes only inside double quotes.
            if char == "\\" and quote == '"':
                index += 2
                continue
            if char == quote:
                quote = ""
            index += 1
            continue
        if char == "\\":  # An escaped character outside quotes never splits.
            index += 2
            continue
        if char in "'\"":
            quote = char
            index += 1
            continue
        prev = command[index - 1] if index else ""  # str: the character before ("" at the start).
        nxt = command[index + 1] if index + 1 < len(command) else ""  # str: the character after ("" at the end).
        found = ""  # str: the separator at this position, "" for none.
        if command.startswith(("&&", "||"), index):
            found = command[index:index + 2]
        elif char in (";", "\n"):
            found = char
        elif char == "|" and prev != ">":
            found = "|"
        elif char == "&" and prev not in ("<", ">") and nxt not in (">", "&"):
            found = "&"
        if found:
            parts.append((sep, command[start:index]))
            sep, start = found, index + len(found)
            index += len(found)
            continue
        index += 1
    parts.append((sep, command[start:]))
    return parts


def _main_session_path(word: str, base: str, kind: str = "main") -> bool:
    """True when `word` (a script path as written) lies under the folders of `kind` in this project.

    kind "main": work/claude-main/ or work/codex-main/; "harness": eval/, scripts/ or src/ in FindSee, except the exempt
    scripts (none here) (_ADVISOR_EXEMPT_SCRIPTS). Judged on the resolved path (links followed) and on the lexical path
    (as written), taken from `base` when relative, case folded and with "\\" read as "/" (as `_rel` gives it); a form
    outside the project counts for neither (the outside-path rules judge it)."""
    prefixes = _LAUNCH_FOLDER_SETS[kind][0]  # tuple[str, ...]: the folders of this kind.
    word = word.strip("\"'")  # str: the bare word.
    if not word:
        return False
    for resolve in (True, False):
        abs_path = _to_abs(word, resolve=resolve, base=base)  # str | None: resolved or lexical absolute path.
        if abs_path is None or not _inside(abs_path):
            continue
        low = _rel(abs_path).lower()  # str: root-relative, "/" separators, lower case.
        if low.startswith(prefixes) and low not in _ADVISOR_EXEMPT_SCRIPTS:
            return True
    return False


def _pythonpath_entries(value: str) -> list[str]:
    """The entries (list[str], as written, empty ones dropped) of one PYTHONPATH value written on a command line.

    Split at ":" (POSIX) and at ";" (native Windows, inside quotes); a one-letter piece followed by a piece that starts
    with "\\" or "/" is a Windows drive ("C:\\x") and is joined back to it."""
    entries: list[str] = []  # The entries found so far.
    for part in value.split(";"):
        pieces = part.split(":")  # list[str]: the POSIX split; a drive letter is rejoined below.
        index = 0  # int: position in pieces.
        while index < len(pieces):
            piece = pieces[index]  # str: one entry, or a drive letter that belongs to the next piece.
            if len(piece) == 1 and piece.isalpha() and index + 1 < len(pieces) and pieces[index + 1][:1] in ("\\", "/"):
                piece = piece + ":" + pieces[index + 1]  # "C" + ":" + "\\x": a Windows path.
                index += 1
            if piece.strip():
                entries.append(piece.strip())
            index += 1
    return entries


def _folder_hit(abs_path: str, kind: str) -> bool:
    """True when `abs_path` (absolute) is one of the folders of `kind` or lies under one.

    Judged on the resolved path (links followed) and on the lexical path, case folded with "/" separators, as
    `_main_session_path` judges a script; a path outside the project counts for neither."""
    prefixes = _LAUNCH_FOLDER_SETS[kind][0]  # tuple[str, ...]: the folders of this kind, "/"-terminated.
    for resolve in (True, False):
        path = _to_abs(abs_path, resolve=resolve)  # str | None: resolved or lexical absolute path.
        if path is None or not _inside(path):
            continue
        if (_rel(path).lower() + "/").startswith(prefixes):  # The folder itself or anything under it.
            return True
    return False


def _module_launch(module: str, bases: list[str], kind: str) -> bool:
    """True when `python -m <module>` started from one of `bases` would load code from a folder of `kind`.

    Resolution: `bases` are the folder the command runs in (Python's `-m` puts it first on sys.path) and each PYTHONPATH
    entry written on the command line, absolute. Under each base the dotted name is turned into a path segment by
    segment (`a.b` -> <base>/a, then <base>/a/b, which Python loads as a/b.py, a/b/__main__.py or the package folder
    a/b/); the module counts when one of those paths - the first segment's, or a longer one's - is a folder of `kind` or
    lies under one. Judged lexically: whether a file exists does not matter, so a refusal never depends on a file the
    same command line could create first. Never counted: a name whose first segment is a standard-library top-level name
    (_STDLIB_TOP_NAMES: `json.tool` from inside the folders; from the project root such a name lies outside them anyway,
    as an installed module's does), and a name whose `.py` path under that base is an exempt script. A name with an
    empty segment (".x", "a..b") or a path separator is no module Python runs and is not counted here."""
    segments = module.strip("\"'").split(".")  # list[str]: the dotted name's parts.
    if not segments or any(not part or "/" in part or "\\" in part for part in segments):
        return False
    if segments[0] in _STDLIB_TOP_NAMES:  # Exact name (Python's module names are case-sensitive on POSIX).
        return False
    for base in bases:
        target = os.path.join(base, *segments)  # str: <base>/a/b, the module's path without a suffix.
        exempt = _to_abs(target + ".py", resolve=False)  # str | None: the `.py` form, lexical, for the exemption.
        if exempt is not None and _inside(exempt) and _rel(exempt).lower() in _ADVISOR_EXEMPT_SCRIPTS:
            continue  # The process check stays allowed from this base.
        path = base  # str: grows by one segment per step.
        for part in segments:
            path = os.path.join(path, part)
            if _folder_hit(path, kind):
                return True
    return False


def _advisor_launch_words(words: list[str], cwd: str, depth: int, stdin_files: list[str],
                          kind: str = "main", pythonpath: list[str] | None = None) -> tuple[str, str]:
    """`cwd` is the folder relative words are taken from; a `cd` / `pushd` returns the folder it moves to. `stdin_files`
    are the files fed to the command's standard input (`< file`, or the operands of `cat` piped into it); they count
    only for an interpreter given no script operand (it then reads its program from standard input). `kind` names the
    folder set judged (_LAUNCH_FOLDER_SETS: "main" by default, or "harness") and is passed on to every nested judgement.
    `pythonpath` holds the PYTHONPATH values set earlier in the same command line (an `export` / `declare -x` operand or
    a bare assignment); this function appends to it when the simple command is such a statement, and adds the command's
    own prefix assignments (`PYTHONPATH=v cmd`, `env PYTHONPATH=v cmd`) for this command only. `env -C <dir>` /
    `--chdir` runs the rest in that folder; `env -u <name>` skips its value."""
    module_re = _LAUNCH_FOLDER_SETS[kind][1]  # re.Pattern: the dotted module form of this kind's folders.
    carried = pythonpath if pythonpath is not None else []  # list[str]: values from earlier in the line (appended to).
    local = list(carried)  # list[str]: the values that apply to this command (carried + its own prefix assignments).
    own: list[str] = []  # list[str]: this command's own PYTHONPATH assignments (kept for later words if it is bare).
    after_env = False  # bool: the last prefix word dropped was `env` (its -C / -u options take a value).
    # Drop assignments, prefix words with their options and numbers ("nice -n 5", "timeout 60"), keywords and "{}".
    while words and (re.match(r"^[A-Za-z_]\w*=", words[0]) or words[0].lower() in _LAUNCH_PREFIX_WORDS
                     or words[0].lower() in _SHELL_LEAD_WORDS or words[0].startswith("-")
                     or re.match(r"^\d+(\.\d+)?[smhd]?$", words[0]) or words[0] == "{}"):
        word = words[0]  # str: the word being dropped.
        assigned = _PYTHONPATH_ASSIGN_RE.match(word)
        if assigned:
            own.append(assigned.group(1))
            local.append(assigned.group(1))
        if after_env and (word in ("-C", "--chdir") or word.startswith("--chdir=")):
            # `env -C <dir> <command>` runs the command in <dir>; judged there, the line's folder unchanged.
            folder = word.split("=", 1)[1] if "=" in word else (words[1] if len(words) > 1 else "")  # str: <dir>.
            rest = words[1:] if "=" in word else words[2:]  # list[str]: the words after the option and its value.
            moved = _to_abs(folder, base=cwd) if folder else None  # str | None: the folder the command runs in.
            run_cwd = moved if moved is not None and _inside(moved) else cwd  # str: that folder, else the current one.
            return _advisor_launch_words(rest, run_cwd, depth, stdin_files, kind, local)[0], cwd
        if after_env and word in ("-u", "--unset") and len(words) > 1:
            words = words[2:]  # `env -u NAME`: NAME is the option's value, not the command.
            continue
        if word.lower() in _LAUNCH_PREFIX_WORDS:
            after_env = word.lower() == "env"  # A later prefix word (env ... nice ...) ends env's options.
        words = words[1:]
    if not words:
        carried.extend(own)  # A bare `PYTHONPATH=v` statement holds for the rest of the line.
        return "", cwd
    name = re.sub(r"\.exe$", "", os.path.basename(words[0].replace("\\", "/")).lower())  # str: the command's name.
    args = words[1:]  # list[str]: the command's words after its name.
    if name in _EXPORT_WORDS:  # `export PYTHONPATH=v` (declare -x, ...) holds for the rest of the line.
        carried.extend(found.group(1) for found in map(_PYTHONPATH_ASSIGN_RE.match, args) if found)
        return "", cwd
    if name in _CD_WORDS:  # Follow the folder for later words of the line (a cd out of the project is denied apart).
        target = next((arg for arg in args if not arg.startswith("-")), None)  # str | None: the folder named.
        moved = _to_abs(target, base=cwd) if target else None  # str | None: the folder it moves to.
        return "", (moved if moved is not None and _inside(moved) else cwd)
    if name == "eval":  # `eval <words>` runs its words as a command line.
        return _advisor_main_launch(" ".join(args), depth + 1, cwd, kind, list(local)), cwd
    if name in ("conda", "mamba", "micromamba") and args[:1] == ["run"]:  # `conda run [options] <command>`.
        rest = args[1:]  # list[str]: the words after `run`.
        run_cwd = cwd  # str: the folder `--cwd` names, else the current one.
        index = 0  # int: position in rest.
        while index < len(rest) and rest[index].startswith("-"):
            option = rest[index]  # str: one of conda run's options.
            if option in ("-n", "--name", "-p", "--prefix", "--cwd") and index + 1 < len(rest):
                if option == "--cwd":
                    run_cwd = _to_abs(rest[index + 1], base=cwd) or cwd
                index += 2
                continue
            if option.startswith("--cwd="):
                run_cwd = _to_abs(option.split("=", 1)[1], base=cwd) or cwd
            index += 1
        # The PYTHONPATH in effect (carried and prefix values) reaches the command conda runs.
        return _advisor_launch_words(rest[index:], run_cwd, depth, stdin_files, kind, local)[0], cwd
    if ("/" in words[0] or "\\" in words[0]) and _main_session_path(words[0], cwd, kind):
        return words[0], cwd  # A script run by its path (a bare name is looked up on PATH, not in the folder).
    if name in (".", "source"):  # The shell reads the file as commands.
        return (args[0] if args and _main_session_path(args[0], cwd, kind) else ""), cwd
    script = None  # str | None: the interpreter's script operand; None = none (the program comes from standard input).
    if _PYTHON_NAMES_RE.match(name):
        index = 0  # int: position in args.
        while index < len(args):
            arg = args[index]  # str: an option or the script.
            if arg == "-":  # The program is read from standard input.
                break
            if not arg.startswith("-"):
                script = arg
                break
            if re.match(r"^-[A-Za-z]*c$", arg):  # -c <code>: the program is inline, no script runs.
                return "", cwd
            if re.match(r"^-[A-Za-z]*m$", arg):  # -m <module>: the dotted form of the folders.
                module = args[index + 1] if index + 1 < len(args) else ""  # str: the module name.
                # This kind's module form; the exempt process check is no launch.
                launched = module_re.match(module) and module.lower() not in _ADVISOR_EXEMPT_MODULES  # bool-like.
                if not launched:
                    # The name resolved against the folder the command runs in (Python's `-m` puts it first on sys.path)
                    # and against each PYTHONPATH entry written on the line, taken from that folder.
                    bases = [cwd] + [entry for entry in (_to_abs(item, resolve=False, base=cwd) for value in local
                                                         for item in _pythonpath_entries(value)) if entry]
                    launched = _module_launch(module, bases, kind)  # bool: the module loads code from the folders.
                return (module if launched else ""), cwd
            index += 2 if arg in ("-W", "-X", "--check-hash-based-pycs") else 1  # Options with a separate value.
    elif name in _SHELL_NAMES:
        index = 0  # int: position in args.
        while index < len(args):
            arg = args[index]  # str: an option or the script.
            if re.match(r"^-[A-Za-z]*c[A-Za-z]*$", arg):  # -c <script>: judge the script as a command line.
                text = args[index + 1] if index + 1 < len(args) else ""  # str: the script text.
                return _advisor_main_launch(text, depth + 1, cwd, kind, list(local)), cwd  # PYTHONPATH too.
            if not arg.startswith(("-", "+")):
                script = arg
                break
            index += 2 if arg in ("-o", "+o") else 1  # -o <option name> takes a value.
    elif name in _POWERSHELL_NAMES:
        lowered = [arg.lower() for arg in args]  # list[str]: PowerShell options are case-insensitive.
        for index, arg in enumerate(lowered):
            if arg in ("-command", "-c") and index + 1 < len(args):  # A command line: judge it again.
                # The PYTHONPATH in effect reaches the command line PowerShell runs.
                return _advisor_main_launch(" ".join(args[index + 1:]), depth + 1, cwd, kind, list(local)), cwd
            if arg in ("-file", "-f") and index + 1 < len(args):
                script = args[index + 1]
                break
        else:
            script = next((arg for arg in args if not arg.startswith("-")), None)  # A first operand is -File's.
    elif name in _SCRIPT_INTERPRETERS:
        if any(arg in _INLINE_CODE_OPTIONS for arg in args):  # The program is inline.
            return "", cwd
        script = next((arg for arg in args if not arg.startswith("-")), None)
    else:
        return "", cwd  # Not a launch form this rule knows (reading commands land here).
    if script is not None:
        return (script if _main_session_path(script, cwd, kind) else ""), cwd
    # str: a script fed on standard input.
    found = next((path for path in stdin_files if _main_session_path(path, cwd, kind)), "")
    return found, cwd


def _advisor_main_launch(command: str, depth: int = 0, base: str | None = None, kind: str = "main",
                         pythonpath: list[str] | None = None) -> str:
    """The first launch of a script under work/claude-main/ or work/codex-main/ in a shell command (str), or "".

    `kind` selects the folder set (_LAUNCH_FOLDER_SETS): "main" (the default: the two MAIN session folders, as before)
    or "harness"; every form below is seen for either kind. `pythonpath`: the PYTHONPATH values in effect when this text
    runs (an outer line's, for a nested `bash -c` / eval / substitution); None at the top.

    Seen, per simple command (split outside quotes by `_split_unquoted`; a `cd` / `pushd` earlier in the line moves the
    folder later relative words are taken from): a script path in command position (`./work/claude-main/s/x.py`,
    `work/codex-main/s/x.sh`), `source` / `.` of one; the script operand of a Python spelling (python, python3.13,
    pythonw, py, ".exe" too), of bash / sh / zsh / dash / ksh, of node / perl / ruby and pwsh / powershell `-File`; such
    an interpreter reading the script from `< file` or from `cat <file> |`; relative, root-absolute and backslash paths,
    case folded, links resolved; behind assignments, the prefix words (env, command, exec, nohup, time, nice, timeout,
    xargs, stdbuf), keywords and `(...)`; `conda run [-n env] [--cwd dir] <command>`; and, judged again up to three
    levels deep, `$(...)`, `<(...)`, backticks, `eval ...`, a shell's `-c` script and PowerShell's `-Command` text. Not
    seen: a script named through a variable, inline code that runs one (`python -c "runpy.run_path(...)"`,
    `exec(open(...).read)`), the commands `find -exec` or an `xargs` reading the names from its input runs, a copy of
    the script elsewhere, a program that starts it. The script is returned as written (the word on the command line, or
    the module name)."""
    if depth > 3:  # Nested deeper than any form a command is expected to hold: refused.
        raise _NestedTooDeep()
    cwd = TOOL_CWD if base is None else base  # str: the folder relative words are taken from; moved by `cd`.
    carried = list(pythonpath or [])
    # list[str]: the inner command lines of substitutions and backticks, each judged on its own.
    inner = re.findall(r"[$<>]\(([^()]*)\)", command) + re.findall(r"`([^`]*)`", command)
    for text in inner:
        found = _advisor_main_launch(text, depth + 1, cwd, kind, list(carried))  # str: a launch found inside, or "".
        if found:
            return found
    previous: list[str] = []  # list[str]: the words of the simple command before this one (a pipe's source).
    for sep, segment in _split_unquoted(command):
        stdin_files = _REDIRECT_STDIN_RE.findall(segment)  # list[str]: files an input redirect feeds the command.
        # list[str]: the simple command's words without its redirects, brackets stripped, empty words dropped.
        words = [w for w in (tok.lstrip("({").rstrip(")}") for tok in
                             _cmd_tokens(_REDIRECT_IN_RE.sub(" ", _REDIRECT_OUT_RE.sub(" ", segment)))) if w]
        if sep == "|" and previous and previous[0].lower() in _PIPE_SOURCE_WORDS:  # `cat <file> | <interpreter>`.
            stdin_files += [word for word in previous[1:] if not word.startswith("-")]
        previous = words
        # This kind's folders.
        found, cwd = _advisor_launch_words(words, cwd, depth, stdin_files, kind, carried)
        if found:
            return found
    return ""


# The destructive rules of _DENY_PATTERNS are regular expressions over the whole line, so an ordinary spelling passed
# them: `rm -f -r <folder>` (the recursive flag had to stand directly after `rm`), `git reset -q --hard`, an option
# between `git` and its sub-command (`git -P push`, `git --no-pager stash`), a checkout followed on the same line by
# another command's `-c`, `git --git-dir=<path>`, an `-it 5` of another command on a training line. The rules are
# decided; what follows makes the guard see those spellings: each simple command is read as the shell reads its words,
# and the rules are judged on those words. The text patterns stay as they were and decide first, so no verdict they gave
# moves; the word rules only add refusals. A heuristic reader, not a shell.
# -------------------------------------------------------------------------------------------- tuple[str, ...]: the
# operators of a POSIX shell line (and PowerShell's common ones), longest first so that a longer operator wins over its
# prefix (">>" before ">", "&&" before "&"); a newline separates commands as ";" does.
_SHELL_OPERATORS = ("&>>", "<<<", "<<-", ">>", ">|", ">&", "&>", "<<", "<&", "<>", "&&", "||", ";;", "|&", "<(", ">(",
                    ";", "&", "|", "<", ">", "(", ")", "\n")
# set[str]: the redirect operators whose operand is written (">&" only when its operand is a file, not "1" or "-").
_OUTPUT_REDIRECTS = {">", ">>", ">|", "&>", "&>>", "<>", ">&"}
# set[str]: the redirect operators whose operand is read (a file, a heredoc delimiter, a here-string, an fd).
_INPUT_REDIRECTS = {"<", "<<", "<<-", "<<<", "<&"}
# dict[str, set[str]]: per prefix word of _LAUNCH_PREFIX_WORDS, its options whose value is the next word when written
# without "=" (so the value is not taken for the command): env -u NAME / -C DIR, nice -n N, timeout -s SIGNAL / -k
# DURATION, xargs -I REPLACE / -n N / -P N / -d DELIM / -a FILE / -E EOF / -L N / -s N, stdbuf -i / -o / -e MODE.
_PREFIX_VALUE_OPTIONS = {
    "env": {"-u", "--unset", "-C", "--chdir"},
    "nice": {"-n", "--adjustment"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
    "xargs": {"-I", "-n", "-P", "-d", "-a", "-E", "-L", "-s", "--max-args", "--max-procs", "--delimiter",
              "--arg-file", "--eof", "--max-lines", "--max-chars"},
    "stdbuf": {"-i", "-o", "-e", "--input", "--output", "--error"},
}


# The installed tokenizer, kept byte for byte beside the new `_shell_tokens`.
def _shell_tokens_installed(text: str) -> list[tuple[str, str]]:
    """The tokens of one shell command line as a POSIX shell reads them: ("word", text) or ("op", operator).

    A word has its quotes and backslash escapes removed as the shell removes them (`.c\\laude` and `.cla""ude` are
    `.claude`; inside "..." a backslash escapes only \\ " $ ` and a newline; '...' is literal). An unquoted `#` at a
    word's start begins a comment to the end of the line. Operators are those of _SHELL_OPERATORS, longest first; a word
    of unquoted digits written directly before a redirect operator is its file descriptor (`2>`, `2>&1`) and is dropped.
    A heredoc's body (`<<EOF` ... `EOF` on its own line) is skipped, so its text is not read as commands. Backticks,
    `$` and braces are ordinary word characters (`_inner_command_texts` reads the commands inside substitutions).
    Raises ValueError on an unclosed quote (the shell refuses such a line too)."""
    tokens: list[tuple[str, str]] = []  # The tokens found so far.
    word: list[str] = []  # list[str]: the characters of the word being read.
    in_word = False  # bool: a word has started (an empty quoted word "" counts as one).
    digits_only = True  # bool: the word so far is unquoted digits (a file descriptor if a redirect follows).
    heredocs: list[str] = []  # list[str]: heredoc delimiters whose bodies start after the next newline.
    expect_delimiter = False  # bool: the next word is a heredoc delimiter (after "<<" or "<<-").
    index = 0  # int: the scan position.
    length = len(text)  # int: the line's length in characters.

    def flush() -> None:
        """End the current word (if any): append it as a word token, or as a heredoc delimiter's name too."""
        nonlocal word, in_word, digits_only, expect_delimiter
        if in_word:
            value = "".join(word)  # str: the word with quotes and escapes removed.
            tokens.append(("word", value))
            if expect_delimiter:
                heredocs.append(value)  # The body starts after the next newline.
                expect_delimiter = False
        word, in_word, digits_only = [], False, True

    while index < length:
        char = text[index]  # str: the character at the scan position.
        if char == "'":  # A single-quoted span: literal up to the next "'".
            end = text.find("'", index + 1)  # int: the closing quote's position, -1 if none.
            if end < 0:
                raise ValueError("unclosed single quote")
            word.append(text[index + 1:end])
            in_word, digits_only, index = True, False, end + 1
            continue
        if char == '"':  # A double-quoted span: a backslash escapes only \ " $ ` and a newline.
            index += 1
            while index < length and text[index] != '"':
                if text[index] == "\\" and index + 1 < length and text[index + 1] in '\\"$`\n':
                    word.append(text[index + 1] if text[index + 1] != "\n" else "")
                    index += 2
                    continue
                word.append(text[index])
                index += 1
            if index >= length:
                raise ValueError("unclosed double quote")
            in_word, digits_only, index = True, False, index + 1
            continue
        if char == "\\":  # An escape outside quotes: the next character is literal; backslash-newline joins lines.
            if index + 1 < length and text[index + 1] != "\n":
                word.append(text[index + 1])
                in_word, digits_only = True, False
            index += 2
            continue
        if char == "#" and not in_word:  # A comment to the end of the line.
            end = text.find("\n", index)  # int: the end of the comment, -1 at the end of the text.
            index = length if end < 0 else end
            continue
        if char in " \t\r":  # Blanks end a word.
            flush()
            index += 1
            continue
        if char in "<>|&;()\n":
            operator = next(op for op in _SHELL_OPERATORS if text.startswith(op, index))  # str: longest match.
            if in_word and digits_only and operator[0] in "<>" and operator not in ("<(", ">("):
                word, in_word, digits_only = [], False, True  # "2>" / "2>&1": a file descriptor, not a word.
            flush()
            tokens.append(("op", operator))
            index += len(operator)
            if operator in ("<<", "<<-"):
                expect_delimiter = True  # The next word names the heredoc's end.
            if operator == "\n" and heredocs:  # Skip each pending heredoc body, up to its delimiter line.
                for delimiter in heredocs:
                    while index < length:
                        end = text.find("\n", index)  # int: the end of this body line, -1 at the end of the text.
                        line = text[index:] if end < 0 else text[index:end]  # str: one body line.
                        index = length if end < 0 else end + 1
                        if line.strip() == delimiter:
                            break
                heredocs = []
            continue
        word.append(char)
        in_word = True
        digits_only = digits_only and char.isdigit()
        index += 1
    flush()
    return tokens


# The installed command splitter, on the installed tokenizer.
def _parse_simple_commands_installed(text: str) -> list[tuple[list[str], list[str]]]:
    """The simple commands of one shell line, in order, as (words, written redirect targets) pairs.

    Split at every operator that is not a redirect (";", "&", "&&", "||", "|", "|&", ";;", "(", ")", "<(", ">(", a
    newline). A redirect's operand is taken out of the words: an output redirect's operand (">", ">>", ">|", "&>",
    "&>>", "<>", and ">&" when its operand is not a file descriptor such as "1" or "-") is a written target; an input
    redirect's operand (a file, a heredoc delimiter) is dropped. Raises ValueError as `_shell_tokens` does."""
    commands: list[tuple[list[str], list[str]]] = []  # The pairs found so far.
    words: list[str] = []  # list[str]: the current simple command's words.
    targets: list[str] = []  # list[str]: the current simple command's written redirect targets.
    tokens = _shell_tokens_installed(text)  # list[tuple[str, str]]: the line's tokens.
    index = 0  # int: position in tokens.
    while index < len(tokens):
        kind, value = tokens[index]  # str, str: one token.
        if kind == "word":
            words.append(value)
            index += 1
            continue
        if value in _OUTPUT_REDIRECTS or value in _INPUT_REDIRECTS:
            operand = tokens[index + 1][1] if index + 1 < len(tokens) and tokens[index + 1][0] == "word" else None
            if operand is not None and value in _OUTPUT_REDIRECTS:
                if not (value == ">&" and re.match(r"^\d*-?$", operand)):  # ">&1", ">&-": a descriptor, no file.
                    targets.append(operand)
            index += 2 if operand is not None else 1
            continue
        if words or targets:  # Any other operator ends the simple command.
            commands.append((words, targets))
        words, targets = [], []
        index += 1
    if words or targets:
        commands.append((words, targets))
    return commands


# The installed substitution reader (innermost parentheses).
def _inner_command_texts_installed(command: str) -> list[str]:
    """The command lines inside `$( ... )`, `<( ... )`, `>( ... )` and backticks (list[str]), single-quoted text aside.

    Inside '...' a substitution is literal text and runs nothing, so single-quoted spans (outside double quotes) are
    blanked before the search; inside "..." it runs, so double quotes are kept. Innermost parentheses only (a regular
    expression, as `_git_invocations` reads them); an outer text is judged on its own anyway."""
    chars = list(command)  # list[str]: the line, with single-quoted spans blanked below.
    in_double = False  # bool: inside a double-quoted span.
    index = 0  # int: the scan position.
    while index < len(chars):
        char = chars[index]  # str: the character at the scan position.
        if char == "\\" and not in_double:
            index += 2  # An escaped character (an escaped quote opens nothing).
            continue
        if char == '"':
            in_double = not in_double
        elif char == "'" and not in_double:
            end = command.find("'", index + 1)  # int: the closing quote, -1 if none.
            end = len(chars) - 1 if end < 0 else end
            for blank in range(index, end + 1):
                chars[blank] = " "  # Blank the literal span, quotes included.
            index = end + 1
            continue
        index += 1
    text = "".join(chars)  # str: the line with single-quoted spans blanked.
    return re.findall(r"[$<>]\(([^()]*)\)", text) + re.findall(r"`([^`]*)`", text)


# The installed command reader; `_simple_commands` joins its reading.
def _simple_commands_installed(command: str, depth: int = 0):
    """Yield (words, written redirect targets) of every simple command the shell would run for `command`, in order.

    The commands of `$(...)`, `<(...)`, `>(...)` and backticks first (`_inner_command_texts`, also inside double
    quotes), then each simple command of the line (`_parse_simple_commands`); after a command, the commands it runs in
    turn: `eval <words>`, a shell's `-c` script (bash / sh / zsh / dash / ksh, also -lc, -ec ...) and the command of a
    `find ... -exec / -execdir / -ok / -okdir ...;` or `+`. Nested forms are judged up to three levels deep, as the
    other parsers of this file are; deeper, `_NestedTooDeep` is raised and `pre_bash` refuses the line. A line with an
    unclosed quote yields nothing (the shell refuses it as well). The words are yielded as written after quote removal
    (assignments and prefix words included; `_strip_command_prefix` takes them off)."""
    if depth > 3:  # Nested deeper than any form a command is expected to hold: refused.
        raise _NestedTooDeep()
    for text in _inner_command_texts_installed(command):
        yield from _simple_commands_installed(text, depth + 1)
    try:
        commands = _parse_simple_commands_installed(command)  # list[tuple[list[str], list[str]]]: the line's commands.
    except ValueError:
        return  # An unclosed quote: bash refuses to run the line.
    for words, targets in commands:
        yield words, targets
        bare, _cwd = _strip_command_prefix(words, TOOL_CWD)  # list[str]: from the command word on.
        if not bare:
            continue
        name = _command_name(bare[0])  # str: the command's name.
        if name == "eval":  # `eval <words>` runs its words as a command line.
            yield from _simple_commands_installed(" ".join(bare[1:]), depth + 1)
        elif name in _SHELL_NAMES:  # `bash -c "<script>"`: the script is a command line.
            for index, arg in enumerate(bare[1:-1], 1):
                if re.match(r"^-[A-Za-z]*c[A-Za-z]*$", arg):
                    yield from _simple_commands_installed(bare[index + 1], depth + 1)
                    break
        elif name == "find":  # `find ... -exec <command> {} ;` (or +): the command between -exec and ; / +.
            index = 1  # int: position in bare.
            while index < len(bare):
                if bare[index] in ("-exec", "-execdir", "-ok", "-okdir"):
                    end = next((pos for pos in range(index + 1, len(bare)) if bare[pos] in (";", "+")), len(bare))
                    yield bare[index + 1:end], []
                    index = end
                index += 1


def _shell_tokens(text: str, bodies: list[str] | None = None) -> list[tuple[str, str]]:
    """The tokens of one shell command line as a POSIX shell reads them: ("word", text) or ("op", operator).

    A word has its quotes and backslash escapes removed as the shell removes them (`.c\\laude` and `.cla""ude` are
    `.claude`; inside "..." a backslash escapes only \\ " $ ` and a newline; '...' is literal). An unquoted `#` at a
    word's start begins a comment to the end of the line. Operators are those of _SHELL_OPERATORS, longest first; a word
    of unquoted digits written directly before a redirect operator is its file descriptor (`2>`, `2>&1`) and is dropped.
    A heredoc's body (`<<EOF` ... `EOF` on its own line) is skipped, so its text is not read as commands. Backticks, `$`
    and braces are ordinary word characters (`_inner_command_texts` reads the commands inside substitutions). Raises
    ValueError on an unclosed quote (the shell refuses such a line too).))` or `((...))` - is a shift, not a heredoc
    (until this step `$((1<<20))` started a heredoc whose body was every later line); `$'...'` is ANSI-C quoting, in
    which a backslash escapes the next character (`$'it\\'s'` is one word, not an unclosed quote) and the common escapes
    are decoded; inside "...", a `$(...)` is copied whole into the word up to its matching `)` (`_substitution_end`), so
    quotes inside it (`"$(printf "%s" "it's")"`) do not end the span. When `bodies` (a list) is given, each heredoc body
    is appended to it as (index of its `<<` operator in the returned tokens, body text), so a caller can read the script
    a shell is fed. }` and `$[ ... ]` are one word part up to their matching close (`_param_span_end`), so a `<<` or a
    `)` inside them is neither a heredoc nor an operator (R3, S2, S3). This reader is no longer the only one:
    `_simple_commands` and `_real_folder_records` also judge the installed reading (`_shell_tokens_installed`), so a
    line this reader gets wrong can only add commands."""
    tokens: list[tuple[str, str]] = []  # The tokens found so far.
    word: list[str] = []  # list[str]: the characters of the word being read.
    in_word = False  # bool: a word has started (an empty quoted word "" counts as one).
    digits_only = True  # bool: the word so far is unquoted digits (a file descriptor if a redirect follows).
    heredocs: list[str] = []  # list[str]: heredoc delimiters whose bodies start after the next newline.
    expect_delimiter = False  # bool: the next word is a heredoc delimiter (after "<<" or "<<-").
    index = 0  # int: the scan position.
    length = len(text)  # int: the line's length in characters.
    # Bool, the last character added to the word is an unquoted "$" (a following "'" opens $'...' quoting).
    dollar_last = False
    paren_depth = 0  # int: open "(" / "<(" / ">(" operators not yet closed by ")" (0 at the top level).
    arith: list[int] = []  # list[int]: the depth at which each open `((` arithmetic span started.
    heredoc_ops: list[int] = []  # list[int]: token index of each pending heredoc's `<<` operator.

    def flush() -> None:
        """End the current word (if any): append it as a word token, or as a heredoc delimiter's name too."""
        nonlocal word, in_word, digits_only, expect_delimiter, dollar_last
        if in_word:
            value = "".join(word)  # str: the word with quotes and escapes removed.
            tokens.append(("word", value))
            if expect_delimiter:
                heredocs.append(value)  # The body starts after the next newline.
                expect_delimiter = False
        word, in_word, digits_only, dollar_last = [], False, True, False

    while index < length:
        char = text[index]  # str: the character at the scan position.
        if char == "'" and dollar_last:  # $'...' (ANSI-C quoting): a backslash escapes the next character.
            word.pop()  # The "$" is the quoting's marker, not part of the word.
            index += 1
            while index < length and text[index] != "'":
                if text[index] == "\\" and index + 1 < length:  # An escape: decoded when common, else kept as written.
                    word.append(_ANSI_C_ESCAPES.get(text[index + 1], "\\" + text[index + 1]))
                    index += 2
                    continue
                word.append(text[index])
                index += 1
            if index >= length:
                raise ValueError("unclosed $'...' quote")
            in_word, digits_only, dollar_last, index = True, False, False, index + 1
            continue
        after_dollar = dollar_last  # bool: the "$" marker state before this character.
        dollar_last = False  # Any other character ends the "$" marker (set again below for a plain "$").
        if char == "'":  # A single-quoted span: literal up to the next "'".
            end = text.find("'", index + 1)  # int: the closing quote's position, -1 if none.
            if end < 0:
                raise ValueError("unclosed single quote")
            word.append(text[index + 1:end])
            in_word, digits_only, index = True, False, end + 1
            continue
        if char == '"':  # A double-quoted span: a backslash escapes only \ " $ ` and a newline.
            index += 1
            while index < length and text[index] != '"':
                if text[index] == "\\" and index + 1 < length and text[index + 1] in '\\"$`\n':
                    word.append(text[index + 1] if text[index + 1] != "\n" else "")
                    index += 2
                    continue
                if text.startswith("$(", index):  # A substitution inside "..." is copied whole.
                    end = _substitution_end(text, index + 2)  # int: its closing ")", -1 if none.
                    if end >= 0:
                        word.append(text[index:end + 1])
                        index = end + 1
                        continue
                word.append(text[index])
                index += 1
            if index >= length:
                raise ValueError("unclosed double quote")
            in_word, digits_only, index = True, False, index + 1
            continue
        if char == "\\":  # An escape outside quotes: the next character is literal; backslash-newline joins lines.
            if index + 1 < length and text[index + 1] != "\n":
                word.append(text[index + 1])
                in_word, digits_only = True, False
            index += 2
            continue
        if char == "#" and not in_word:  # A comment to the end of the line.
            end = text.find("\n", index)  # int: the end of the comment, -1 at the end of the text.
            index = length if end < 0 else end
            continue
        if char in " \t\r":  # Blanks end a word.
            flush()
            index += 1
            continue
        if char == "$" and not after_dollar and text[index + 1:index + 2] in ("{", "["):  # `${` / `$[`.
            # }` / `$[ ... ]` is one word part up to its matching close; copied as written (quotes inside kept), so its
            # `<<`, `)` or blanks are not read as operators. Unclosed: read as before.
            end = _param_span_end(text, index + 1)  # int: the matching "}" / "]", -1 if none.
            if end >= 0:  # A closed span: the whole of it joins the word.
                word.append(text[index:end + 1])  # Copied as written, "$" and the braces / brackets included.
                in_word, digits_only, index = True, False, end + 1  # A word has started; go on after the close.
                continue  # The character after the span.
        if char in "<>|&;()\n":
            operator = next(op for op in _SHELL_OPERATORS if text.startswith(op, index))  # str: longest match.
            # Bool, this "(" opens `` close together (`_arith_end`), else bash reads two sub-shells.
            opens_arith = (operator == "(" and text.startswith("((", index) and (not in_word or word[-1:] == ["$"])
                           and _arith_end(text, index) >= 0)  # bool: see the two comment lines above.
            if in_word and digits_only and operator[0] in "<>" and operator not in ("<(", ">("):
                word, in_word, digits_only = [], False, True  # "2>" / "2>&1": a file descriptor, not a word.
            flush()
            tokens.append(("op", operator))
            index += len(operator)
            if opens_arith:  # Remember where the arithmetic span began.
                arith.append(paren_depth)
            if operator in ("(", "<(", ">("):  # The depth of open parentheses.
                paren_depth += 1
            elif operator == ")":
                paren_depth = max(0, paren_depth - 1)
                if arith and paren_depth <= arith[-1]:  # The arithmetic span's `))` is reached.
                    arith.pop()
            if operator in ("<<", "<<-") and not arith:  # Inside `()` "<<" is a shift.
                expect_delimiter = True  # The next word names the heredoc's end.
                heredoc_ops.append(len(tokens) - 1)  # The operator's token index, for its body.
            if operator == "\n" and heredocs:  # Skip each pending heredoc body, up to its delimiter line.
                for number, delimiter in enumerate(heredocs):
                    body: list[str] = []  # list[str]: this heredoc's body lines.
                    while index < length:
                        end = text.find("\n", index)  # int: the end of this body line, -1 at the end of the text.
                        line = text[index:] if end < 0 else text[index:end]  # str: one body line.
                        index = length if end < 0 else end + 1
                        if line.strip() == delimiter:
                            break
                        body.append(line)
                    if bodies is not None and number < len(heredoc_ops):  # The body, to the caller.
                        bodies.append((heredoc_ops[number], "\n".join(body)))
                heredocs = []
                heredoc_ops = []  # Every pending body was read.
            continue
        word.append(char)
        in_word = True
        digits_only = digits_only and char.isdigit()
        dollar_last = char == "$" and not after_dollar  # A following "'" opens $'...'.
        index += 1
    flush()
    return tokens


# dict[str, str]: the escapes of $'...' quoting decoded by `_shell_tokens` (bash's list, the common part: \n \t \r \a \b
# \f \v \e \E \\ \' \" \?); any other escape (octal, \x, \u, \c) is kept as written.
_ANSI_C_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v", "e": "\x1b",
                   "E": "\x1b", "\\": "\\", "'": "'", '"': '"', "?": "?"}


def _marker_dollar(text: str, pos: int) -> bool:
    """True when the `$` at `pos` of `text` is a quoting / expansion marker: not escaped and not the second `$` of a `$$`
    pair. bash reads `$$` as one parameter (the shell's process id) before it looks at quotes, so in `$$'a\\'` the quote
    is an ordinary single quote; in `$$$'a'` the third `$` opens `$'...'` again; a run of `$` written after a backslash
    starts with a literal `$` (`\\$'a'` is a `$` and a plain quote)."""
    start = pos  # int: where the run of "$" characters that ends at pos begins.
    while start > 0 and text[start - 1] == "$":  # Walk back over the run of "$".
        start -= 1  # One "$" more in the run.
    run = pos - start + 1  # int: the run's length, this "$" included (at least 1).
    if start > 0 and text[start - 1] == "\\":  # The run's first "$" is escaped: a literal character.
        run -= 1  # Not counted: a literal character.
    return run % 2 == 1  # Pairs of "$" are `$$` parameters; an odd one left over is the marker.


def _arith_end(text: str, index: int) -> int:
    """The index (int) just after the `))` that closes the `((` at `index` of `text`, when the two `)` close together
    - the shell's arithmetic `((...))` or `$((...))` -; -1 otherwise.

    bash reads `((` as arithmetic only when the inner `(` and the outer one are closed by `))`; `((true); cat ...)` -
    where the inner `(` is closed by a `)` that no `)` follows - is two sub-shells, and a `<<` in it is a heredoc.
    Parentheses are counted from the two of `((`; backslash escapes and '...' / "..." spans are skipped; when the text
    ends first the answer is -1 (not arithmetic: the reading that keeps heredocs, as the installed reader had it). One
    of the three scans the step budget counts - checked at the entry (`_scan_budget_enter`), and every answer counted
    where it is returned (`_scan_budget_add`: the distance from `index` to the answer, or to the text's end for -1); the
    answers themselves are unchanged."""
    _scan_budget_enter()  # Past this event's budget, `_StepBudgetExceeded` is raised before the scan.
    depth = 2  # int: open parentheses, the two of `((` included.
    pos = index + 2  # int: the scan position, after `((`.
    while pos < len(text):  # To the end of the text at most.
        char = text[pos]  # str: the character at the scan position.
        if char == "\\":  # An escaped character counts for nothing.
            pos += 2  # The backslash and the character it escapes.
            continue  # Next character.
        if char in "'\"":  # A quoted span: skipped whole (an unclosed one ends the scan).
            end = text.find(char, pos + 1)  # int: its closing quote, -1 if none.
            if end < 0:  # Unclosed: no `))` can be trusted after it.
                return _scan_budget_add(text, index, -1)  # Not arithmetic.
            pos = end + 1  # After the closing quote.
            continue  # Next character.
        if char == "(":  # A nested opening parenthesis.
            depth += 1  # One more to close.
        elif char == ")":  # A closing parenthesis.
            depth -= 1  # One fewer open.
            if depth == 1:  # The inner `(` of `((` is closed: arithmetic only if the outer one closes right here.
                # Just after `))`, or not arithmetic.
                return _scan_budget_add(text, index, pos + 2 if text[pos + 1:pos + 2] == ")" else -1)
        pos += 1  # Next character.
    return _scan_budget_add(text, index, -1)  # The text ended first.


def _param_span_end(text: str, index: int) -> int:
    """The index (int) of the `}` / `]` that closes the `{` / `[` at `index` of `text` (the brace of `${ ... }` or the
    bracket of `$[ ... ]`), or -1 when the text ends first.

    A parameter expansion and the old arithmetic form are one word part in bash: a `<<` inside (`${v:1<<2}`, `$[1<<20]`)
    is a shift, not a heredoc, and a `)` inside does not close a substitution around it. Nested braces / brackets of the
    same kind are counted; backslash escapes and '...' / "..." spans are skipped. One of the three scans the step budget
    counts - checked at the entry (`_scan_budget_enter`), and every answer counted where it is returned
    (`_scan_budget_add`: the distance from `index` to the answer, or to the text's end for -1); the answers themselves
    are unchanged."""
    _scan_budget_enter()  # Past this event's budget, `_StepBudgetExceeded` is raised before the scan.
    opener = text[index]  # str: "{" or "[".
    closer = "}" if opener == "{" else "]"  # str: the matching close.
    depth = 1  # int: open braces / brackets, this one included.
    pos = index + 1  # int: the scan position.
    while pos < len(text):  # To the end of the text at most.
        char = text[pos]  # str: the character at the scan position.
        if char == "\\":  # An escaped character counts for nothing.
            pos += 2  # The backslash and the character it escapes.
            continue  # Next character.
        if char in "'\"":  # A quoted span: skipped whole (an unclosed one ends the scan).
            end = text.find(char, pos + 1)  # int: its closing quote, -1 if none.
            if end < 0:  # Unclosed: the span has no trusted close.
                return _scan_budget_add(text, index, -1)  # Read as before.
            pos = end + 1  # After the closing quote.
            continue  # Next character.
        if char == opener:  # A nested brace / bracket of the same kind.
            depth += 1  # One more to close.
        elif char == closer:  # A closing brace / bracket.
            depth -= 1  # One fewer open.
            if depth == 0:  # The span's own close.
                return _scan_budget_add(text, index, pos)  # Its index.
        pos += 1  # Next character.
    return _scan_budget_add(text, index, -1)  # The text ended first.


def _heredoc_delimiter(text: str, index: int) -> tuple[str, bool, int] | None:
    """The heredoc delimiter that starts at `index` (just after "<<" or "<<-"): (name, quoted, end index), or None.

    The pattern is matched in place (`_HEREDOC_DELIMITER_RE.match(text, index)`) instead of on a copy of the rest of the
    text (`text[index:]`), which cost the text's length at every `<<`; the pattern holds no `^`, lookbehind or end
    anchor, so it matches the same word and the answer is the same."""
    while index < len(text) and text[index] in " \t":
        index += 1
    match = _HEREDOC_DELIMITER_RE.match(text, index)  # re.Match | None: the delimiter word, read in place.
    if not match:
        return None
    quoted = bool(match.group(1)) or text[index:index + 1] == "\\"  # bool: a quoted (literal) body.
    return match.group(2), quoted, match.end()  # `end` is already an index of `text` (was index + end).


# re.Pattern: the heredoc delimiter word of `_heredoc_delimiter` - an optional quote, an optional backslash, the name
# (no blank, quote or shell operator character), the same quote again. The pattern text is the one that function matched
# before this step, compiled once so it can be matched in place.
_HEREDOC_DELIMITER_RE = re.compile(r"""(['"]?)\\?([^\s'";&|()<>]+)\1""")


def _skip_heredoc_bodies(text: str, index: int, pending: list[tuple[str, bool]], found: list[str] | None) -> int:
    """Skip the heredoc bodies `pending` ((delimiter, quoted) pairs) that start at `index` (just after a newline); return
    the index after the last delimiter line. When `found` (a list) is given, the substitutions inside each unquoted body
    (where they run, as in "...") are appended to it."""
    for delimiter, quoted in pending:
        start = index  # int: where this body starts.
        while index < len(text):
            end = text.find("\n", index)  # int: the end of this body line, -1 at the end of the text.
            line = text[index:] if end < 0 else text[index:end]  # str: one body line.
            if line.strip() == delimiter:
                body_end = index  # int: where the body ends (the delimiter line is not part of it).
                index = len(text) if end < 0 else end + 1
                break
            index = len(text) if end < 0 else end + 1
        else:
            body_end = len(text)  # No delimiter line: the body runs to the end of the text.
        if found is not None and not quoted:  # Substitutions run in an unquoted body.
            found.extend(_substitution_texts(text[start:body_end], literal_quotes=True))
    return index


def _substitution_end(text: str, start: int) -> int:
    """The index (int) of the `)` that closes a command substitution whose text begins at `start` (just after "$(", "<(" or
    ">("), or -1 when the text ends first.

    )` and backslash escapes), backticks, `#` comments, heredoc bodies (`_heredoc_delimiter`), and parentheses counted.
    An arithmetic span (`$((...))`, or `((...))` inside) reads "<<" as a shift, not a heredoc. A quote after `$$` is an
    ordinary quote (`_marker_dollar`); `((` is arithmetic only when its `))` close together (`_arith_end`); `${ ... }`
    and `$[ ... ]` are skipped whole (`_param_span_end`), so their `<<` is no heredoc and their `)` closes nothing. One
    of the three scans the step budget counts - checked at the entry (`_scan_budget_enter`), and every answer counted
    where it is returned (`_scan_budget_add`: the distance from `start` to the answer, or to the text's end for -1; a
    nested scan counts itself, and this one's distance includes the span it skipped); the answers themselves are
    unchanged."""
    _scan_budget_enter()  # Past this event's budget, `_StepBudgetExceeded` is raised before the scan.
    depth = 1  # int: open parentheses, the substitution's own included.
    # list[int]: depths of open arithmetic spans; `$((` opens one only when its `))` close together.
    arith = [0] if text.startswith("(", start) and start > 0 and _arith_end(text, start - 1) >= 0 else []
    pending: list[tuple[str, bool]] = []  # list[(str, bool)]: heredoc delimiters awaiting the next newline.
    index = start  # int: the scan position.
    length = len(text)  # int: the text's length.
    while index < length:
        char = text[index]  # str: the character at the scan position.
        if char == "\\":  # An escaped character closes nothing.
            index += 2
            continue
        if char == "'":  # '...' (or $'...', where a backslash escapes): literal to the closing quote.
            ansi = index > 0 and _marker_dollar(text, index - 1)  # bool: $'...' quoting.
            index += 1
            while index < length and text[index] != "'":
                index += 2 if ansi and text[index] == "\\" else 1
            if index >= length:
                return _scan_budget_add(text, start, -1)  # Unclosed quote.
            index += 1
            continue
        if char == "$" and text[index + 1:index + 2] in ("{", "[") and _marker_dollar(text, index):  # ${ $[
            span_end = _param_span_end(text, index + 1)  # int: the "}" / "]" of ${ } / $[ ], or -1.
            if span_end >= 0:  # Skipped whole: its `<<` is no heredoc and its `)` closes nothing.
                index = span_end + 1  # After its close.
                continue
        if char == '"':  # "...": backslash escapes and nested substitutions.
            index += 1
            while index < length and text[index] != '"':
                if text[index] == "\\":
                    index += 2
                    continue
                if text.startswith("$(", index):
                    inner = _substitution_end(text, index + 2)  # int: the nested substitution's end.
                    if inner < 0:
                        return _scan_budget_add(text, start, -1)  # Nested one unclosed.
                    index = inner + 1
                    continue
                index += 1
            if index >= length:
                return _scan_budget_add(text, start, -1)  # Unclosed "...".
            index += 1
            continue
        if char == "`":  # A backtick substitution: to the next unescaped backtick.
            index += 1
            while index < length and text[index] != "`":
                index += 2 if text[index] == "\\" else 1
            if index >= length:
                return _scan_budget_add(text, start, -1)  # Unclosed backtick.
            index += 1
            continue
        if char == "#" and (index == start or text[index - 1] in " \t\n;&|("):  # A comment to the end of the line.
            end = text.find("\n", index)  # int: the comment's end, -1 if none.
            if end < 0:
                return _scan_budget_add(text, start, -1)  # A comment to the end.
            index = end
            continue
        if not arith and text.startswith("<<", index) and not text.startswith("<<<", index):
            found = _heredoc_delimiter(text, index + (3 if text.startswith("<<-", index) else 2))  # The delimiter.
            if found:
                pending.append((found[0], found[1]))
                index = found[2]
                continue
        if char == "\n" and pending:  # The pending heredoc bodies start here.
            index = _skip_heredoc_bodies(text, index + 1, pending, None)
            pending = []
            continue
        if char == "(":
            if text.startswith("((", index) and _arith_end(text, index) >= 0:  # Arithmetic opens)` close).
                arith.append(depth)
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return _scan_budget_add(text, start, index)  # The closing ")".
            if arith and depth <= arith[-1]:
                arith.pop()
        index += 1
    return _scan_budget_add(text, start, -1)  # The text ended first.


def _substitution_texts(text: str, literal_quotes: bool = False) -> list[str]:
    """The command lines inside the top-level `$(...)`, `<(...)`, `>(...)` and backticks of `text` (list[str]), each read
    whole to its matching `)` (`_substitution_end`), so an outer substitution is judged with all its text and its own
    inner ones are reached when that text is judged again.

    Quoting as the shell reads it: '...' and $'...' are literal (a substitution there runs nothing); inside "..." a
    backslash escapes `\\"` (it does not end the span) and `$` and backticks run, process substitution does not; a
    heredoc body is skipped when its delimiter is quoted and read like "..." otherwise. `literal_quotes=True` reads the
    whole text like the inside of "..." (quotes are characters), for an unquoted heredoc body. A quote after `$$` is an
    ordinary quote (`_marker_dollar`); a `<<` inside an arithmetic `((...))` whose `))` close together (`_arith_end`),
    or inside `${ ... }` / `$[ ... ]` (`_param_span_end`), is a shift, not a heredoc - the substitutions inside those
    spans are still read."""
    found: list[str] = []  # list[str]: the inner command lines.
    in_double = literal_quotes  # bool: inside "..." (or a body read like it).
    pending: list[tuple[str, bool]] = []  # list[(str, bool)]: heredoc delimiters awaiting the next newline.
    index = 0  # int: the scan position.
    length = len(text)  # int: the text's length.
    quiet_until = -1  # int: the last index of an arithmetic or ${ } / $[ ] span; no heredoc starts up to it.
    while index < length:
        char = text[index]  # str: the character at the scan position.
        if char == "\\":  # An escaped character opens nothing (also \" inside "...").
            index += 2
            continue
        if char == "'" and not in_double:  # '...' or $'...': literal.
            ansi = index > 0 and _marker_dollar(text, index - 1)  # bool: $'...'.
            index += 1
            while index < length and text[index] != "'":
                index += 2 if ansi and text[index] == "\\" else 1
            index += 1
            continue
        if char == '"' and not literal_quotes:
            in_double = not in_double
            index += 1
            continue
        if char in "$<>" and text.startswith("(", index + 1) and (char == "$" or not in_double):
            end = _substitution_end(text, index + 2)  # int: the matching ")", -1 if none.
            if end < 0:
                break  # Unbalanced: nothing more is read here (the regular-expression reading still applies).
            found.append(text[index + 2:end])
            index = end + 1
            continue
        if char == "`":
            end = index + 1  # int: the closing backtick's position.
            while end < length and text[end] != "`":
                end += 2 if text[end] == "\\" else 1
            if end >= length:
                break
            found.append(text[index + 1:end])
            index = end + 1
            continue
        if char == "$" and text[index + 1:index + 2] in ("{", "[") and _marker_dollar(text, index):  # ${ $[
            quiet_until = max(quiet_until, _param_span_end(text, index + 1))
        elif char == "(" and not in_double and text.startswith("((", index):  # Maybe arithmetic.
            quiet_until = max(quiet_until, _arith_end(text, index) - 1)
        if (not in_double and index > quiet_until and text.startswith("<<", index)
                and not text.startswith("<<<", index)):  # Not inside an arithmetic or ${ } / $[ ] span.
            delimiter = _heredoc_delimiter(text, index + (3 if text.startswith("<<-", index) else 2))  # Or None.
            if delimiter:
                pending.append((delimiter[0], delimiter[1]))
                index = delimiter[2]
                continue
        if char == "\n" and pending:  # The heredoc bodies: skipped, an unquoted one read for substitutions.
            index = _skip_heredoc_bodies(text, index + 1, pending, found)
            pending = []
            continue
        index += 1
    return found


def _parse_simple_commands(text: str, feeds: list[dict] | None = None) -> list[tuple[list[str], list[str]]]:
    """The simple commands of one shell line, in order, as (words, written redirect targets) pairs.

    Split at every operator that is not a redirect (";", "&", "&&", "||", "|", "|&", ";", "(", ")", "<(", ">(", a
    newline). A redirect's operand is taken out of the words: an output redirect's operand (">", ">>", ">|", "&>",
    "&>>", "<>", and ">&" when its operand is not a file descriptor such as "1" or "-") is a written target; an input
    redirect's operand (a file, a heredoc delimiter) is dropped. Raises ValueError as `_shell_tokens` does. When `feeds`
    (a list) is given, one dict per returned command is appended to it: {"stdin": [texts fed to the command - each
    heredoc body (`<<`, `<<-`) and here-string (`<<<`) operand], "piped": True when the command follows "|" or "|&"} -
    so a caller can read the script a shell is fed. The returned commands are the same with or without it."""
    commands: list[tuple[list[str], list[str]]] = []  # The pairs found so far.
    words: list[str] = []  # list[str]: the current simple command's words.
    targets: list[str] = []  # list[str]: the current simple command's written redirect targets.
    bodies: list[tuple[int, str]] = []  # list[(int, str)]: heredoc bodies by their operator's token index.
    tokens = _shell_tokens(text, bodies)  # list[tuple[str, str]]: the line's tokens.
    body_of = dict(bodies)  # dict[int, str]: the body of the heredoc whose `<<` is that token.
    fed: list[str] = []  # list[str]: the texts fed to the current command's standard input.
    piped = False  # bool: the current command follows "|" or "|&".
    index = 0  # int: position in tokens.
    while index < len(tokens):
        kind, value = tokens[index]  # str, str: one token.
        if kind == "word":
            words.append(value)
            index += 1
            continue
        if value in _OUTPUT_REDIRECTS or value in _INPUT_REDIRECTS:
            operand = tokens[index + 1][1] if index + 1 < len(tokens) and tokens[index + 1][0] == "word" else None
            if operand is not None and value in _OUTPUT_REDIRECTS:
                if not (value == ">&" and re.match(r"^\d*-?$", operand)):  # ">&1", ">&-": a descriptor, no file.
                    targets.append(operand)
            if index in body_of:  # A heredoc's body is fed to this command.
                fed.append(body_of[index])
            elif value == "<<<" and operand is not None:  # So is a here-string's word.
                fed.append(operand)
            index += 2 if operand is not None else 1
            continue
        if words or targets:  # Any other operator ends the simple command.
            commands.append((words, targets))
            if feeds is not None:  # What this command was fed, and whether it is piped into.
                feeds.append({"stdin": fed, "piped": piped})
        piped = value in ("|", "|&")  # The next command reads this one's output.
        words, targets, fed = [], [], []
        index += 1
    if words or targets:
        commands.append((words, targets))
        if feeds is not None:
            feeds.append({"stdin": fed, "piped": piped})
    return commands


def _inner_command_texts(command: str) -> list[str]:
    """The command lines inside `$( ... )`, `<( ... )`, `>( ... )` and backticks (list[str]), single-quoted text aside.

    Inside '...' a substitution is literal text and runs nothing, so single-quoted spans (outside double quotes) are
    blanked before the search; inside "..." it runs, so double quotes are kept. Innermost parentheses only (a regular
    expression, as `_git_invocations` reads them); an outer text is judged on its own anyway. The texts of
    `_substitution_texts` are added - each top-level substitution read whole to its matching `)`, with `\\"` inside
    "..." read as an escape (the reading below toggles on it and may then blank a single-quoted span that is in fact
    inside "...") - so `x="$(cd lib && <command> && echo $(pwd))"` has its outer text judged too; the installed reading
    is kept unchanged and its texts come first. The installed reading is the installed function itself, kept beside this
    one as `_inner_command_texts_installed` (byte for byte), so this union cannot give fewer texts than it did. The
    membership test reads a set of the installed reading's texts instead of searching their list once per substitution
    (a cost growing with the square of their number); the set holds the same texts and the list is not changed while it
    is read, so every answer is the same."""
    texts = _inner_command_texts_installed(command)  # list[str]: the installed reading's texts, first.
    installed = set(texts)  # set[str]: the same texts, for a membership test in constant time.
    return texts + [inner for inner in _substitution_texts(command) if inner not in installed]  # A union.


def _command_name(word: str) -> str:
    """The command name of a command word (str): its last path segment, lower case, a trailing ".exe" removed."""
    return re.sub(r"\.exe$", "", os.path.basename(word.replace("\\", "/")).lower())


def _strip_command_prefix(words: list[str], cwd: str) -> tuple[list[str], str]:
    """The words of a simple command from its command word on, and the folder it runs in: (list[str], str).

    Dropped in front: assignments (NAME=value), keywords and grouping words (_SHELL_LEAD_WORDS: if, then, do, !, {,
    ...), the prefix words of _LAUNCH_PREFIX_WORDS (env, command, builtin, exec, nohup, time, nice, timeout, xargs,
    stdbuf) with their options and option values (_PREFIX_VALUE_OPTIONS) and the numbers they take ("nice -n 5",
    "timeout 60", "timeout 9s"), and xargs' "{}". `env -C <dir>` / `--chdir=<dir>` moves the folder the command runs in
    (returned; `cwd` is the folder before); `env -S <string>` / `--split-string` is split into words, as env does. A
    dropped word moves an index (`pos`) instead of copying the rest of the list (`words = words[1:]`, a cost growing
    with the square of the words' number); the words from `pos` on are the list the copies left, so every answer is the
    same (the list given is returned itself when nothing is dropped, as before)."""
    prefix = ""  # str: the last prefix word dropped ("" before any), whose options are being skipped.
    pos = 0  # int: the index of the word at command position; the words before it are dropped.
    while pos < len(words):  # The same test as `while words:` on the remaining words.
        word = words[pos]  # str: the word at command position.
        low = word.lower()  # str: the same, case folded (prefix words and keywords are matched case-folded).
        if re.match(r"^[A-Za-z_]\w*=", word) or low in _SHELL_LEAD_WORDS:
            pos += 1  # An assignment, a keyword or a grouping word: the command comes later.
            continue
        if low in _LAUNCH_PREFIX_WORDS:
            prefix, pos = low, pos + 1  # A prefix word: its options and the command follow.
            continue
        if prefix and word.startswith("-") and len(word) > 1:
            name = word.split("=", 1)[0]  # str: the option without an "=value" part.
            # str: its value - after "=", else the next word.
            value = word.split("=", 1)[1] if "=" in word else (words[pos + 1] if len(words) > pos + 1 else "")
            if prefix == "env" and name in ("-C", "--chdir"):
                moved = _to_abs(value, base=cwd) if value else None  # str | None: the folder the command runs in.
                cwd = moved if moved is not None and _inside(moved) else cwd
            if prefix == "env" and name in ("-S", "--split-string"):
                # The string is the command's words: a new list (its tokens, then the words after the option and its
                # value), read from its start.
                words, pos = _cmd_tokens(value) + words[pos + (1 if "=" in word else 2):], 0
                continue
            takes_value = "=" not in word and name in _PREFIX_VALUE_OPTIONS.get(prefix, ())  # bool: next word is it.
            pos += 2 if takes_value else 1  # The option, and its value when it takes one.
            continue
        if prefix and (re.match(r"^\d+(\.\d+)?[smhd]?$", word) or word == "{}"):
            pos += 1  # A prefix word's number ("nice -n 5" after -n, "timeout 60") or xargs' "{}".
            continue
        break
    # list[str]: the words from the command word on - the list itself when nothing was dropped (as the old loop returned
    # it), else the slice the copies left (empty when `pos` ran past the end, as `words[2:]` of a one-word list was).
    return (words[pos:] if pos else words), cwd


def _simple_commands(command: str, depth: int = 0):
    """Yield (words, written redirect targets) of every simple command the shell would run for `command`: the commands of
    BOTH word readings. Every rule that reads commands goes through this function.

    First everything the installed reader yields (`_simple_commands_installed`: the installed guard's own reader, byte
    for byte, with its tokenizer `_shell_tokens_installed`), in its order; then each command of the new reading that the
    installed reading has not already yielded - a repeat is skipped once per copy (counted as a multiset), so a rule
    meets a command once and no reason is given twice. So a rule sees at least the commands the installed hooks gave it,
    in the same order and before anything new, whatever a new reading gets wrong. `_word_write_targets`, which follows
    each `cd` in the order of the commands, therefore keeps the installed folder sequence for the installed commands;
    the new reading's extra commands are judged after them."""
    seen: dict[tuple[tuple[str, ...], tuple[str, ...]], int] = {}  # Installed commands (words, targets) -> count.
    for words, targets in _simple_commands_installed(command, depth):  # The installed reading, first.
        key = (tuple(words), tuple(targets))  # tuple: the command in a hashable form.
        seen[key] = seen.get(key, 0) + 1  # One copy more of this command.
        yield words, targets
    for words, targets in _simple_commands_new(command, depth):  # Then the new reading.
        key = (tuple(words), tuple(targets))  # tuple: the command in a hashable form.
        if seen.get(key, 0):  # Already yielded by the installed reading: skipped, once per copy.
            seen[key] -= 1  # That copy is used up.
            continue
        yield words, targets


def _simple_commands_new(command: str, depth: int = 0):
    """The commands of `$(...)`, `<(...)`, `>(...)` and backticks first (`_inner_command_texts`, also inside double
    quotes), then each simple command of the line (`_parse_simple_commands`); after a command, the commands it runs in
    turn: `eval <words>`, a shell's `-c` script (bash / sh / zsh / dash / ksh, also -lc, -ec ...) and the command of a
    `find ... -exec / -execdir / -ok / -okdir ...;` or `+`. Nested forms are judged up to three levels deep, as the
    other parsers of this file are; deeper, `_NestedTooDeep` is raised and `pre_bash` refuses the line. A line with an
    unclosed quote yields nothing (the shell refuses it as well). The words are yielded as written after quote removal
    (assignments and prefix words included; `_strip_command_prefix` takes them off). A text with an unclosed quote is
    read line by line (the shell runs the complete lines before the broken one and refuses that one; the broken line
    yields nothing)."""
    if depth > 3:  # Nested deeper than any form a command is expected to hold: refused.
        raise _NestedTooDeep()
    for text in _inner_command_texts(command):
        yield from _simple_commands(text, depth + 1)
    feeds: list[dict] = []  # list[dict]: per command, the texts fed to it and whether it is piped into.
    try:
        commands = _parse_simple_commands(command, feeds)  # list[tuple[list[str], list[str]]]: the line's commands.
    except ValueError:
        # An unclosed quote. bash runs the complete lines before the broken one; each line of a text of several lines is
        # read on its own (a line that is broken alone yields nothing).
        lines = command.split("\n")  # list[str]: the text's lines.
        if len(lines) > 1:
            for line in lines:
                yield from _simple_commands(line, depth)
        return  # An unclosed quote: bash refuses to run the line.
    for number, (words, targets) in enumerate(commands):
        yield words, targets
        # The commands this one runs in turn that the reading below does not follow; `before` is the command whose
        # output is piped into this one, with what it was fed (None when it is not piped into).
        before = (commands[number - 1][0], feeds[number - 1]["stdin"]) if number and feeds[number]["piped"] else None
        yield from _commands_run_by(words, depth, feeds[number]["stdin"], before, new_only=True)
        bare, _cwd = _strip_command_prefix(words, TOOL_CWD)  # list[str]: from the command word on.
        if not bare:
            continue
        name = _command_name(bare[0])  # str: the command's name.
        if name == "eval":  # `eval <words>` runs its words as a command line.
            yield from _simple_commands(" ".join(bare[1:]), depth + 1)
        elif name in _SHELL_NAMES:  # `bash -c "<script>"`: the script is a command line.
            for index, arg in enumerate(bare[1:-1], 1):
                if re.match(r"^-[A-Za-z]*c[A-Za-z]*$", arg):
                    yield from _simple_commands(bare[index + 1], depth + 1)
                    break
        elif name == "find":  # `find ... -exec <command> {} ;` (or +): the command between -exec and ; / +.
            index = 1  # int: position in bare.
            while index < len(bare):
                if bare[index] in ("-exec", "-execdir", "-ok", "-okdir"):
                    end = next((pos for pos in range(index + 1, len(bare)) if bare[pos] in (";", "+")), len(bare))
                    yield bare[index + 1:end], []
                    index = end
                index += 1


def _exec_segments(bare: list[str]) -> list[list[str]]:
    """The commands (list of word lists) of `find ... -exec / -execdir / -ok / -okdir <command>;` (or `+`), read from a
    find command's words `bare` (list[str], from `find` on) as `_simple_commands` reads them."""
    segments: list[list[str]] = []  # list[list[str]]: one word list per -exec.
    index = 1  # int: position in bare.
    while index < len(bare):
        if bare[index] in ("-exec", "-execdir", "-ok", "-okdir"):
            end = next((pos for pos in range(index + 1, len(bare)) if bare[pos] in (";", "+")), len(bare))
            segments.append(bare[index + 1:end])
            index = end
        index += 1
    return segments


def _fed_texts(fed: list[str] | None, before: tuple[list[str], list[str]] | None) -> list[str]:
    """The texts a shell reads as its script from standard input (list[str]): what it was fed itself (`fed`: heredoc
    bodies, here-strings) and, when it is piped into (`before`: the previous command's words and what that one was fed),
    the text of an `echo` / `printf` (its arguments after its options, `\\n` and `\\t` read as escapes) or what a `cat`
    without a file operand was fed (`cat <<EOF | bash`). Not reached: a file (`bash < f`, `cat f | bash`), a program's
    output, a variable, process substitution (`bash <(...)`). The options of `echo` / `printf` are skipped by an index
    (`first`) instead of copying the rest of the arguments once per option; the arguments from `first` on are the list
    the copies left, so the text is the same."""
    texts = list(fed or [])  # list[str]: the texts found.
    if before:
        words, before_fed = before  # list[str], list[str]: the piped command's words and its fed texts.
        bare, _cwd = _strip_command_prefix(words, TOOL_CWD)  # list[str]: from the command word on.
        name = _command_name(bare[0]) if bare else ""  # str: its name.
        args = bare[1:]  # list[str]: its arguments.
        if name in ("echo", "printf"):
            first = 0  # int: the index of the first argument that is not an option.
            while first < len(args) and args[first].startswith("-") and len(args[first]) > 1 and args[first] != "--":
                first += 1  # Options (`echo -e`, `printf -v x`) are not the text.
            # str: the printed text, roughly - the arguments after the options.
            text = " ".join(arg for arg in args[first:] if arg != "--")
            texts.append(text.replace("\\n", "\n").replace("\\t", "\t"))
        elif name == "cat" and not [arg for arg in args if not arg.startswith("-") or arg == "-"]:
            texts += before_fed  # `cat <<EOF | bash`: the heredoc body is the script.
    return texts


# int: the deepest level `_commands_run_by` reads - `function` / `coproc` bodies and `-exec` commands counted together;
# a call is made only from levels below it, so a fourth level raises `_NestedTooDeep`. Three, as every other nested form
# of this file.
_RUN_BY_LEVELS = 3


def _commands_run_by(words: list[str], depth: int, fed: list[str] | None = None,
                     before: tuple[list[str], list[str]] | None = None, new_only: bool = False, body_depth: int = 0):
    """Yield (words, written redirect targets) of the commands one simple command (its words, list[str]) runs in turn.

    `new_only=True` (the call from `_simple_commands` for a line's own commands, whose eval, `-c` script and `-exec`
    commands it already yields) gives only what that reading does not: the commands a `find -exec` command runs in turn
    (it is read as a command of its own: a shell's `-c` script, eval, a nested find); a `trap` handler (its first
    operand, when a signal follows - `trap - EXIT` and `trap -p` set or print nothing); the body of `function f { ...;
    }` (the words after the name) and of `coproc`; and the script a shell without a `-c` option is fed (`_fed_texts`).
    `new_only=False` (an -exec command) adds eval and the `-c` script. A `coproc` body is read twice (`bare[1:]` and
    `bare[2:]`, with and without a NAME) by a call of this function at the same `depth`, so `coproc` written k times
    cost a number of calls growing like the Fibonacci numbers in k. `body_depth` (int, 0 for the command itself) counts
    the `function` / `coproc` bodies being read inside one another; a body past three levels raises `_NestedTooDeep`, as
    every other nested form of this file does, and `pre_bash` refuses the deeper line. The `find` branch called this
    function for each `-exec` command with `body_depth` back at 0, so a `coproc` pair in front of a `find` restarted the
    count at every `-exec` (`coproc coproc find. -exec` repeated: calls doubling per unit). Now EVERY call this function
    makes to itself passes the count on: a LEVEL is one `function` / `coproc` body or one `-exec` command read from the
    command one level up (the command itself is level 0); sibling `-exec`s of one `find` are each one level below that
    find, not below one another. A call is made only from levels 0, 1 and 2 (`_RUN_BY_LEVELS`); a fourth level raises
    `_NestedTooDeep`. Each level's calls read word lists that are disjoint ranges of the level above (a find's segments)
    or two overlapping ones (a `coproc` body with and without a NAME), so a command of w words makes at most 1 + 2w + 4w
    + 8w calls, each reading at most w words."""
    bare, _cwd = _strip_command_prefix(words, TOOL_CWD)  # list[str]: from the command word on.
    if not bare:
        return
    name = _command_name(bare[0])  # str: the command's name.
    is_c = any(re.match(r"^-[A-Za-z]*c[A-Za-z]*$", arg) for arg in bare[1:])  # bool: a shell's `-c` option.
    if not new_only and name == "eval":  # `eval <words>` runs its words as a command line.
        yield from _simple_commands(" ".join(bare[1:]), depth + 1)
    elif not new_only and name in _SHELL_NAMES and is_c:  # `bash -c "<script>"`: the script is a command line.
        for index, arg in enumerate(bare[1:-1], 1):
            if re.match(r"^-[A-Za-z]*c[A-Za-z]*$", arg):
                yield from _simple_commands(bare[index + 1], depth + 1)
                break
    if name == "find":  # Each -exec command: itself (unless already yielded) and what it runs in turn.
        for segment in _exec_segments(bare):
            if body_depth >= _RUN_BY_LEVELS:  # An -exec command at a fourth level - past the limit.
                raise _NestedTooDeep()
            if not new_only:
                yield segment, []
            # The -exec command, one level below this find.
            yield from _commands_run_by(segment, depth + 1, body_depth=body_depth + 1)
    elif name == "trap":  # `trap [--] '<command line>' <signal> ...`: the handler is a command line.
        index = 1  # int: position in bare; the options -p / -l (and "--") are skipped.
        while index < len(bare) and bare[index].startswith("-") and bare[index] != "-":
            index += 1
            if bare[index - 1] == "--":
                break
        if index + 1 < len(bare) and bare[index] != "-":  # A handler followed by at least one signal.
            yield from _simple_commands(bare[index], depth + 1)
    elif name in ("function", "coproc"):  # `function f { ...; }`, `coproc [NAME] <command>`: the body's words.
        for rest in ([bare[2:]] if name == "function" else [bare[1:], bare[2:]]):
            if rest:
                # A body at a fourth level - past the limit of the nested forms.
                if body_depth >= _RUN_BY_LEVELS:
                    raise _NestedTooDeep()
                yield rest, []
                # The body's own commands, one body level deeper.
                yield from _commands_run_by(rest, depth, body_depth=body_depth + 1)
    if name in _SHELL_NAMES and not is_c:  # A shell without -c reads its script from standard input.
        for text in _fed_texts(fed, before):
            yield from _simple_commands(text, depth + 1)


def _short_cluster_has(option: str, letters: str) -> bool:
    """True when `option` (str) is a cluster of short options (`-x`, `-xyz`: one "-", letters only) holding one of
    `letters` (str)."""
    return re.match(r"^-[A-Za-z]+$", option) is not None and any(letter in option[1:] for letter in letters)


def _long_option_prefix(option: str, names: tuple[str, ...], least: int) -> bool:
    """True when `option` (str, case folded, any "=value" removed) is one of `names` or an abbreviation of one at
    least `least` characters long (GNU getopt and Git's parse-options accept an unambiguous prefix of a long option;
    `least` is chosen so that the prefix is unambiguous among the command's own long options)."""
    name = option.split("=", 1)[0].lower()  # str: the option's name.
    return name.startswith("--") and len(name) >= least and any(full.startswith(name) for full in names)


def _rm_recursive(args: list[str]) -> bool:
    """True when the arguments of `rm` (list[str], after the command word) hold a recursive option.

    GNU rm reads its options wherever they stand among the arguments (until "--"), so every option word counts: a
    cluster of short options holding "r" or "R" (`-r`, `-fr`, `-vR`; PowerShell's alias `rm -Recurse` / `-r` too), or
    `--recursive` or an abbreviation of it (`--rec`, `--r`: no other long option of rm starts with "--r")."""
    for arg in args:
        if arg == "--":  # Everything after is a file name, even "-r".
            return False
        if arg.startswith("--"):
            if _long_option_prefix(arg, ("--recursive",), 3):
                return True
        elif arg.startswith("-") and len(arg) > 1 and "r" in arg[1:].lower():
            return True
    return False


def _git_destructive(args: list[str]) -> str:
    """The reason (str) of the destructive git rule the words after `git` (list[str]) break, or "".

    git's own options before the sub-command are skipped (`-P`, `--no-pager`, `-c <name>=<value>`, ...); among them
    `-C`, `--git-dir` and `--work-tree`, with or without "=", are another repository. The sub-command is matched
    case-folded (as the text patterns, which use re.I); its option words are read wherever they stand before "--".
    The rules are those of _DENY_PATTERNS, judged on words: push; pull / merge / rebase / cherry-pick; fetch with
    `--prune` / `--prune-tags` or a short cluster holding p / P; reset with `--hard` / `--merge` (or an abbreviation:
    `--ha`, `--me`); clean / stash / filter-branch / filter-repo; checkout / restore / switch without -b / -B / -c /
    -C / --orphan in the same command (the patterns' look-aheads read to the end of the line); branch with `--delete`
    or a short cluster holding d / D; tag with `--delete` or a cluster holding d; reflog expire / delete; gc with
    `--prune`; update-ref with `-d`."""
    index = 0  # int: position in args; git's own options are skipped.
    while index < len(args) and args[index].startswith("-"):
        option = args[index]  # str: one of git's own options.
        if option.split("=", 1)[0] in ("-C", "--git-dir", "--work-tree"):
            return _REASON_GIT_DIR
        index += 2 if option in _GIT_GLOBAL_VALUE_OPTIONS and "=" not in option else 1
    if index >= len(args):
        return ""
    sub = args[index].lower()  # str: the sub-command, case folded.
    rest = args[index + 1:]  # list[str]: the sub-command's words.
    options = []  # list[str]: its option words before "--".
    for arg in rest:
        if arg == "--":
            break
        if arg.startswith("-") and len(arg) > 1:
            options.append(arg)
    lowered = [option.lower() for option in options]  # list[str]: the same, case folded.
    if sub == "push":
        return _REASON_PUSH
    if sub in ("pull", "merge", "rebase", "cherry-pick"):
        return _REASON_MERGE
    if sub == "fetch" and any(low.startswith("--prune") or _short_cluster_has(opt, "pP")
                              for opt, low in zip(options, lowered)):
        return _REASON_MERGE
    if sub == "reset" and any(_long_option_prefix(low, ("--hard", "--merge"), 4) for low in lowered):
        return _REASON_RESET
    if sub in ("clean", "stash", "filter-branch", "filter-repo"):
        return _REASON_TREE
    if sub in ("checkout", "restore", "switch") and not any(low in ("-b", "-c") or low.startswith("--orphan")
                                                            for low in lowered):
        return _REASON_CHECKOUT
    if sub == "branch" and any(low == "--delete" or _short_cluster_has(opt, "dD")
                               for opt, low in zip(options, lowered)):
        return _REASON_REFS
    if sub == "tag" and any(low == "--delete" or _short_cluster_has(opt, "d") for opt, low in zip(options, lowered)):
        return _REASON_REFS
    if sub == "reflog" and next((arg for arg in rest if not arg.startswith("-")), "").lower() in ("expire", "delete"):
        return _REASON_REFS
    if sub == "gc" and any(low.startswith("--prune") for low in lowered):
        return _REASON_REFS
    if sub == "update-ref" and "-d" in options:
        return _REASON_REFS
    return ""


def _destructive_command(command: str, kind: str = "all") -> str:
    """The reason (str) of the first destructive rule a simple command of `command` breaks, judged on its words; "".

    Seen wherever `_simple_commands` sees a command (separators, groups, keywords, prefix words with their options,
    substitutions, eval, `bash -c`, `find -exec`): `rm` with a recursive option word anywhere among its arguments
    (`_rm_recursive`); PowerShell's Remove-Item / ri and cmd's rmdir / rd / del / erase with `-Recurse` (any
    abbreviation from `-r`) or `/s` anywhere (del / erase also `/q`), as their text patterns refuse right after the
    name; and the git rules of `_git_destructive` for a `git` / `git.exe` command word (any case, behind a path). Not
    seen, besides the reader's limits: a command named through a variable or an alias, a function, a script, a program
    that removes or runs git (Python `shutil.rmtree`, `subprocess`)."""
    for words, _targets in _simple_commands(command):
        bare, _cwd = _strip_command_prefix(words, TOOL_CWD)  # list[str]: from the command word on.
        if not bare:
            continue
        name = _command_name(bare[0])  # str: the command's name.
        args = bare[1:]  # list[str]: its arguments.
        if kind == "git" and not _is_git_word(bare[0]):
            continue  # Only the git rules are judged for this kind.
        if kind != "git" and name == "rm" and _rm_recursive(args):
            return _REASON_RM
        if kind != "git" and name in ("remove-item", "ri", "rmdir", "rd", "del", "erase"):
            recurse = any(arg.lower() in ("/s", "-r") or (arg.lower().startswith("-r") and "-recurse".startswith(
                arg.lower())) for arg in args)  # bool: a recursive option (PowerShell -Recurse, cmd /s).
            if recurse and name in ("remove-item", "ri"):
                return _REASON_REMOVE_ITEM
            if recurse and name in ("rmdir", "rd"):
                return _REASON_RMDIR
            if (recurse or any(arg.lower() == "/q" for arg in args)) and name in ("del", "erase"):
                return _REASON_DEL
        if kind != "files" and _is_git_word(bare[0]):
            reason = _git_destructive(args)  # str: the git rule broken, or "".
            if reason:
                return reason
    return ""


# `git checkout` / `git switch` keep their new-branch exemption (-b / -B / -c / -C / --orphan) only without an option
# that throws away the working tree's changes: -f / --force (checkout and switch; switch's --discard-changes is the
# same), -m / --merge (a three-way merge of local changes that can leave them in conflict). Git's documentation
# (recalled, not run): `git checkout -f -b <new>` and `git switch --discard-changes -c <new>` discard every uncommitted
# change before the branch is made. str: the refusal's reason.
_REASON_FORCED_BRANCH = ("git checkout/switch with a new branch (-b/-B/-c/-C/--orphan) and -f/--force/"
                         "--discard-changes/-m/--merge discards or merges the shared working tree's uncommitted "
                         "changes (R6). Approve only if you asked for it; otherwise create the branch without that option.")


def _forced_branch_creation(command: str) -> str:
    """The reason (str) when a `git checkout` / `git switch` simple command of `command` holds both a new-branch option and
    a force or merge option, else "".

    Read on the word reader's simple commands (`_simple_commands`), git's own options skipped as `_git_destructive`
    skips them; option words before "--": a new-branch option as the destructive rule reads it (-b / -c in any case,
    --orphan...), a force or merge option as a short cluster holding f or m (`-f`, `-qf`, `-m`) or a long option or its
    abbreviation (`--f...` of --force, `--di...` of --discard-changes, `--m...` of --merge; an abbreviation Git finds
    ambiguous is refused by Git anyway)."""
    for words, _targets in _simple_commands(command):
        bare, _cwd = _strip_command_prefix(words, TOOL_CWD)  # list[str]: from the command word on.
        if not bare or not _is_git_word(bare[0]):
            continue
        args = bare[1:]  # list[str]: the words after git.
        index = 0  # int: position in args; git's own options are skipped.
        while index < len(args) and args[index].startswith("-"):
            index += 2 if args[index] in _GIT_GLOBAL_VALUE_OPTIONS and "=" not in args[index] else 1
        if index >= len(args) or args[index].lower() not in ("checkout", "switch"):
            continue
        options = []  # list[str]: the sub-command's option words before "--".
        for arg in args[index + 1:]:
            if arg == "--":
                break
            if arg.startswith("-") and len(arg) > 1:
                options.append(arg)
        lowered = [option.lower() for option in options]  # list[str]: the same, case folded.
        new_branch = any(low in ("-b", "-c") or low.startswith("--orphan") for low in lowered)  # bool.
        forced = any(_short_cluster_has(opt, "fm") or _long_option_prefix(low, ("--force", "--merge"), 3)
                     or _long_option_prefix(low, ("--discard-changes",), 4)
                     for opt, low in zip(options, lowered))  # bool: a force or merge option.
        if new_branch and forced:
            return _REASON_FORCED_BRANCH
    return ""


# Dict[str, set[str]]: per command, the options whose value is the next word when written without "=" (so a value is not
# taken for a source or a target): rsync's filters, shells and folders, install's mode / owner / group, the backup
# suffix of cp / ln / mv / install, sed's script / file / line length, perl's program.
_WRITE_VALUE_OPTIONS = {
    "rsync": {"-e", "--rsh", "--exclude", "--include", "--filter", "-f", "--exclude-from", "--include-from",
              "--files-from", "--log-file", "--temp-dir", "-T", "--partial-dir", "--backup-dir", "--compare-dest",
              "--copy-dest", "--link-dest", "--chmod", "--chown", "--suffix", "--rsync-path", "--password-file",
              "--max-size", "--min-size", "--timeout", "--bwlimit", "--port"},
    "install": {"-m", "--mode", "-o", "--owner", "-g", "--group", "-S", "--suffix"},
    "cp": {"-S", "--suffix"}, "ln": {"-S", "--suffix"}, "mv": {"-S", "--suffix"},
    "sed": {"-e", "-f", "-l", "--expression", "--file", "--line-length"},
    "perl": {"-e", "-E", "-I", "-M", "-m", "-x", "-F"},
}
# set[str]: the commands (GNU coreutils) whose short option `-t` takes the target folder, attached
# (`-t.git/hooks`) or in a cluster (`-rt <dir>`); rsync's `-t` keeps the modification times instead and is
# not among them.
_DASH_T_TARGET = {"cp", "ln", "install", "mv"}
# set[str]: the commands that move or copy their sources into a destination named last (or by -t / -Destination); for
# them a folder destination also receives `<destination>/<source's last name>`.
_COPY_INTO = _WRITE_LAST_OPERAND | {"mv", "move", "move-item"}
# dict[str, str]: per in-place editor, the short-option letters after which the rest of the word is a value (so a
# later "i" is part of that value, not the in-place switch): sed -e SCRIPT / -f FILE / -l N; perl -e CODE, -I DIR,
# -M / -m MODULE, -x DIR, -F PATTERN, -d / -D / -C settings.
_IN_PLACE_STOP = {"sed": "efl", "perl": "eEIMmxFdDC"}
_FOLDER_LIST_LIMIT = 4096  # int: the most entries of one source folder listed for a folder-contents copy.


def _in_place(name: str, args: list[str]) -> bool:
    """True when `sed` / `perl` (name, str) is told by its arguments (list[str]) to edit its files in place.

    A short-option cluster holding "i" before any value-taking letter (_IN_PLACE_STOP): `-i`, `-i.bak`, `-Ei`, `-ni`,
    `-pi`, `-lpi`, `-pie` (sed `-ei` is the script "i", not in place); sed's `--in-place[=SUFFIX]` or an abbreviation of
    it from `--in`."""
    for arg in args:
        if arg == "--":
            return False
        if arg.startswith("--"):
            if name == "sed" and _long_option_prefix(arg, ("--in-place",), 4):
                return True
            continue
        if arg.startswith("-") and len(arg) > 1:
            for letter in arg[1:]:
                if letter == "i":
                    return True
                if letter in _IN_PLACE_STOP.get(name, "") or not letter.isalpha():
                    break  # The rest of the word is this option's value.
    return False


def _folder_entries(source: str, cwd: str) -> list[str]:
    """The names (list[str]) in the folder `source` (a word, relative to `cwd`) when it is an existing folder inside the
    project; [] otherwise. Used only for a copy of a folder's contents (`src/.`, rsync's `src/`), whose written
    names are the folder's entries; at most _FOLDER_LIST_LIMIT names, links not followed for the listing itself."""
    abs_path = _to_abs(source, base=cwd)  # str | None: the folder, links resolved.
    if abs_path is None or not _inside(abs_path) or not os.path.isdir(abs_path):
        return []
    try:
        return sorted(os.listdir(abs_path))[:_FOLDER_LIST_LIMIT]
    except OSError:
        return []


def _command_write_words(name: str, args: list[str], cwd: str) -> list[str]:
    """The written target words (list[str], as the shell gives them, relative to `cwd`) of one simple command.

    The commands of _WRITE_ALL_OPERANDS write every operand (and a -t value); sed / perl in place (`_in_place`) write
    every operand; the commands of _COPY_INTO write the destination - the -t / --target-directory (also abbreviated
    from `--targ`, or attached / clustered for cp, ln, install, mv: `-t.git/hooks`, `-rt <dir>`) or -Destination
    (abbreviated from `-des`) value, else the last operand - and, when that destination is a folder (a -t value, two
    or more sources, a trailing "/", ".", or an existing folder), `<destination>/<source's last name>` for each source,
    or `<destination>/<entry>` for each entry of a source folder whose contents are copied (`src/.`, `.`, rsync's
    `src/`); `dd of=` writes its file. Option values (_WRITE_VALUE_OPTIONS) are not operands."""
    operands: list[str] = []  # Words that are not options.
    flagged: list[str] = []  # Values of the target-folder options.
    value_options = _WRITE_VALUE_OPTIONS.get(name, set())  # set[str]: this command's options that take a value.
    # bool: the command takes its target folder from -t / --target-directory / -Destination; not rsync, whose -t keeps
    # the modification times.
    targets_by_option = name in _COPY_INTO and name != "rsync"
    options_done = False  # bool: True after "--".
    index = 0  # int: position in args.
    while index < len(args):
        arg = args[index]  # str: one argument.
        nxt = args[index + 1] if index + 1 < len(args) else None  # str | None: the word after it.
        index += 1
        if options_done or arg == "-" or not arg.startswith("-"):
            operands.append(arg)
            continue
        if arg == "--":
            options_done = True
            continue
        low = arg.lower()  # str: the option, case folded (PowerShell options are case-insensitive).
        if targets_by_option and (low in _TARGET_OPTIONS or (len(low) >= 4 and "-destination".startswith(low))
                                  or (_long_option_prefix(low, ("--target-directory",), 6) and "=" not in low)):
            if nxt is not None:
                flagged.append(nxt)  # The next word is the target folder.
                index += 1
            continue
        if targets_by_option and "=" in low and _long_option_prefix(low, ("--target-directory",), 6):
            flagged.append(arg.split("=", 1)[1])  # `--target-directory=<dir>`, `--target-dir=<dir>`, `--targ=<dir>`.
            continue
        clustered = re.match(r"^-([A-Za-z]*?)t(.*)$", arg) if name in _DASH_T_TARGET else None  # re.Match | None.
        if clustered and not arg.startswith("--"):
            if clustered.group(2):
                flagged.append(clustered.group(2))  # `-t<dir>`, `-rt<dir>`: the rest of the word is the folder.
            elif nxt is not None:
                flagged.append(nxt)  # `-t <dir>`, `-rt <dir>`: the next word is the folder.
                index += 1
            continue
        if arg.split("=", 1)[0] in value_options and "=" not in arg and nxt is not None:
            index += 1  # This option's value is the next word, not an operand.
    if name in _WRITE_ALL_OPERANDS and name not in _COPY_INTO:
        return operands + flagged
    if name in ("sed", "perl"):
        return operands + flagged if _in_place(name, args) else []
    if name == "dd":
        return [arg[3:] for arg in args if arg.startswith("of=")]
    if name not in _COPY_INTO:
        return []
    destination = flagged[-1] if flagged else (operands[-1] if operands else None)  # str | None: the target.
    if destination is None:
        return []
    sources = operands if flagged else operands[:-1]  # list[str]: the words copied or moved into it.
    written = [destination] + (sources if name in ("mv", "move", "move-item") else [])  # mv also removes its sources.
    dest_abs = _to_abs(destination, base=cwd)  # str | None: the destination, links resolved.
    is_folder = bool(flagged) or len(sources) > 1 or destination.endswith(("/", "\\")) \
        or destination in (".", "./") or (dest_abs is not None and os.path.isdir(dest_abs))  # bool: a folder.
    if not is_folder:
        return written
    for source in sources:
        trimmed = source.rstrip("/\\")  # str: the source without a trailing separator.
        contents = source in (".", "./") or source.endswith(("/.", "\\.")) or (
            name == "rsync" and source.endswith(("/", "\\")))  # bool: the folder's contents are copied, not itself.
        if contents:
            written += [destination.rstrip("/\\") + "/" + entry for entry in _folder_entries(source, cwd)]
        elif trimmed and os.path.basename(trimmed.replace("\\", "/")) not in ("", ".", ".."):
            written.append(destination.rstrip("/\\") + "/" + os.path.basename(trimmed.replace("\\", "/")))
    return written


def _is_hard_link(name: str, args: list[str]) -> bool:
    """True when the command (name, str; args, list[str]) makes hard links: `ln` without `-s` / `--symbolic` (a short
    cluster holding "s", or `--sym...`), or `cp` with `-l` / `--link` (a short cluster holding "l", as in `cp -al`)."""
    options = [arg for arg in args if arg.startswith("-") and len(arg) > 1]  # list[str]: the option words.
    if name == "ln":
        return not any(_short_cluster_has(opt, "s") or _long_option_prefix(opt, ("--symbolic",), 4) for opt in options)
    if name == "cp":
        return any(_short_cluster_has(opt, "l") or _long_option_prefix(opt, ("--link",), 4) for opt in options)
    return False


def _link_sources(args: list[str]) -> list[str]:
    """The source operands (list[str]) of `ln` / `cp` arguments (list[str]): every operand when the target folder is
    given by `-t` (attached, clustered or separate) or `--target-directory`, else every operand but the last; option
    values (`-S <suffix>`, the -t folder) are not operands."""
    operands: list[str] = []  # Words that are not options.
    has_target = False  # bool: the target folder was named by an option.
    skip = False  # bool: the next word is an option's value.
    done = False  # bool: after "--".
    for arg in args:
        if skip:
            skip = False
            continue
        if done or arg == "-" or not arg.startswith("-"):
            operands.append(arg)
            continue
        if arg == "--":
            done = True
            continue
        clustered = re.match(r"^-([A-Za-z]*?)t(.*)$", arg) if not arg.startswith("--") else None  # re.Match | None.
        if clustered:
            has_target, skip = True, not clustered.group(2)  # `-t <dir>` takes the next word; `-t<dir>` does not.
        elif _long_option_prefix(arg, ("--target-directory",), 6):
            has_target, skip = True, "=" not in arg
        elif arg in ("-S", "--suffix"):
            skip = True
    return operands if has_target else operands[:-1]


def _word_write_targets(command: str, link_sources: list[tuple[str, str]] | None = None,
                        records: list[tuple[str, str, str]] | None = None,
                        scope_values: bool = False) -> list[tuple[str, str]]:
    """The literal write targets of a shell command read as words, as (word, folder it is relative to) pairs.

    Every simple command `_simple_commands` yields (separators, groups, keywords, substitutions, eval, a shell's `-c`
    script, `find -exec`): its output redirects (`>`, `>>`, `>|`, `&>`, `>&file`), taken from the folder the line is in;
    then, after `_strip_command_prefix` (assignments, keywords, prefix words with their options; `env -C <dir>` moves
    the folder of that command only), the targets `_command_write_words` reads. The folder moves with `cd` / `chdir` /
    `Set-Location` / `sl` (`cd -` returns to the folder before the last move in this line, when there was one), `pushd
    <dir>` (remembered) and `popd` (back to the remembered folder); a move inside a sub-shell is kept for the rest of
    the line (a stricter reading). Quotes and backslashes are removed as the shell removes them, so `.cla""ude` and
    `.c\\laude` read `.claude`. Not seen: what a program writes by itself, a word built from a variable, a glob or a
    substitution (skipped by `_shell_harness_class`), a `cd` through a variable, and a folder copied whole whose harness
    names lie deeper than its first level (`cp -r work/tmp/<s>/tree .` writes `./tree/.claude/...`). When `link_sources`
    (a list) is given, the source operands of every command that makes hard links (`_is_hard_link`: `ln` without -s, `cp
    -l`) are appended to it as (word, folder) pairs. When `records` (a list) is given, every target is appended to it as
    (word, folder, command name) - ">" for a redirect - so a rule can tell a write through a file from removing a name.
    `scope_values=True` (the ADVISOR scope rule only) reads each command's arguments without the value operands
    `_scope_args` names (`chmod 644`, `touch -d <date>`, a sed script ...)."""
    targets: list[tuple[str, str]] = []  # The pairs found so far.
    cwd = TOOL_CWD  # str: the folder the next command runs in.
    previous: str | None = None  # str | None: the folder before the last move (for `cd -`), None while unknown.
    stack: list[str] = []  # list[str]: the folders `pushd` remembered, last on top.
    for words, redirects in _simple_commands(command):
        targets += [(word, cwd) for word in redirects]
        if records is not None:  # The redirects, named ">".
            records += [(word, cwd, ">") for word in redirects]
        bare, run_cwd = _strip_command_prefix(words, cwd)  # list[str], str: the command and the folder it runs in.
        if not bare:
            continue
        name = _command_name(bare[0])  # str: the command's name.
        args = _scope_args(name, bare[1:]) if scope_values else bare[1:]  # list[str]: its arguments.
        if name in _CD_WORDS or name == "popd":
            target = next((arg for arg in args if not arg.startswith(("-", "+")) or arg == "-"), None)  # str | None.
            if name == "popd":
                moved = stack.pop() if stack else None  # str | None: the remembered folder.
            elif target == "-":
                moved = previous  # `cd -`: the folder before the last move, if this line made one.
            elif target is None:
                moved = None  # `cd` alone goes home (outside the project); `pushd` alone swaps: not followed.
            else:
                moved = _to_abs(target, base=cwd)  # str | None: the folder named.
            if moved is not None and _inside(moved):
                if name == "pushd":
                    stack.append(cwd)
                previous, cwd = cwd, moved
            continue
        targets += [(word, run_cwd) for word in _command_write_words(name, args, run_cwd)]
        targets += [(word, run_cwd) for word in _more_write_words(name, args, run_cwd)]
        if records is not None:  # The same targets with the command's name.
            records += [(word, run_cwd, name) for word in _command_write_words(name, args, run_cwd)
                        + _more_write_words(name, args, run_cwd)]
        if link_sources is not None and _is_hard_link(name, args):  # The files a hard link is made to.
            link_sources += [(word, run_cwd) for word in _link_sources(args)]
    return targets


# Tuple[str, ...]: the commands whose `--t...` abbreviates --target-directory (GNU's `--help` of the installed coreutils
# lists no other long option starting `--t` for cp, mv, ln or install) and whose `-T` / `--no-target-directory` makes
# the destination the copy itself (its contents are the source's contents).
_TARGET_DIR_COMMANDS = ("cp", "mv", "ln", "install")


def _perl_cluster(arg: str) -> str:
    """A perl switch cluster (str) with `-0[digits]` / `-0x[hex]` and `-l[digits]` taken out, up to the first switch
    that takes the rest of the word as its value (_IN_PLACE_STOP), so `_in_place` sees the letters after them
    (`-0pi`, `-0777pi`, `-l0pi` -> `-pi`); perl's own reading (`perl -h`: `-0[octal/hexadecimal]`, `-l[octnum]`)."""
    body = arg[1:]  # str: the switches after the "-".
    out: list[str] = []  # list[str]: the switches kept.
    index = 0  # int: position in body.
    while index < len(body):
        letter = body[index]  # str: one switch.
        if letter in _IN_PLACE_STOP["perl"]:  # The rest of the word is this switch's value: kept as written.
            out.append(body[index:])
            break
        if letter == "0":  # -0 with octal digits, or -0x with hex digits.
            index += 1
            if body[index:index + 1] in ("x", "X"):
                index += 1
                while index < len(body) and body[index] in "0123456789abcdefABCDEF":
                    index += 1
            else:
                while index < len(body) and body[index] in "01234567":
                    index += 1
            continue
        if letter == "l":  # -l with octal digits.
            index += 1
            while index < len(body) and body[index] in "01234567":
                index += 1
            continue
        out.append(letter)
        index += 1
    return "-" + "".join(out)


def _normalize_write_args(name: str, args: list[str]) -> list[str]:
    """Other words are unchanged; nothing after "--"."""
    out: list[str] = []  # list[str]: the arguments, written out.
    for index, arg in enumerate(args):
        if arg == "--":
            return out + args[index:]
        low = arg.lower()  # str: the option, case folded.
        value = arg[arg.index("="):] if "=" in arg else ""  # str: an "=value" part, kept.
        if name in _TARGET_DIR_COMMANDS and _long_option_prefix(low, ("--target-directory",), 3):
            out.append("--target-directory" + value)
        elif name == "sed" and _long_option_prefix(low, ("--in-place",), 3):
            out.append("--in-place" + value)
        elif name == "perl" and arg.startswith("-") and not arg.startswith("--") and len(arg) > 1:
            out.append(_perl_cluster(arg))
        else:
            out.append(arg)
    return out


def _copy_contents_writes(name: str, args: list[str], cwd: str) -> list[str]:
    """<new folder>`); rsync with `src` (no trailing "/") to a new destination writes `<destination>/<src's last name>`. []
    otherwise (a -t folder, several sources, a file)."""
    if name not in _TARGET_DIR_COMMANDS and name != "rsync":
        return []
    operands: list[str] = []  # list[str]: the words that are not options.
    recursive = name in ("mv", "rsync")  # bool: the copy takes folders whole (mv and rsync always do).
    no_target = False  # bool: -T / --no-target-directory given.
    value_options = _WRITE_VALUE_OPTIONS.get(name, set())  # set[str]: options whose value is the next word.
    index = 0  # int: position in args.
    while index < len(args):
        arg = args[index]  # str: one argument.
        index += 1
        if arg == "--":
            operands += args[index:]
            break
        if arg == "-" or not arg.startswith("-"):
            operands.append(arg)
            continue
        low = arg.lower()  # str: the option, case folded.
        if arg.split("=", 1)[0] in value_options and "=" not in arg:
            index += 1  # The option's value is the next word.
        elif _long_option_prefix(low, ("--target-directory",), 3) or (
                name != "rsync" and not arg.startswith("--") and re.match(r"^-[A-Za-z]*t", arg)):
            return []  # A target folder named by an option: `_command_write_words` reads that form.
        elif _long_option_prefix(low, ("--no-target-directory",), 6) or (_short_cluster_has(arg, "T")
                                                                         and name != "rsync"):
            no_target = True
        elif _short_cluster_has(arg, "rRa") or _long_option_prefix(low, ("--recursive", "--archive"), 4):
            recursive = True
    if len(operands) != 2:
        return []
    source, destination = operands  # str, str: the one source and the destination.
    entries = _folder_entries(source, cwd)  # list[str]: the source folder's first-level names ([] for a file).
    dest_abs = _to_abs(destination, base=cwd)  # str | None: the destination, links resolved.
    new_destination = dest_abs is not None and not os.path.exists(dest_abs)  # bool: it does not exist yet.
    dest = destination.rstrip("/\\")  # str: the destination without a trailing separator.
    if name == "rsync" and not source.endswith(("/", "\\")):
        trimmed = source.rstrip("/\\")  # str: the source folder's name as written.
        return [dest + "/" + os.path.basename(trimmed)] if entries and new_destination else []
    if no_target or (recursive and new_destination):
        return [dest + "/" + entry for entry in entries]
    return []


def _more_write_words(name: str, args: list[str], cwd: str) -> list[str]:
    """The write targets of one simple command (list[str]) that `_command_write_words` misses: its reading of the arguments
    with the abbreviations written out (`_normalize_write_args`: `cp --t=<dir>`, `sed --i`, `perl -0pi`), and the
    folder-image copies of `_copy_contents_writes` (`cp -rT <tree> .`)."""
    normalized = _normalize_write_args(name, args)  # list[str]: the arguments, abbreviations written out.
    written = _command_write_words(name, normalized, cwd) if normalized != args else []  # list[str]: targets.
    return written + _copy_contents_writes(name, normalized, cwd)


# str: the operator token `_real_folder_records` puts between its two readings of a line; no shell text can produce it
# (the tokenizers emit only the operators of _SHELL_OPERATORS).
_READING_RESTART = "\x00installed reading"  # str: a NUL first, so never a shell operator.


def _real_folder_records(command: str, start: list[str] | None = None, depth: int = 0,
                         link_sources: list[tuple[str, str]] | None = None,
                         scope_values: bool = False) -> list[tuple[str, str, str]]:
    """The literal write targets of a shell command judged from the folders the shell may really be in, as (word, folder,
    command name) triples (">" for a redirect).

    The line is walked in BOTH word readings, each from the starting folders - the new one (`_shell_tokens`) and the
    installed one (`_shell_tokens_installed`), joined by a restart marker (_READING_RESTART) - and the triples of both
    are returned (repeats once), so a line the new reading gets wrong still yields what the installed reading sees; when
    the new reading meets an unclosed quote, its lines are read one by one (each again in both readings) and the
    installed reading of the whole text is walked as well.

    The word reader `_word_write_targets` follows every `cd` as if it succeeded and stayed (a `cd` in a sub-shell is
    kept for the rest of the line, a stricter reading there), so `cd work/tmp/<missing>; cp x .claude/settings.json` was
    read as a scratch write. This reader keeps, per point of the line, the set of folders the shell can be in:
    - a `cd` / `pushd` / `popd` / `cd -` in a pipeline (`cd x | cat`), a background job (`cd x &`), a sub-shell or a
      substitution (`( ... )`, `$( ... )`, `<( ... )`) moves nothing after that element or group;
    - otherwise the commands joined to it by `&&` run only when it succeeded, so they are judged from the new folder
      alone (no false refusal for `cd <folder> && <command>`, whether the folder exists yet or not); after `;`, a
      newline, `||` or `&`, the folder before is kept beside the new one unless the new one exists now (a `cd` to an
      existing folder inside the project succeeds), so a `cd` that may fail does not hide the folder the shell stays in.
      Targets per simple command as the word reader reads them (`_command_write_words`, `_more_write_words`, output
      redirects; `env -C`), judged from each such folder; the commands it runs in turn (`_commands_run_by`: eval, a
      shell's `-c` script, `find -exec`, a trap handler, a function body, a fed shell) and the substitutions inside it
      (`_inner_command_texts`) are judged from the folders the command runs in, without moving them. A text with an
      unclosed quote is read line by line. Not seen: what `_word_write_targets` does not see either. `scope_values=True`
      (the ADVISOR scope rule only) drops the value operands `_scope_args` names from each command's arguments before
      its targets are read. Every `cd` to a folder that does not exist keeps the folder before beside the new one, so k
      such `cd`s joined by `;` left 2**k folders, each resolved at every later `cd` (time and memory). The set's size is
      checked where it grows (`_folder_set_check`): past `_FOLDER_SET_LIMIT` folders `_TooManyFolders` is raised and
      `pre_bash` refuses the line."""
    if depth > 3:  # The same limit as the other parsers.
        raise _NestedTooDeep()
    cwds = list(start) if start else [TOOL_CWD]  # list[str]: the folders the shell may be in now.
    records: list[tuple[str, str, str]] = []  # The triples found so far.
    bodies: list[tuple[int, str]] = []  # list[(int, str)]: heredoc bodies by their operator's token index.
    try:
        tokens = _shell_tokens(command, bodies)  # list[tuple[str, str]]: the line's tokens (the new reading).
    except ValueError:
        tokens = []  # The new reading yields nothing for the whole text; its lines are read one by one.
        lines = command.split("\n")  # list[str]: the text's lines, each read on its own (see `_simple_commands`).
        for line in lines if len(lines) > 1 else []:
            records += _real_folder_records(line, cwds, depth, link_sources, scope_values)
    try:
        installed = _shell_tokens_installed(command)  # list[tuple[str, str]]: the installed reading.
    except ValueError:
        installed = []  # An unclosed quote for the installed reader too: it yields nothing, as it did.
    # list[tuple[str, str]]: one walk over both readings; the marker starts the installed one afresh. The heredoc bodies
    # (body_of) are indexed in the new reading only, which comes first, so no index of the installed reading (all past
    # the marker) can meet one.
    tokens = tokens + [("op", _READING_RESTART)] + installed  # New reading, marker, installed reading.
    for text in _inner_command_texts(command):  # Substitutions run in a sub-shell: judged, never moving the folder.
        records += _real_folder_records(text, cwds, depth + 1, link_sources, scope_values)
    body_of = dict(bodies)  # dict[int, str]: the body of the heredoc whose `<<` is that token.
    carry: list[str] = []  # list[str]: folders where a `cd` of the current `&&` chain may have failed.
    stack: list[tuple[list[str], list[str]]] = []  # list: (folders, carry) saved at each "(" / "<(" / ">(".
    pushed: list[list[str]] = []  # list[list[str]]: the folders `pushd` remembered, last on top.
    previous: list[str] | None = None  # list[str] | None: the folders before the last move (for `cd -`).
    words: list[str] = []  # list[str]: the current simple command's words.
    redirects: list[str] = []  # list[str]: its output redirect targets.
    fed: list[str] = []  # list[str]: the texts fed to its standard input.
    piped_in = False  # bool: it follows "|" / "|&".
    last: tuple[list[str], list[str]] | None = None  # The previous command's (words, fed), for a pipe into a shell.

    def dedupe(folders: list[str]) -> list[str]:
        """`folders` (list[str]) without repeats, in order."""
        return list(dict.fromkeys(folders))

    def finish(terminator: str) -> None:
        """Judge the current simple command, which ends at `terminator` (an operator, "" at the end of the text)."""
        nonlocal cwds, carry, previous, last
        if not (words or redirects):
            return
        # One judgment (or `cd` resolution) per folder beyond the first, counted here once per finished command (a `cd`
        # and a command with redirects only included), against the event's bound `_FOLDER_WORK_LIMIT`.
        _folder_work_add(cwds)
        records.extend((word, folder, ">") for folder in cwds for word in redirects)
        bare, _cwd = _strip_command_prefix(words, cwds[0])  # list[str]: from the command word on.
        name = _command_name(bare[0]) if bare else ""  # str: the command's name.
        args = bare[1:]  # list[str]: its arguments.
        if name in _CD_WORDS or name == "popd":
            if piped_in or terminator in ("|", "|&", "&"):
                return  # A pipeline element or a background job runs in a sub-shell: nothing moves.
            target = next((arg for arg in args if not arg.startswith(("-", "+")) or arg == "-"), None)  # str | None.
            if name == "popd":
                moved = pushed.pop() if pushed else None  # list[str] | None: the remembered folders.
                failed: list[str] = []  # list[str]: folders where the move may fail.
            elif target == "-":
                moved, failed = previous, []  # `cd -`: the folders before the last move, when this line made one.
            elif target is None:
                moved, failed = None, []  # `cd` alone goes home (outside the project): not followed.
            else:
                resolved = [(folder, _to_abs(target, base=folder)) for folder in cwds]  # (from, to) pairs.
                moved = [to for _f, to in resolved if to is not None and _inside(to)]
                failed = [folder for folder, to in resolved if to is None or not os.path.isdir(to)]
            if moved:
                if name == "pushd":
                    pushed.append(list(cwds))
                previous, cwds = list(cwds), _folder_set_check(dedupe(moved))  # The set's size checked.
                # The carry checked too - inside one `&&` chain it takes a folder per `cd` that may fail while the set
                # stays one folder (`cd d && ` written m times: a carry of m, each `cd` resolved one level deeper - the
                # square), so past `_FOLDER_SET_LIMIT` the line is refused with the same reason.
                carry = _folder_set_check(dedupe(carry + failed))
            return
        for folder in cwds:  # Every other command: its targets from each folder it may run in.
            bare_f, run_cwd = _strip_command_prefix(words, folder)  # list[str], str: `env -C` moves run_cwd.
            if not bare_f:
                continue
            # list[str]: the arguments read for targets, value operands dropped for the scope rule.
            read_args = _scope_args(name, bare_f[1:]) if scope_values else bare_f[1:]
            records.extend((word, run_cwd, name) for word in _command_write_words(name, read_args, run_cwd))
            records.extend((word, run_cwd, name) for word in _more_write_words(name, read_args, run_cwd))
            if link_sources is not None and _is_hard_link(name, bare_f[1:]):  # A hard link's sources.
                link_sources.extend((word, run_cwd) for word in _link_sources(bare_f[1:]))
            for inner_words, inner_redirects in _commands_run_by(words, depth, fed, last if piped_in else None):
                records.extend((word, run_cwd, ">") for word in inner_redirects)
                inner_bare, inner_cwd = _strip_command_prefix(inner_words, run_cwd)  # The command it runs.
                if inner_bare:
                    inner_name = _command_name(inner_bare[0])  # str: that command's name.
                    inner_args = _scope_args(inner_name, inner_bare[1:]) if scope_values else inner_bare[1:]
                    records.extend((word, inner_cwd, inner_name) for word in
                                   _command_write_words(inner_name, inner_args, inner_cwd)
                                   + _more_write_words(inner_name, inner_args, inner_cwd))
        last = (words, fed)

    index = 0  # int: position in tokens.
    while index < len(tokens):
        kind, value = tokens[index]  # str, str: one token.
        if kind == "op" and value == _READING_RESTART:  # The installed reading starts from the start folders.
            finish("")  # The new reading's last command.
            cwds, carry, previous, last = (list(start) if start else [TOOL_CWD]), [], None, None  # As at start.
            stack.clear()  # No sub-shell of the new reading stays open.
            pushed.clear()  # Nor a folder it pushed.
            words, redirects, fed, piped_in = [], [], [], False  # No command is half read.
            index += 1
            continue
        if kind == "word":
            words.append(value)
            index += 1
            continue
        if value in _OUTPUT_REDIRECTS or value in _INPUT_REDIRECTS:
            operand = tokens[index + 1][1] if index + 1 < len(tokens) and tokens[index + 1][0] == "word" else None
            if operand is not None and value in _OUTPUT_REDIRECTS and not (
                    value == ">&" and re.match(r"^\d*-?$", operand)):
                redirects.append(operand)
            if index in body_of:
                fed.append(body_of[index])
            elif value == "<<<" and operand is not None:
                fed.append(operand)
            index += 2 if operand is not None else 1
            continue
        finish(value)  # Any other operator ends the simple command.
        if value in (";", "\n", "||", "&", ";;"):  # An `&&` chain ends: a `cd` of it may have failed, so the
            # folder before it counts from here on - the one place the set grows.
            cwds, carry = _folder_set_check(dedupe(cwds + carry)), []
        if value in ("(", "<(", ">("):  # A sub-shell or substitution: its moves end with it.
            stack.append((list(cwds), list(carry)))
            carry = []
        elif value == ")" and stack:
            cwds, carry = stack.pop()
        piped_in = value in ("|", "|&")
        words, redirects, fed = [], [], []
        index += 1
    finish("")
    return list(dict.fromkeys(records))  # The two readings' triples, each once, in order.


def _shell_hard_link_class(command: str) -> tuple[str | None, str]:
    """A hard link is a second name of the same file, so a later write through the new name - even one inside work/tmp/,
    where the folder rules do not apply - writes the harness file. The sources of `ln` without -s and of `cp -l` /
    `--link` are judged as `_path_harness_class` judges a write target (resolved and as written); a word holding a
    variable, a glob or a substitution is skipped, as `_shell_harness_class` skips it."""
    sources: list[tuple[str, str]] = []  # list[tuple[str, str]]: (source word, folder) pairs.
    _word_write_targets(command, link_sources=sources)
    result: str | None = None  # str | None: the stricter class so far.
    shown = ""  # str: the project-relative path that gave it.
    for word, cwd in sources:
        if not word or any(ch in word for ch in "$%*?`{["):
            continue
        found, rel = _path_harness_class(word, base=cwd)  # (str | None, str): resolved and lexical forms judged.
        if _stricter(result, found) != result:
            result, shown = found, rel
    return result, shown


def _multi_link_target(command: str) -> tuple[str, int]:
    """The first shell write target outside work/tmp/ that is a file with more than one hard link: (its project-relative
    path, its link count), or ("", 0).

    The guard judges a path by its names, resolved and as written, and a hard link has another name it cannot see -
    which may be a harness file. The targets are those of `_shell_write_targets` (both readers); a target that does not
    exist yet, a folder, or one under work/tmp/ is not judged here."""
    for word, cwd in _shell_write_targets(command):
        word = word.strip("\"'").rstrip(";&|,)")  # str: the bare word, as `_shell_harness_class` trims it.
        if not word or any(ch in word for ch in "$%*?`{["):
            continue
        abs_path = _to_abs(word, base=cwd)  # str | None: the target, links resolved.
        if abs_path is None or not _inside(abs_path):
            continue
        rel = _rel(abs_path)  # str: project-relative, "/" separators.
        if (rel.lower() + "/").startswith(HARNESS_SCRATCH_PREFIX):
            continue  # Scratch is outside this rule (the advisor's wording).
        try:
            info = os.stat(abs_path)  # os.stat_result: the file the name leads to.
        except OSError:
            continue  # Does not exist (yet): no other name can exist either.
        if os.path.isfile(abs_path) and info.st_nlink > 1:
            return rel, info.st_nlink
    return "", 0


# Set[str]: the commands (and ">" for a redirect) that write THROUGH an existing file - opening it in place, so every
# other name of the same file sees the change: the redirects, cp onto an existing file, tee, dd, truncate, shred, chmod
# / chown / touch (the file's mode, owner, times), PowerShell's Copy-Item / Set-Content / Add-Content / Out-File /
# Clear-Content, cmd's copy. Not: rm / unlink / rmdir / mv / move / Move-Item (a name is removed or replaced), sed -i /
# perl -i / install / rsync (a new file is written and renamed over the name), ln -f (the name is replaced). A limit:
# rsync with --inplace or --append DOES write through the existing file, and is not listed here, so such a write onto a
# multi-link name under work/tmp/ is not refused by this rule.
_WRITE_THROUGH = {">", "cp", "tee", "dd", "truncate", "shred", "chmod", "chown", "touch", "copy", "copy-item",
                  "set-content", "add-content", "out-file", "clear-content"}


def _multi_link_write_through(command: str) -> tuple[str, int]:
    """The first shell write target under work/tmp/ that a command writes THROUGH (_WRITE_THROUGH) and that is a file with
    more than one hard link: (its project-relative path, its link count), or ("", 0).

    The guard cannot tell which file the other name is (a walk of the harness folders would read every object of .git/),
    so any multi-link file there is refused for the forms that write through it; the cost is one `os.stat` per literal
    target. Removing or renaming such a name stays allowed (nothing is written through). Targets: both word readers,
    with the command's name (`_word_write_targets(records=...)`, `_real_folder_records`). In this tree no project tool
    leaves multi-link files under work/tmp/."""
    records: list[tuple[str, str, str]] = []  # list[(word, folder, name)]: every target with its command's name.
    _word_write_targets(command, records=records)
    records += _real_folder_records(command)
    for word, cwd, name in records:
        if name not in _WRITE_THROUGH:
            continue
        word = word.strip("\"'").rstrip(";&|,)")  # str: the bare word, as `_shell_harness_class` trims it.
        if not word or any(ch in word for ch in "$%*?`{["):
            continue
        abs_path = _to_abs(word, base=cwd)  # str | None: the target, links resolved.
        if abs_path is None or not _inside(abs_path):
            continue
        rel = _rel(abs_path)  # str: project-relative, "/" separators.
        if not (rel.lower() + "/").startswith(HARNESS_SCRATCH_PREFIX):
            continue  # Outside work/tmp/: `_multi_link_target` judges it (every write form).
        try:
            info = os.stat(abs_path)  # os.stat_result: the file the name leads to.
        except OSError:
            continue  # Does not exist (yet): no other name can exist either.
        if os.path.isfile(abs_path) and info.st_nlink > 1:
            return rel, info.st_nlink
    return "", 0


def _hard_link_tree_class(command: str) -> tuple[str | None, str]:
    """<new folder>` links `.claude/`, `.git/`, `CLAUDE.md` ...) and the sources of a hard link made after a `cd` the shell
    may really be in (`_real_folder_records`). Returns (class, project-relative path) or (None, "").

    A folder source is listed from disk (`_folder_entries`, at most _FOLDER_LIST_LIMIT names); each entry is judged as
    `<source>/<entry>` by `_path_harness_class`. Not seen: harness names deeper than the first level."""
    sources: list[tuple[str, str]] = []  # list[(word, folder)]: the hard links' source operands.
    _word_write_targets(command, link_sources=sources)
    _real_folder_records(command, link_sources=sources)
    result: str | None = None  # str | None: the stricter class so far.
    shown = ""  # str: the project-relative path that gave it.
    for word, cwd in sources:
        if not word or any(ch in word for ch in "$%*?`{["):
            continue
        candidates = [word] + [word.rstrip("/\\") + "/" + entry for entry in _folder_entries(word, cwd)]  # list[str].
        for candidate in candidates:
            found, rel = _path_harness_class(candidate, base=cwd)  # (str | None, str): this name's class.
            if _stricter(result, found) != result:
                result, shown = found, rel
    return result, shown


# The value operands the ADVISOR scope rule read as written files. dict[str, set[str]]: per command, the options whose
# value is the next word when written without "=" (GNU coreutils' `--help`: truncate -s / --size SIZE, -r / --reference
# RFILE; touch -d / --date STRING, -t STAMP, -r / --reference FILE; mkdir -m / --mode MODE; sed -e / -f; PowerShell's
# -ItemType, -Value, -Encoding, -Filter, -Include, -Exclude, -ErrorAction, -Stream, -Delimiter, case folded). Matched as
# written (case-sensitive) - `sed -E` is not `sed -e`; mkdir's `--context` takes its value only with "="
# (`--context[=CTX]`), so the word after it is the folder made and it is not listed here.
_SCOPE_VALUE_OPTIONS = {
    "truncate": {"-s", "--size", "-r", "--reference"},
    "touch": {"-d", "--date", "-t", "-r", "--reference"},
    "mkdir": {"-m", "--mode"},  # mkdir -m / --mode MODE.
    "sed": {"-e", "--expression", "-f", "--file", "-l", "--line-length"},
}
# set[str]: PowerShell's options (lower case) whose value is the next word, for its file cmdlets of _WRITE_ALL_OPERANDS
# and _COPY_INTO (`New-Item <path> -ItemType Directory`, `Set-Content -Path <p> -Value <text>`). Not `-Name` -
# New-Item's `-Name <file>` is the item made (in the current or the -Path folder), so its value stays an operand and is
# judged as a written name.
_POWERSHELL_VALUE_OPTIONS = {"-itemtype", "-value", "-encoding", "-filter", "-include", "-exclude",
                             "-erroraction", "-stream", "-delimiter"}
# re.Pattern: a chmod mode operand (octal, or symbolic `u+w`, `go-rwx`, `a=r,u+x`).
_CHMOD_MODE_RE = re.compile(r"^([0-7]{1,4}|[ugoa]*([-+=]([rwxXst]*|[ugo]))+(,[ugoa]*([-+=]([rwxXst]*|[ugo]))+)*)$")


def _scope_args(name: str, args: list[str]) -> list[str]:
    """`args` (list[str]) without the operands of command `name` that are values, not written files: chmod's mode (the
    first operand, when it reads as a mode and no --reference is given); chown's / chgrp's owner (the first operand,
    when no --reference is given and it holds no "/"); the values of _SCOPE_VALUE_OPTIONS and _POWERSHELL_VALUE_OPTIONS;
    sed's script (the first operand, when no -e / -f gives it). Used by the ADVISOR scope rule only: the harness rule
    keeps reading every operand (a mode or a date names no harness file). An option is matched case folded only for a
    PowerShell cmdlet (whose parameters are case insensitive); for every other command as written, so sed's `-E`
    (extended expressions, no value) is not read as `-e` (whose value is the script) and `sed -i -E s/a/b/ <file>` keeps
    its file as a written target."""
    low_name = name.lower()  # str: the command's name, case folded.
    powershell = "-" in low_name  # bool: a PowerShell cmdlet (Verb-Noun: copy-item, new-item, set-content).
    values = _SCOPE_VALUE_OPTIONS.get(low_name, set()) | (_POWERSHELL_VALUE_OPTIONS if powershell else set())
    out: list[str] = []  # list[str]: the arguments kept.
    skip = False  # bool: the next word is an option's value.
    done = False  # bool: after "--".
    for arg in args:
        if skip:
            skip = False
            continue
        if not done and arg == "--":
            done = True
            out.append(arg)
            continue
        # Case folded for a PowerShell cmdlet only (`arg in values` for every other command).
        if not done and arg.startswith("-") and len(arg) > 1 and (arg.lower() if powershell else arg) in values:
            skip = True  # This option's value is the next word: dropped with it.
            continue
        out.append(arg)
    operands = [index for index, arg in enumerate(out) if not arg.startswith("-") or arg == "-"]  # list[int].
    # bool: chmod / chown / chgrp --reference=<file>, also abbreviated.
    has_reference = any(_long_option_prefix(arg, ("--reference",), 4) for arg in args)
    # bool: sed's script is given by an option, so the first operand is a file, not the script. `--f` alone is ambiguous
    # in GNU sed (--follow-symlinks): read as a script option it only keeps the first operand as a written target.
    script_given = any(arg in ("-e", "--expression", "-f", "--file") or arg.startswith(("--expression=", "--file="))
                       or _long_option_prefix(arg, ("--expression", "--file"), 3)
                       or re.match(r"^-[A-Za-z]*[ef]", arg) is not None for arg in args if arg != "--")
    if operands and not has_reference and (
            (low_name == "chmod" and _CHMOD_MODE_RE.match(out[operands[0]]))
            or (low_name in ("chown", "chgrp") and "/" not in out[operands[0]])
            or (low_name == "sed" and not script_given)):
        del out[operands[0]]  # The mode, the owner, or sed's script: no file is written there.
    return out


def _advisor_write_outside_scope(command: str) -> str:
    """The first literal shell write target (str, project-relative) that lies inside the project but outside the ADVISOR's
    write scope (ADVISOR_DIR), or "".

    Judged on the resolved and the lexical path, so a link inside the scope that leads out of it, and a name written
    through such a link, are both outside. The null device of native Windows (`nul`) is no file; a target outside the
    project, one holding a variable, a glob or a substitution, is skipped. The targets are read by both word readers -
    `_word_write_targets` (every `cd` followed) and `_real_folder_records` (the folders the shell may really be in, so
    `(cd advisor/claude/tmp); rm <file>` and `cd <missing folder>; rm <file>` are judged from the folder the shell stays
    in) - without the value operands of `_scope_args` (`chmod 644`, `truncate -s 0`, `touch -d <date>`, `mkdir -m
    <mode>`, a sed script), and, on the PowerShell tool, with backslashes read as folder separators (PowerShell escapes
    with a backtick, never a backslash; the shell reading removed them, so `advisor\\claude\\tmp\\a.json` read as
    `advisorclaudetmpa.json`)."""
    text = command.replace("\\", "/") if TOOL_NAME.lower() == "powershell" else command  # str: the line read.
    targets = _word_write_targets(text, scope_values=True)  # list[(word, folder)]: every `cd` followed.
    targets += [(word, folder) for word, folder, _name in _real_folder_records(text, scope_values=True)]
    for word, cwd in targets:
        word = word.strip("\"'").rstrip(";&|,)")  # str: the bare word, as `_shell_harness_class` trims it.
        if not word or word.lower() == "nul" or any(ch in word for ch in "$%*?`{["):
            continue
        if re.match(r"^[A-Za-z]{2,}:", word):  # A PowerShell provider drive (`Env:NAME`, `Variable:x`), not a file;
            continue  # a Windows drive letter is one letter (`C:`) and is judged by the outside-path rules.
        for resolve in (True, False):
            abs_path = _to_abs(word, resolve=resolve, base=cwd)  # str | None: resolved or lexical absolute path.
            if abs_path is None or not _inside(abs_path):
                continue
            rel = _rel(abs_path)  # str: project-relative, "/" separators.
            if not (rel.lower() + "/").startswith(ADVISOR_DIR + "/"):
                return rel
    return ""


def pre_bash(data: dict) -> None:
    """PreToolUse for Bash / PowerShell: every check of `_pre_bash_checks`; a line nested past the parsers' limit is
    refused, so a fourth level of `eval` / `bash -c` / `$(...)` no longer passes unjudged.

    `_deny` and `_ask` end the process with SystemExit, which passes through here unchanged. The event's tool name is
    kept in TOOL_NAME for the ADVISOR scope rule, which reads a PowerShell command's backslashes as folder separators.
    The step budget of the three scans starts here (`_scan_budget_reset`, from the command's length), and a line whose
    scans pass it is refused (`_StepBudgetExceeded`), in every role and launch state, as a line nested too deep is.
    `function` / `coproc` bodies read inside one another count as nested forms too (`_NestedTooDeep`, the reason names
    them), and a line whose `cd`s leave more folders than `_FOLDER_SET_LIMIT` (`_TooManyFolders`) is refused with its
    own reason, in every role and launch state."""
    global TOOL_NAME  # The event's tool, read once per event (one event per process).
    TOOL_NAME = str(data.get("tool_name") or "")
    _scan_budget_reset((data.get("tool_input") or {}).get("command"))  # Counter 0, limit from the length.
    _folder_work_reset()  # The folder reader's work count starts at 0 for this event.
    try:
        _pre_bash_checks(data)
    except _NestedTooDeep:
        # The forms list names the `function` / `coproc` bodies as well; "more than three levels deep" is kept word for
        # word (the self-test's cases look for it); "past what the guard's parsers judge" is dropped to keep the reason
        # under 300 characters (265).
        _deny("The command nests command lines (`$( ... )`, backticks, `eval`, a shell's `-c` script, a `function` / "
              "`coproc` body, a `find -exec` command) more than three levels deep, so it is refused in every role "
              ". Write the inner commands out, or put them in a script file.")
    except _StepBudgetExceeded:  # The scans passed this event's step budget.
        _deny(_REASON_STEP_BUDGET)
    except _TooManyFolders:  # The `cd`s left more folders than the guard follows.
        _deny(_REASON_FOLDER_SET)


# str: the step budget's refusal (ASCII, under 300 characters): what happened and what to do instead; the same in every
# role and launch state.
_REASON_STEP_BUDGET = ("This line is too complex for the guard to read in bounded time: its parameter, arithmetic and "
                       "substitution scans passed their step budget, so it is refused in every "
                       "role. Split it, or put the script in a file and run the file.")
# str: the folder bound's refusal (ASCII, under 300 characters): what happened and what to do instead; the same in every
# role and launch state. The first sentence stays word for word (the self-test and MAIN's tools look for "leaving more
# possible folders than the guard follows").
_REASON_FOLDER_SET = ("This line's `cd` commands may fail, leaving more possible folders than the guard follows "
                      "so it is refused in every role. Join each `cd` and its commands with `&&` in a "
                      "sub-shell, `(cd dir && cmd && cmd)`, or use paths from the project root.")


def _pre_bash_checks(data: dict) -> None:
    """The checks of PreToolUse for Bash / PowerShell: each check denies, asks or falls through; the end allows
    (sys.exit(0))."""
    command = (data.get("tool_input") or {}).get("command")
    if not isinstance(command, str) or not command.strip():
        sys.exit(0)
    cmd = command.strip()
    # list[str]: the reasons of the git rules this line breaks.
    git_asks: list[str] = []

    # Rule 2: explicit env-file references are denied, including documentation/example variants.
    for tok in _cmd_tokens(cmd) + re.findall(r"[^\s'\"=,()]+", cmd):
        if ENV_FILE_RE.search(tok):
            _deny("The command references a .env file. Credentials are never read, printed, "
                  "copied or edited by an agent.")
    if SECRETS_RE.search(cmd):
        _deny("The command references a secrets/ directory.")

    # R10 credential printing
    if _CRED_RE.search(cmd):
        _deny("The command would print or inspect credentials (keys / secrets / tokens / passwords).")

    # R6: a one-off core.hooksPath / core.fsmonitor / alias.* on git's command line - each makes Git run a program.
    # Asked, with its own reason, before the general one-off rule below.
    oneoff = _git_oneoff_config(cmd)  # str: the option as written, or "".
    if oneoff:
        git_asks.append("`%s` sets core.hooksPath, core.fsmonitor or an alias for one git command; each makes Git run "
                        "a program (a hooks folder, a file-system monitor command, a shell alias). Approve only if you "
                        "asked for it (R6)." % oneoff[:200])
    # R6: any other one-off configuration value, and an assignment of GIT_CONFIG_COUNT / _KEY_<n> / _VALUE_<n> /
    # _PARAMETERS / _GLOBAL / _SYSTEM on a command line.
    oneoff_any = _git_oneoff_any(cmd)  # str: the option as written, or "".
    if oneoff_any and not oneoff:
        git_asks.append("`%s` gives git a one-off configuration value. Many names make Git run a program (pager, "
                        "editor, ssh command, credential helper, diff and filter drivers, included files). Approve "
                        "only if you asked for it (R6)." % oneoff_any[:200])
    config_env = _git_config_env_assignment(cmd)  # str: the assignment as written, or "".
    if config_env and _GIT_CONFIG_FILE_ENV_RE.match(config_env):
        git_asks.append("`%s` points Git at another configuration file (GIT_CONFIG_GLOBAL / GIT_CONFIG_SYSTEM), which "
                        "can set any name a one-off `git -c` could. Approve only if you asked for it (R6)."
                        % config_env[:200])
    elif config_env:
        git_asks.append("`%s` gives git a one-off configuration value through the environment (GIT_CONFIG_COUNT, "
                        "GIT_CONFIG_KEY_<n>, GIT_CONFIG_VALUE_<n>, GIT_CONFIG_PARAMETERS act like `git -c`). Approve "
                        "only if you asked for it (R6)." % config_env[:200])

    # R8 destructive & environment commands (no git rule among these patterns any more: they are _GIT_ASK_PATTERNS)
    for pattern, reason in _DENY_PATTERNS:
        if re.search(pattern, cmd, re.I):
            _deny(reason)
    # The file-removal rules judged on each simple command's words, after the patterns above: `rm -f -r <dir>`,
    # `Remove-Item -Recurse`, behind prefixes, groups, substitutions, eval, `bash -c`.
    destructive = _destructive_command(cmd, kind="files")  # str: the reason of the rule broken, or "".
    if destructive:
        _deny(destructive)

    # R6: the git text patterns and word rules - confirmations, collected here and raised at the end.
    for pattern, reason in _GIT_ASK_PATTERNS:
        if re.search(pattern, cmd, re.I):
            git_asks.append(reason)
    git_destructive = _destructive_command(cmd, kind="git")  # str: a git rule's reason (word rules), or "".
    if git_destructive:
        git_asks.append(git_destructive)
    forced_branch = _forced_branch_creation(cmd)  # str: the reason, or "".
    if forced_branch:
        git_asks.append(forced_branch)
    config_write = _git_config_write(cmd)  # str: the simple command, or "".
    if config_write:
        git_asks.append("`%s` changes Git's configuration (hooks path, fsmonitor, aliases and filters can make Git "
                        "run commands). Approve only a configuration change you asked for (R6); read forms such as "
                        "`git config --get <name>` need no approval." % config_write[:200])
    git_word = _git_word_rules(cmd)  # str: the reason of the rule a git command breaks, or "".
    if git_word:
        git_asks.append(git_word)

    # R5 advisor role. Process / GPU inspection commands (pgrep, ps, nvidia-smi ...) are exempt even when their
    # arguments name a project tool, as long as the line launches no interpreter.
    if ROLE == "ADVISOR":
        readonly_probe = _ADVISOR_READONLY_RE.match(cmd.strip()) is not None and not _PY_INVOKE_RE.search(cmd)
        if _ADVISOR_BASH_DENY.search(cmd) and not readonly_probe:
            _deny("ADVISOR sessions never run the app, tests, the eval/ harness or scripts/ tools. Allowed: cheap "
                  "read-only checks (CPU, <= ~60 s) on saved records (work/results/**) with output to "
                  "advisor/claude/tmp/.")
        # R6: an ADVISOR's mutating git asks.
        if _ADVISOR_GIT_RE.search(cmd) and not readonly_probe:
            git_asks.append("ADVISOR sessions never run mutating git without your approval: advisors normally use "
                            "only git status / diff / log / show / rev-parse / ls-files / blame. Approve only if you "
                            "asked for it (R6).")
        # `-m <module>` is resolved against the command's folder and the line's PYTHONPATH.
        launched = _advisor_main_launch(cmd)  # str: the script as written, or "".
        if launched:
            _deny("ADVISOR sessions never launch MAIN's session tools: `%s` lies under work/claude-main/, "
                  "work/codex-main/ or work/gemini-main/. Reading those folders stays allowed (Read / "
                  "Grep / Glob, cat, grep, sha256sum, a Python read of a record)." % launched[:200])
        harness_launch = _advisor_main_launch(cmd, kind="harness")  # str: the script or module as written, or "".
        if harness_launch:
            _deny("ADVISOR sessions never run the app, tests, the eval/ harness or scripts/ tools: `%s` is a script or "
                  "module under eval/, scripts/ or src/. Allowed: cheap read-only checks (CPU, <= ~60 s) "
                  "on saved records with output to advisor/claude/tmp/." % harness_launch[:200])
        for match in re.finditer(r">{1,2}\s*([^\s|&;]+)", cmd):
            target = match.group(1).strip("\"'")
            abs_path = _to_abs(target)
            if abs_path is not None and not _rel(abs_path).lower().startswith(ADVISOR_DIR + "/"):
                if target.lower() not in ("nul", "/dev/null", "&1", "&2"):
                    _deny("ADVISOR redirects must target %s/ (tmp/ or reports/)." % ADVISOR_DIR)

    # Rule 1: paths in the command
    _check_path_candidates(cmd)

    # R4 for shell writes: a literal write target that is a harness path at any depth is denied (the .claude/-like
    # class, .git/ included) or asked (CLAUDE.md, AGENTS.md, CLAUDE.local.md), as the file tools are; an ADVISOR is
    # denied on all; FINDSEE_ALLOW_HARNESS_EDIT=1 allows a MAIN. Reading or naming such a path is not a write and Git's
    # own commands write .git/ themselves, so `git status/diff/log/apply/add/commit` are unaffected.
    shell_ask = ""  # str: the target to confirm, raised after every deny check below.
    # Hard links. A write target outside work/tmp/ with more than one hard link is refused (another of its names may be
    # a harness file), and a hard link made to a harness file is judged by that file's class. Both before the harness
    # rule below, so their reason names the link; FINDSEE_ALLOW_HARNESS_EDIT=1 lifts them for a MAIN, as it lifts the
    # harness rule; an ADVISOR is refused.
    multi_rel, multi_count = _multi_link_target(cmd)  # (str, int): the multi-link target and its link count.
    if multi_rel and (ROLE == "ADVISOR" or not HARNESS_EDIT):
        _deny("The command writes %s, a file with %d hard links: another of its names may be a role/harness file the "
              "guard cannot see, so shell writes to a multi-link file outside work/tmp/ are refused. "
              "Write a fresh copy under another name instead." % (multi_rel, multi_count))
    # The same under work/tmp/, for the forms that write through a file (a redirect, cp, tee, dd, truncate, ...): a
    # second name there may be a harness file's. Lifted as the rule above is.
    through_rel, through_count = _multi_link_write_through(cmd)  # (str, int): the target and its link count.
    if through_rel and (ROLE == "ADVISOR" or not HARNESS_EDIT):
        _deny("The command writes through %s, a file under work/tmp/ with %d hard links: another of its names may be a "
              "role/harness file the guard cannot see. Remove the name and write a fresh "
              "file instead." % (through_rel, through_count))
    link_cls, link_rel = _shell_hard_link_class(cmd)  # (str | None, str): the class of a hard link's source.
    if link_cls is not None and (ROLE == "ADVISOR" or (not HARNESS_EDIT and link_cls == "deny")):
        _deny("The command makes a hard link to %s, a role/harness file owned by the user: a write through the new "
              "name would change it. Copy the file instead.%s"
              % (link_rel, _harness_rule_note(link_rel)))
    if link_cls == "ask" and not HARNESS_EDIT:
        shell_ask = link_rel  # Confirmed by the user below, after every deny check.
        link_ask = True  # bool: the confirmation is for a hard link (its own message below).
    else:
        link_ask = False  # bool: no hard-link confirmation pending.
    # A hard-link copy of a folder holding harness files (`cp -al. <dir>`), and a hard link made after a `cd`, judged as
    # the rule above judges a hard link's source.
    tree_cls, tree_rel = _hard_link_tree_class(cmd)  # (str | None, str): the strictest class linked, and its path.
    if tree_cls is not None and (ROLE == "ADVISOR" or (not HARNESS_EDIT and tree_cls == "deny")):
        _deny("The command makes a hard link to %s, a role/harness file owned by the user (a hard-link copy of a "
              "folder links every file in it): a write through the new name would change it. "
              "Copy the files instead.%s" % (tree_rel, _harness_rule_note(tree_rel)))
    if tree_cls == "ask" and not HARNESS_EDIT and not shell_ask:
        shell_ask, link_rel, link_ask = tree_rel, tree_rel, True  # Confirmed below with the hard-link message.
    shell_cls, shell_rel = _shell_harness_class(cmd)  # (str | None, str): class and target.
    if shell_cls is not None and ROLE == "ADVISOR":
        _deny("The command writes %s, a role/harness file owned by the user; an ADVISOR proposes harness changes "
              "through a ledger entry.%s" % (shell_rel, _harness_rule_note(shell_rel)))
    if shell_cls is not None and not HARNESS_EDIT:
        if shell_cls == "deny":
            _deny("The command writes %s, a role/harness file owned by the user. Propose the change in chat or as a "
                  "patch the user applies; the user re-launches with FINDSEE_ALLOW_HARNESS_EDIT=1 to permit an "
                  "explicitly requested edit.%s" % (shell_rel, _harness_rule_note(shell_rel)))
        shell_ask = shell_rel
    # An ADVISOR's every literal shell write target, not only a `>` redirect (its rule above) - the operands of rm, mv,
    # cp, tee, touch, mkdir and the like, in-place edits, a folder destination, `>&file`, a `cd` earlier in the line
    # followed - must lie in its scope. After the harness and hard-link rules, so those keep their reasons; a target
    # outside the project is left to the outside-path rules above.
    if ROLE == "ADVISOR":
        outside_scope = _advisor_write_outside_scope(cmd)  # str: the first target outside advisor/claude/, or "".
        if outside_scope:
            _deny("ADVISOR shell writes must target %s/ (tmp/ or reports/): the command writes %s. "
                  "Point code, record or config changes to a MAIN agent through a ledger entry."
                  % (ADVISOR_DIR, outside_scope[:200]))

    # Critical instruction 3: Python work only inside the project environment. If the launching shell did not
    # activate it, interpreter launches are denied unless the command itself pins it (conda run -n / conda activate /
    # the env's interpreter path / the project's .venv interpreter / uv run).
    if _PY_INVOKE_RE.search(cmd) and not VENV_ACTIVE and not _VENV_PINNED_RE.search(cmd):
        _deny("No project environment (%s) is active in the shell this session was launched from "
              "(CONDA_DEFAULT_ENV=%r, VIRTUAL_ENV %s). Use `conda run -n %s python ...`, `.venv/bin/python ...` "
              "(Windows: `.venv\\Scripts\\python ...`) or `uv run ...`, or ask the user to activate the "
              "environment and relaunch. Running with another interpreter is not permitted."
              % (_ENV_TEXT, _ACTIVE_ENV, "inside the project" if _VENV_IN_ROOT else "not inside the project",
                 CONDA_ENV))

    # Every deny check has passed: the confirmations, gathered into one question (one hook answer per event).
    asks: list[str] = []
    # A shell write to an entry file (CLAUDE.md, AGENTS.md, GEMINI.md, CLAUDE.local.md) or, R6, to a git-related path
    # (.git/, .gitmodules) asks.
    if shell_ask and link_ask and shell_ask == link_rel:
        asks.append("The command makes a hard link to %s, a role/harness or git-related file: a write through the new "
                    "name would change it. Approve only an edit you asked for in this session.%s"
                    % (shell_ask, _harness_rule_note(shell_ask)))
    elif shell_ask:
        kind = ("a git-related role/harness file owned by the user" if _is_git_path(shell_ask)
                else "a role/harness file owned by the user")  # str.
        asks.append("The command writes %s, %s. Approve only an edit you asked for in this session; refuse to leave "
                    "the file unchanged.%s" % (shell_ask, kind, _harness_rule_note(shell_ask)))
    asks += git_asks  # R6: the git rules' reasons.
    for pattern, reason in _ASK_PATTERNS:  # Process kills, downloads, commits.
        if re.search(pattern, cmd, re.I):
            asks.append(reason)
    if asks:
        unique = list(dict.fromkeys(asks))  # list[str]: the reasons in order, each once.
        _ask(" | ".join(unique))
    sys.exit(0)


# --------------------------------------------------------------------------------------------
# PostToolUse: Write | Edit | MultiEdit | NotebookEdit
# --------------------------------------------------------------------------------------------
def post_write(data: dict) -> None:
    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or tool_input.get("path")
    if not isinstance(file_path, str) or not file_path.strip():
        sys.exit(0)
    abs_path = _to_abs(file_path)
    if abs_path is None or not _inside(abs_path):
        sys.exit(0)
    rel = _rel(abs_path)
    low = rel.lower()
    # first_write: True when this session has not yet recorded a write to `rel`. Static reminders
    # are emitted once per file per session so a long multi-edit turn does not repeat the same
    # paragraph after every edit; the measured under-comment note below keeps firing every time.
    first_write = rel not in _state_read(data)
    _state_add(data, rel)

    notes: list[str] = []
    if _is_code(rel) or _CODE_EXT_RE.search(low):
        # Critical instruction 4: every edited/added block, line and variable is commented.
        if first_write:
            notes.append("Critical instruction 4 applies to %s: detailed comments/descriptions for "
                         "every added or changed block, line and variable (what, why, "
                         "shape/dtype/units/range where relevant); docstrings for new functions/classes; "
                         "update comments the change made stale." % rel)
        if low.endswith(".py"):
            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
                    _text = fh.read()
                _code_lines = [ln for ln in _text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
                _comment_lines = [ln for ln in _text.splitlines() if ln.strip().startswith("#") or "  # " in ln]
                _doc_count = _text.count('"""') // 2 + _text.count("'''") // 2
                if _code_lines and (len(_comment_lines) + _doc_count) < max(3, len(_code_lines) // 8):
                    notes.append("%s looks under-commented (%d comment lines / %d docstrings for %d code "
                                 "lines): add the missing block/line/variable comments now."
                                 % (rel, len(_comment_lines), _doc_count, len(_code_lines)))
            except Exception:  # pylint:disable=broad-except
                pass
    if _is_code(rel):
        if first_write:  # once per file per session; the Stop hook still enforces both items
            notes.append("Code path modified (%s): a change_log/ entry from change_log/TEMPLATE.md is "
                         "required before this session ends, the item must be claimed on "
                         "work/WORKBOARD.md, and a claimed result needs evaluation evidence "
                         "(docs/project/EVALUATION_PROTOCOL.md)." % rel)
        if low.endswith(".py") and low.startswith("src/"):
            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read()  # str: the package module just written.
                # The package logs through `logging` so the demo can raise or silence it; scripts and eval tools may
                # print. Chinese text in prompts and spoken replies is expected, so there is no ASCII check here.
                if re.search(r"^\s*print\(", text, re.M):
                    notes.append("print() found in %s - package code uses logging (logger = logging.getLogger(__name__))."
                                 % rel)
            except Exception:  # pylint:disable=broad-except
                pass
    if low.startswith("advisor/") and low.endswith("advice.md") and ROLE != "ADVISOR":
        notes.append("advisor ledger edited by a MAIN agent: only status tags and `> main:` reply lines "
                     "may change; never delete advisor entries.")
    if low in ("progress.md",) or low.startswith("work/backlog") or low.startswith("docs/project/"):
        notes.append("Shared doc edited: append/own-bullets only, never rewrite another agent's lines; "
                     "tag bullets (claude)/(codex)/(gemini) while more than one agent is active.")
    if notes:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                                  "additionalContext": " | ".join(notes)}}))
    sys.exit(0)


# --------------------------------------------------------------------------------------------
# Stop
# --------------------------------------------------------------------------------------------
def stop(data: dict) -> None:
    if data.get("stop_hook_active"):
        sys.exit(0)
    if ROLE == "ADVISOR":
        sys.exit(0)
    written = _state_read(data)
    if not written:
        sys.exit(0)
    code = sorted({p for p in written if _is_code(p)})
    if not code:
        sys.exit(0)
    has_changelog = any(p.lower().startswith("change_log/") and not p.lower().endswith("template.md") for p in written)
    has_workboard = any(p.lower() == "work/workboard.md" for p in written)
    missing = []
    if not has_changelog:
        missing.append("a change_log/ entry (copy change_log/TEMPLATE.md; status WIP is fine mid-task)")
    if not has_workboard:
        missing.append("a claim/release row on work/WORKBOARD.md")
    if missing:
        print(json.dumps({"decision": "block",
                          "reason": "This session modified code (%s) but is missing: %s. Add them "
                                    "now (one short entry each), then finish." % (", ".join(code[:6]), "; ".join(missing))}))
    sys.exit(0)


# --------------------------------------------------------------------------------------------
# SessionStart
# --------------------------------------------------------------------------------------------
def session_start(data: dict) -> None:
    """SessionStart: the project's rules, the session's role and environment status, and the reading order."""
    role = ("ADVISOR (write scope advisor/claude/ only)" if ROLE == "ADVISOR"
            else "MAIN (peer of Codex MAIN and Gemini MAIN; coordinate on work/WORKBOARD.md)")  # str.
    lines = [
        "=== FindSee final project guard (hooks active) ===",
        "CRITICAL AI SYSTEM INSTRUCTIONS (partial hook checks; user authority applies):",
        "  1. You cannot work outside the current working folder: " + PROJECT + " (one exception: this "
        "project's own folder in the user-level Claude folder, " + CLAUDE_HOME_OWN_PATH +
        "; the rest of that folder is read-only, never the credential store).",
        "  2. You must NEVER access, read, or modify any .env files.",
        # Status names the active environment, so the session knows whether Python launches are allowed.
        "  3. You must develop inside the project environment: " + _ENV_TEXT + " "
        "(status now: " + ("ACTIVE (%s)" % (_ACTIVE_ENV if _ACTIVE_ENV.lower() in CONDA_ENVS else ".venv")
                           if VENV_ACTIVE else
                           "NOT ACTIVE - the hook will deny Python launches; use `conda run -n %s ...`, "
                           "`.venv/bin/python ...` or `uv run ...`, or relaunch" % CONDA_ENV) + ").",
        "  4. You must add detailed comments or descriptions for each code block, line and variable you "
        "edit or write (reminded after every code write).",
        "Role: " + role,
        "Also enforced: no secrets/; harness files at any depth (AGENT_ADVISOR.md, .mcp.json, .claude/, .agents/, "
        ".codex/, .gemini/) read-only; CLAUDE.md, AGENTS.md, GEMINI.md and CLAUDE.local.md edits ask the user; "
        "model/media artefacts never hand-written; data/ writes ask (privacy); no pip/conda/uv package changes; "
        "process kills and downloads ask; credentials never printed.",
        "Git (R6): every git rule ASKS instead of denying - push, pull/merge/rebase, reset --hard, clean/stash, "
        "checkout/switch, ref deletion, -C/--git-dir, git config writes, git -c, GIT_CONFIG_*, .git/ and "
        ".gitmodules writes, commits. A line that also breaks a non-git rule is still denied.",
        "Start-of-session reading order: CLAUDE.md / AGENTS.md / GEMINI.md -> tail of PROGRESS.md -> "
        "work/WORKBOARD.md -> work/BACKLOG.md -> newest change_log/ -> advisor/*/advice.md (MAIN) | "
        "AGENT_ADVISOR.md (ADVISOR).",
        "Autonomy: plan -> implement -> evaluate -> document without asking; the user is needed for installs, "
        "downloads, new personal data, git publication, scope changes and anything irreversible.",
    ]
    if data.get("source") in ("compact", "resume"):
        lines.append("(context was compacted/resumed: re-read work/WORKBOARD.md before touching shared files)")
    print("\n".join(lines))
    sys.exit(0)


# --------------------------------------------------------------------------------------------
def main() -> None:
    """Validate event/cwd then dispatch; pre-tool internal errors block with exit code 2."""
    global TOOL_CWD  # Validated event base for all relative path checks in this process.
    handlers = {"pre-bash": pre_bash, "pre-read": pre_read, "pre-write": pre_write,
                "post-write": post_write, "stop": stop, "session-start": session_start}
    try:
        data = _read_input()  # Include malformed-input failures in the blocking handler.
        handler = handlers.get(EVENT)  # Unknown wiring is an error, not implicit permission.
        if handler is None:
            raise ValueError("Unknown hook event")
        TOOL_CWD = os.path.realpath(data.get("cwd") or PROJECT)  # Resolve once per event.
        if not _inside(TOOL_CWD):
            raise ValueError("Tool cwd is outside the project root")
        handler(data)
    except SystemExit:
        raise
    except Exception as err:  # pylint:disable=broad-except
        # Do not echo the payload or arbitrary exception text: they can contain sensitive inputs.
        sys.stderr.write("guard.py could not validate event %s (%s); action blocked where supported.\n"
                         % (EVENT, type(err).__name__))
        sys.exit(2)


if __name__ == "__main__":
    main()
