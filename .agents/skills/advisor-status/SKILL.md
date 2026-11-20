---
name: advisor-status
description: Cheap "anything new?" pulse for the ADVISOR role in the FindSee repository. Use when the user asks whether a review pass is warranted, what changed since the last pass, how many advice entries are open, or types /advisor-status. Reads the ledger, the workboard and changes only; writes NOTHING; ends with a recommendation.
---

# advisor-status — pulse

Writes nothing. Reads `advisor/<agent>/advice.md`, the memory file, `work/WORKBOARD.md` and git state.

1. **Ledger counts:** entries by tag (`[OPEN]`, `[ACK]`, `[DONE]`, `[REJECTED: …]`), the highest A-NNN, the newest
   `Advice Log` line (last-pass marker). Only the initialization line → recommend a full pass.
2. **Main-agent marks** since the marker (`[DONE]`, `[REJECTED]`, `> main:` lines) → a sync is needed.
3. **Changes since the marker** (`git log --stat HEAD ^<marker HEAD>`, `git status --porcelain`), classified:
   `work/results/`, `PROGRESS.md`, `work/BACKLOG.md` → new evidence; `src/**`, `change_log/**` → code change; `eval/**`,
   `data/manifests/**` → harness or split change (a split change invalidates comparisons); `docs/project/**` → plan
   change; harness files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `AGENT_ADVISOR.md`, `.claude/**`, `.agents/**`) → re-read
   before the next pass; `advisor/<other>/**` → read their open items to avoid duplicates.
4. **Running work:** open workboard rows (evaluations in flight make results torn).
5. **Recommend** one of: `full pass` · `sync` · `nothing` · `deep dive: <topic>`.

```
Ledger: OPEN n · ACK n · DONE n · REJECTED n · next ID A-NNN · last pass <ts>
Since then: <k> files — <one line per category>
Running: <none | claim: part, agent, what, ETA>
Recommendation: <full pass | sync | nothing | deep dive: topic> — <reason>
```
