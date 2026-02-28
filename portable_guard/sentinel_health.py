from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .config import PortablePolicy


@dataclass(frozen=True)
class SentinelStats:
    total_runs: int
    pass_count: int
    warn_count: int
    fail_count: int
    timeout_count: int
    reason_coverage_count: int

    @property
    def pass_rate(self) -> float:
        return self.pass_count / self.total_runs if self.total_runs else 0.0

    @property
    def timeout_rate(self) -> float:
        return self.timeout_count / self.total_runs if self.total_runs else 0.0

    @property
    def warn_plus_fail_rate(self) -> float:
        return (self.warn_count + self.fail_count) / self.total_runs if self.total_runs else 1.0

    @property
    def reason_coverage_rate(self) -> float:
        return self.reason_coverage_count / self.total_runs if self.total_runs else 0.0


def _extract_verdict(row: dict) -> str:
    raw = str(row.get("sentinel_verdict") or row.get("verdict") or "").upper()
    if raw in {"PASS", "WARN", "FAIL"}:
        return raw
    return "WARN"


def _has_reason(row: dict) -> bool:
    for key in ("reason", "error", "message"):
        value = str(row.get(key, "")).strip()
        if value:
            return True
    return False


def _is_timeout(row: dict) -> bool:
    runtime = row.get("runtime")
    if isinstance(runtime, dict):
        if bool(runtime.get("timed_out")) or bool(runtime.get("global_timeout")):
            return True
    reason = str(row.get("reason") or row.get("error") or "").lower()
    return "timeout" in reason


def analyze_log(path: Path | str) -> SentinelStats:
    p = Path(path)
    if not p.exists():
        return SentinelStats(0, 0, 0, 0, 0, 0)

    pass_count = 0
    warn_count = 0
    fail_count = 0
    timeout_count = 0
    reason_coverage_count = 0
    total = 0

    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        verdict = _extract_verdict(row)
        if verdict == "PASS":
            pass_count += 1
        elif verdict == "FAIL":
            fail_count += 1
        else:
            warn_count += 1

        if _is_timeout(row):
            timeout_count += 1
        if _has_reason(row):
            reason_coverage_count += 1

    return SentinelStats(
        total_runs=total,
        pass_count=pass_count,
        warn_count=warn_count,
        fail_count=fail_count,
        timeout_count=timeout_count,
        reason_coverage_count=reason_coverage_count,
    )


def is_upstream_ready(stats: SentinelStats, policy: PortablePolicy) -> tuple[bool, list[str]]:
    cfg = policy.sentinel.readiness
    blockers: list[str] = []

    if stats.total_runs == 0:
        blockers.append("No runs found")
        return False, blockers

    if stats.pass_rate < cfg.min_pass_rate:
        blockers.append(
            f"pass_rate too low: {stats.pass_rate:.3f} < {cfg.min_pass_rate:.3f}"
        )
    if stats.timeout_rate > cfg.max_timeout_rate:
        blockers.append(
            f"timeout_rate too high: {stats.timeout_rate:.3f} > {cfg.max_timeout_rate:.3f}"
        )
    if stats.warn_plus_fail_rate > cfg.max_warn_plus_fail_rate:
        blockers.append(
            "warn_plus_fail_rate too high: "
            f"{stats.warn_plus_fail_rate:.3f} > {cfg.max_warn_plus_fail_rate:.3f}"
        )
    if stats.reason_coverage_rate < cfg.min_reason_coverage_rate:
        blockers.append(
            "reason_coverage_rate too low: "
            f"{stats.reason_coverage_rate:.3f} < {cfg.min_reason_coverage_rate:.3f}"
        )

    return len(blockers) == 0, blockers
