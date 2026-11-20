---
description: (ADVISOR session) full advice pass - detect changes, read context, GC marks, critique evaluation-first, write ledger entries, rewrite analysis.md, log, update memory. Writes only advisor/claude/.
---
This command is for a Claude session launched as ADVISOR (`FINDSEE_AGENT_ROLE=ADVISOR`, folder `advisor/claude/`). If
this session was not launched that way, say so in one line and stop: the command does not change an active MAIN
session's role (`AGENTS.md` §Role selection). Read `AGENT_ADVISOR.md` and `AGENTS.md` §ADVISOR contract, then follow
`.agents/skills/advisor-pass/SKILL.md` with `<agent>` = `claude`. Where the skill differs from `AGENT_ADVISOR.md` or
`docs/project/EVALUATION_PROTOCOL.md`, the protocol documents win.

Optional focus: $ARGUMENTS (narrows the critique only; GC, the analysis rewrite and the log still happen). Never touch
`work/WORKBOARD.md`, `PROGRESS.md`, `work/BACKLOG.md` or code. Finish with the <= 10-line chat report.
