---
description: (ADVISOR session) pulse - ledger counts, changes since the last pass, running work, recommendation. Writes nothing.
---
This command is for a Claude session launched as ADVISOR (folder `advisor/claude/`). Read `AGENT_ADVISOR.md` §Reading
order and authority and `AGENTS.md` §ADVISOR contract, then follow `.agents/skills/advisor-status/SKILL.md` with
`<agent>` = `claude`. Print the 4-line report in chat. Write nothing. If the session was not launched with
`FINDSEE_AGENT_ROLE=ADVISOR`, say so in one line (the hooks then still allow MAIN writes - do not make any).
