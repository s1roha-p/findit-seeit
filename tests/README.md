# tests/

pytest, one folder per part (`tests/mode1/`, `tests/voice/`, `tests/mode2/`, `tests/app/`). Fixtures in
`tests/fixtures/` are small and either synthetic or fully redacted and consented (`docs/project/DATA_POLICY.md`).
Run with the project environment: `python -m pytest tests`. A run that collects no tests counts as a failure, not a
pass.
