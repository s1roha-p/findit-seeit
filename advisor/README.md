# advisor/ — advisor agents' folders

Three advisor folders, one per agent family, identical layout. Any of Claude, Codex or Gemini can be MAIN or, in a
separate session the user assigns, ADVISOR (`AGENTS.md`). An advisor writes ONLY inside its own folder; MAIN agents
touch only status tags and `> main:` reply lines inside `advice.md`. Protocol: `AGENT_ADVISOR.md`.

| Folder | Who (when assigned ADVISOR) | Entry file | Invoked by |
|---|---|---|---|
| `claude/` | a Claude Code session launched with `FINDSEE_AGENT_ROLE=ADVISOR` | `AGENT_ADVISOR.md` | `/advisor-*` commands in `.claude/commands/` |
| `codex/` | a Codex session declared `Codex role: ADVISOR` | `AGENTS.md` role table | skills `.agents/skills/advisor-*` by name |
| `gemini/` | a Gemini CLI / Antigravity session declared ADVISOR | `GEMINI.md` (ADVISOR paragraph) | workflows `.agents/workflows/advisor-*` |

Research forms: a Claude advisor on Mythos commissioned for research is the **Claude Mythos RESEARCH
ADVISOR** (`docs/project/RESEARCH_ADVISOR.md`; it uses `claude/`, its vulnerability reproducers go to `claude/tmp/` for
MAIN to run); a Codex advisor on Astra commissioned for theory is the **Codex Astra RESEARCH ADVISOR**
(`docs/project/RESEARCH_ADVISOR_CODEX.md`; it uses `codex/`). Their reports and entries share the folder's ledger with
the numbered passes and name their role in the Advice Log.

Per folder:

```
advice.md               ledger: A-NNN entries with [OPEN]/[ACK]/[DONE]/[REJECTED] tags, Advice Log
analysis.md             standing analysis notebook, rewritten every full pass
reports/                dated deep dives  YYYY-MM-DD_<topic>.md
memory/advisor-state.md the advisor's own memory (last pass, next ID, hypotheses)
tmp/                    scratch for cheap read-only checks (git-ignored)
```

MAIN agents read all three `advice.md` at session start and checkpoints, act or reject with a reason, and reply with
`> main:` lines pointing at records. Never delete an entry; the advisor prunes on its next pass. Advisors read each
other's ledgers to avoid duplicate advice but never edit them.
