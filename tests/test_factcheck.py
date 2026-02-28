from __future__ import annotations

from pathlib import Path

from portable_guard.config import load_policy
from portable_guard.factcheck import run_checks


def _base_claims() -> dict:
    return {
        "schema_version": "1.0",
        "run_id": "abc123",
        "ts": "2026-02-28T20:00:00+00:00",
        "cwd": "/tmp/original",
        "mode": "declared",
        "files_modified": [],
        "files_created": [],
        "artifacts_expected": [],
        "gates": {
            "selftest_ran": False,
            "goldens_ran": False,
            "sentinel_stop_smoke_ran": False,
            "shadow_leak_check_ran": False,
        },
        "commands_executed": [],
        "models_used": [],
    }


def test_quick_mode_ignores_cwd_mismatch_by_default(tmp_path: Path):
    policy = load_policy(workspace=tmp_path)
    claims = _base_claims()

    result = run_checks(claims, mode="quick", policy=policy, runtime_cwd=tmp_path / "other")
    assert result["verdict"] == "PASS"
    assert all(m["check"] != "argv_parity" for m in result["mismatches"])


def test_strict_mode_fails_on_false_gates_and_cwd_mismatch(tmp_path: Path):
    policy = load_policy(workspace=tmp_path)
    claims = _base_claims()

    result = run_checks(claims, mode="strict", policy=policy, runtime_cwd=tmp_path)
    assert result["verdict"] == "FAIL"
    checks = {m["check"] for m in result["mismatches"]}
    assert "B" in checks
    assert "argv_parity" in checks


def test_declared_mode_no_gate_warn_when_no_source_files(tmp_path: Path):
    policy = load_policy(workspace=tmp_path)
    claims = _base_claims()

    result = run_checks(claims, mode="declared", policy=policy, runtime_cwd="/tmp/original")
    assert result["verdict"] == "PASS"
    assert "No source files declared" in " ".join(result["notes"])


def test_forbidden_prefix_is_blocking(tmp_path: Path):
    policy = load_policy(workspace=tmp_path)
    claims = _base_claims()
    claims["files_created"] = [str(Path.home() / ".claude/plugins/cache/omc/touched.txt")]

    result = run_checks(claims, mode="declared", policy=policy, runtime_cwd="/tmp/original")
    assert result["verdict"] == "FAIL"
    assert any(m["check"] == "H" for m in result["mismatches"])
