# src/findsee — the package (to be written)

Planned layout and the functions each part provides: `docs/project/ARCHITECTURE.md`. Part ownership:
`mode1/` → A, `voice/` → B, `mode2/` → C, `app/` → D; `types.py` and `config.py` are shared (change them by agreement).

Week 1: each part adds its module with the signatures from `ARCHITECTURE.md` and a stub that returns a fixed example,
so the app (D) can be wired before the real implementations land.
