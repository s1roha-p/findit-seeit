# data/

Follow `docs/project/DATA_POLICY.md` before adding anything. `raw/` (photos, recordings) and `runtime/` (snapshots and
the memory store the app writes) are git-ignored; share raw data through the team's private drive. `manifests/` is
tracked: one CSV row per file with session, split, sha256, consent note, size band and ground-truth text
(`docs/project/EVALUATION_PROTOCOL.md` section 2). The Claude guard asks before any file-tool write under `data/`.
