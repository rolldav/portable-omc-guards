# portable-omc-guards

Portable extraction of `factcheck` + `sentinel` guard logic from a local Claude setup.

## Why this exists
This mini-repo removes local coupling found in ad-hoc setups:
- no hardcoded `/Users/<name>/...` paths
- no project names hardcoded in source
- configurable policy via JSON + env vars
- deterministic checks with tests

## What is included
- `portable_guard/config.py`: portable config loader (defaults + overrides)
- `portable_guard/factcheck.py`: deterministic claims verification engine
- `portable_guard/sentinel_health.py`: operational readiness scoring for Sentinel logs
- `config/sentinel_portable.schema.json`: JSON schema for policy config
- `examples/config.example.json`: sample policy file
- `tests/`: focused unit tests

## Quick start
```bash
cd /Users/drg/GitHub/portable-omc-guards
python3 -m pytest -q
```

## Design principles
- Portable first: use `${HOME}` and workspace-relative paths, not machine-specific constants.
- Low-noise factcheck: `quick` mode does not raise cwd-parity warnings by default.
- Explicit readiness gate for Sentinel: do not propose/enable upstream if signal quality is degraded.
