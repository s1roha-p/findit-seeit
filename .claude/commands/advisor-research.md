---
description: (ADVISOR session) one research pass on a commissioned question (diagnosis | mechanism | design | adversarial review) or one critical-vulnerability review of a named scope -> advisor/claude/reports/ + ledger entries. Writes only advisor/claude/.
---
This command is for a Claude session launched as ADVISOR (`FINDSEE_AGENT_ROLE=ADVISOR`, folder `advisor/claude/`) and
commissioned by the user for research, as the Claude Mythos RESEARCH ADVISOR (`docs/project/RESEARCH_ADVISOR.md`). If
this session was not launched that way, say so in one line and stop: the command does not change an active MAIN
session's role (`AGENTS.md` §Role selection). Commission: $ARGUMENTS
If empty, ask for the question and its form (diagnosis, mechanism, design, adversarial review, vulnerability) - do
not guess; for `vulnerability` the commission is the scope (component, commit or patch, files).

Follow `.agents/skills/advisor-research/SKILL.md` with `<agent>` = `claude`. No app runs, tests, evaluations, model
execution or GPU; CPU analysis of saved records and simulations only, output under `advisor/claude/tmp/`. Finish with
the skill's <= 10-line chat report.
