from __future__ import annotations

import json
from pathlib import Path

from portable_guard.config import load_policy
from portable_guard.sentinel_health import analyze_log, is_upstream_ready


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_readiness_blocks_degraded_signal(tmp_path: Path):
    log = tmp_path / "sentinel_stop.jsonl"
    rows = [
        {"verdict": "FAIL", "runtime": {"timed_out": True}, "reason": "timeout"},
        {"verdict": "WARN", "runtime": {"global_timeout": True}, "reason": ""},
        {"verdict": "WARN", "reason": "no_parseable_verdicts"},
        {"verdict": "FAIL", "reason": "required_models_unavailable"},
        {"verdict": "PASS", "reason": "ok"},
    ]
    _write_jsonl(log, rows)

    policy = load_policy(workspace=tmp_path)
    stats = analyze_log(log)
    ready, blockers = is_upstream_ready(stats, policy)

    assert not ready
    assert blockers


def test_readiness_passes_healthy_signal(tmp_path: Path):
    log = tmp_path / "sentinel_stop.jsonl"
    rows = []
    for i in range(8):
        rows.append({"verdict": "PASS", "reason": f"ok-{i}", "runtime": {"timed_out": False}})
    rows.append({"verdict": "WARN", "reason": "low-confidence", "runtime": {"timed_out": False}})
    rows.append({"verdict": "FAIL", "reason": "policy-block", "runtime": {"timed_out": False}})
    _write_jsonl(log, rows)

    policy = load_policy(workspace=tmp_path)
    stats = analyze_log(log)
    ready, blockers = is_upstream_ready(stats, policy)

    assert ready
    assert blockers == []
