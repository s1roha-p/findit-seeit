---
name: advisor-sync
description: Acknowledgment sync for the ADVISOR role in the FindSee repository. Use when a MAIN agent (Claude, Codex or Gemini) has marked ledger entries [ACK]/[DONE]/[REJECTED] or left "> main:" replies - verify DONE claims, prune, log - WITHOUT a fresh review. Also for /advisor-sync. Writes only advisor/<agent>/advice.md.
---

# advisor-sync — process marks, prune, log

Writes ONLY `advisor/<agent>/advice.md` (and `advice_archive_<date>.md` when archiving). No new critique, no new
entries except a re-open of a false `[DONE]`.

1. Read `advice.md` fully; record every entry's ID, tag and `> main:` lines (MAIN's property: they survive verbatim
   until the entry is pruned).
2. For each entry:
   - `[DONE]` → **verify** against what it cites (record, test, change log, source line); read the numbers and the
     tier. Verified → move to Recently Resolved with "verified: <where>" (delete if it was already there). Not done →
     keep it and add a new entry referencing it with the discrepancy.
   - `[REJECTED: reason]` → sound → delete and log it; factually wrong → re-raise once under a new ID with stronger
     evidence (never twice).
   - `[ACK]` → keep; a HIGH entry `[ACK]` for 3+ passes gets one escalation line.
   - `[OPEN]` → keep unless a change made it moot (delete and log why).
3. Rewrite: header unchanged; Active Advice sorted HIGH → MED → LOW then ID; Recently Resolved; Advice Log line
   `- YYYY-MM-DD HH:MM — sync: verified A-…; pruned A-…; re-opened A-… as A-…; escalated A-….`
4. Keep the active part to about 150 lines; archive history verbatim with its sha256 noted.

Report in ≤ 8 lines: verified / pruned / re-opened / escalated IDs, and whether a full pass is warranted.
