---
name: advisor-research
description: One research pass for an ADVISOR session commissioned by the user in the FindSee repository - Claude Mythos RESEARCH ADVISOR (diagnosis, mechanism, design, adversarial review, or a vulnerability review of a named scope; writes advisor/claude/) or Codex Astra RESEARCH ADVISOR (statistical design, derivation, knowledge synthesis, theoretical critique; writes advisor/codex/). Use only in a session the user assigned ADVISOR and commissioned for research.
---

# advisor-research — one commissioned research pass

`<agent>` = `claude` (Claude Mythos RESEARCH ADVISOR, charter `docs/project/RESEARCH_ADVISOR.md`) or `codex` (Codex
Astra RESEARCH ADVISOR, charter `docs/project/RESEARCH_ADVISOR_CODEX.md`). Writes only inside `advisor/<agent>/`.

1. **Check the role.** The session must be an ADVISOR (Claude: launched with `FINDSEE_AGENT_ROLE=ADVISOR`; Codex:
   assigned in the user's first message). If not, say so in one line and stop. Announce the charter's name with your
   model ID.
2. **Check the commission.** Claude: one question and its form (diagnosis, mechanism, design, adversarial review), or
   `vulnerability <scope>` (the question is fixed; ask for the scope if it is missing). Codex: one or several jobs, each
   with its form (statistical design, derivation, knowledge synthesis, theoretical critique). Ask - do not guess.
3. **Read** `AGENT_ADVISOR.md`, `AGENTS.md` §ADVISOR contract and your charter in full, then
   `advisor/<agent>/memory/advisor-state.md` and the active entries of the three ledgers, then the scope.
4. **Work** to the charter's section 4 (what the form's report holds) and section 5 (the standards). CPU analysis of
   saved records and simulations only, in the project environment, output under `advisor/<agent>/tmp/`, and not while
   an evaluation is in flight (`work/WORKBOARD.md` rows without a release stamp). Never open the test split beyond what
   `EVALUATION_PROTOCOL.md` allows.
5. **Vulnerability review (Claude only):** state the scope and what was not read; name the trust boundaries and inputs;
   look for the charter's section 6 classes; one ledger entry per finding (`Priority: HIGH` when critical) with class,
   line, trigger, impact, confidence, proposed fix and the test that must fail first; reproducers as files under
   `tmp/` for MAIN to run; build, run and fuzz nothing; a third-party defect goes to the user with a mitigation.
6. **Write** the report(s) to `advisor/<agent>/reports/YYYY-MM-DD_<topic>.md` (UTC date; one per job), one ledger
   entry per decision in `advisor/<agent>/advice.md` (the next A-NNN; `Decision: USER` where the charter's section 8
   says so), a dated Advice Log line naming the role, and `memory/advisor-state.md` updated with what the next numbered
   pass still owes. Prune and archive nothing. Never touch the workboard, `PROGRESS.md`, the backlog, `docs/`, code or
   data.

Finish with a ≤ 10-line chat report: report paths, A-IDs, the headline, the cheapest experiment that could refute it
(for a vulnerability review: the critical findings and the first reproducer MAIN should run), and the next question you
would propose.
