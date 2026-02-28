# Upstream Proposal — Portable Factcheck MVP + Sentinel Readiness Gate

## Context
I am **not a software engineer**. I am a **physician** using LLM tooling daily in a high-responsibility workflow.
This proposal comes from repeated operational usage, with a focus on reliability and low-noise guardrails.

## Problem
Current local guard setups often become:
- environment-coupled (hardcoded user paths)
- project-coupled (hardcoded project lists in code)
- noisy (warnings that do not improve decisions)

That makes upstream adoption difficult and reduces trust in guard outputs.

## What this mini-repo provides
This repository extracts two minimal, portable building blocks:

1. **Factcheck MVP (portable)**
- Deterministic checks over claims payloads
- Config-driven forbidden path/command checks
- No hardcoded `/Users/<name>/...`
- No hardcoded project names
- Low-noise quick mode (cwd-parity warning disabled by default in quick mode)

2. **Sentinel readiness gate**
- Evaluates log quality before recommending upstream enablement
- Explicit thresholds for pass-rate, timeout-rate, warn/fail-rate, and reason coverage
- Prevents upstreaming a degraded, high-noise signal

## Delivered artifacts
- `portable_guard/factcheck.py`
- `portable_guard/sentinel_health.py`
- `portable_guard/config.py`
- `config/sentinel_portable.schema.json`
- `examples/config.example.json`
- Unit tests under `tests/`

## Validation status
- Python syntax checks: PASS
- Unit tests: PASS (`6 passed`)

## Suggested adoption path (incremental)
1. Integrate **Factcheck MVP** first, behind feature flag.
2. Keep **Sentinel readiness** as gating telemetry, not blocking policy, until signal quality is stable.
3. Move strictness from code constants to config schema.
4. Publish reference defaults for safe low-noise operation.

## Why this should help maintainers
- Lower integration risk
- Better portability across contributors
- Better signal-to-noise ratio for operational decisions
- Clear, testable policy surface

## Notes
If useful, I can provide real-world anonymized before/after metrics as a user report.
