from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import PortablePolicy


REQUIRED_FIELDS = {
    "schema_version",
    "run_id",
    "ts",
    "cwd",
    "mode",
    "files_modified",
    "files_created",
    "artifacts_expected",
    "gates",
}
REQUIRED_GATES = {
    "selftest_ran",
    "goldens_ran",
    "sentinel_stop_smoke_ran",
    "shadow_leak_check_ran",
}


@dataclass(frozen=True)
class Mismatch:
    check: str
    severity: str
    detail: str


def _severity_rank(value: str) -> int:
    if value == "FAIL":
        return 2
    if value == "WARN":
        return 1
    return 0


def _source_file_count(claims: dict[str, Any]) -> int:
    return len(claims.get("files_modified", [])) + len(claims.get("files_created", []))


def _missing_required_fields(claims: dict[str, Any]) -> list[str]:
    return sorted(field for field in REQUIRED_FIELDS if field not in claims)


def _missing_required_gates(claims: dict[str, Any]) -> list[str]:
    gates = claims.get("gates", {})
    return sorted(g for g in REQUIRED_GATES if g not in gates)


def _check_paths(claims: dict[str, Any], policy: PortablePolicy) -> list[Mismatch]:
    out: list[Mismatch] = []
    all_paths = (
        claims.get("files_modified", [])
        + claims.get("files_created", [])
        + claims.get("artifacts_expected", [])
    )
    deleted = set(claims.get("files_deleted", []))

    for raw in all_paths:
        path_str = str(raw)
        if path_str in deleted:
            continue

        for prefix in policy.factcheck.forbidden_path_prefixes:
            if path_str.startswith(prefix):
                out.append(Mismatch("H", "FAIL", f"Forbidden path prefix: {path_str}"))
                break

        for fragment in policy.factcheck.forbidden_path_substrings:
            if fragment in path_str:
                out.append(Mismatch("H", "FAIL", f"Forbidden path fragment: {path_str}"))
                break

        p = Path(path_str)
        if not p.exists():
            out.append(Mismatch("C", "FAIL", f"File not found: {path_str}"))

    return out


def _check_commands(claims: dict[str, Any], policy: PortablePolicy) -> list[Mismatch]:
    out: list[Mismatch] = []
    commands = [str(c) for c in claims.get("commands_executed", [])]

    for cmd in commands:
        hit_prefix = any(
            forbidden in cmd for forbidden in policy.factcheck.forbidden_path_prefixes
        )
        if not hit_prefix:
            continue
        stripped = cmd.strip().lstrip("(")
        is_read_only = any(
            stripped.startswith(prefix) for prefix in policy.factcheck.readonly_command_prefixes
        )
        if not is_read_only:
            out.append(Mismatch("H", "FAIL", f"Forbidden mutating command: {cmd}"))

    return out


def run_checks(
    claims: dict[str, Any],
    mode: str,
    policy: PortablePolicy,
    runtime_cwd: str | Path | None = None,
) -> dict[str, Any]:
    """Run portable factcheck logic.

    Modes supported: strict, declared, manual, quick.
    """
    mismatches: list[Mismatch] = []
    notes: list[str] = []

    missing_fields = _missing_required_fields(claims)
    if missing_fields:
        mismatches.append(Mismatch("A", "FAIL", f"Missing required fields: {missing_fields}"))

    missing_gates = _missing_required_gates(claims)
    if missing_gates:
        mismatches.append(Mismatch("A", "FAIL", f"Missing required gates: {missing_gates}"))

    gates = claims.get("gates", {})
    false_gates = sorted(k for k, v in gates.items() if k in REQUIRED_GATES and not bool(v))
    source_files = _source_file_count(claims)

    if mode == "strict" and false_gates:
        mismatches.append(
            Mismatch("B", "FAIL", f"Strict mode requires all gates true, got false: {false_gates}")
        )
    elif mode in {"declared", "manual"} and false_gates and policy.factcheck.warn_on_unverified_gates:
        if source_files > 0 or policy.factcheck.warn_on_unverified_gates_when_no_source_files:
            mismatches.append(
                Mismatch("B", "WARN", f"Unverified gates in declared/manual mode: {false_gates}")
            )
        else:
            notes.append("No source files declared; unverified gates are ignored by policy")

    mismatches.extend(_check_paths(claims, policy))
    mismatches.extend(_check_commands(claims, policy))

    runtime = Path(runtime_cwd or Path.cwd()).resolve()
    claims_cwd = str(claims.get("cwd", "")).strip()
    claims_cwd_canonical = str(Path(claims_cwd).expanduser().resolve()) if claims_cwd else ""

    enforce_cwd = policy.factcheck.warn_on_cwd_mismatch and (
        mode != "quick" or policy.factcheck.enforce_cwd_parity_in_quick
    )
    if enforce_cwd and claims_cwd and claims_cwd_canonical != str(runtime):
        severity = "FAIL" if mode == "strict" else "WARN"
        mismatches.append(
            Mismatch(
                "argv_parity",
                severity,
                f"claims.cwd={claims_cwd_canonical} runtime.cwd={runtime}",
            )
        )

    max_rank = max((_severity_rank(m.severity) for m in mismatches), default=0)
    verdict = "PASS"
    if max_rank == 2:
        verdict = "FAIL"
    elif max_rank == 1:
        verdict = "WARN"

    return {
        "verdict": verdict,
        "mode": mode,
        "mismatches": [m.__dict__ for m in mismatches],
        "notes": notes,
        "claims_evidence": {
            "source_files": source_files,
            "commands_count": len(claims.get("commands_executed", [])),
            "models_count": len(claims.get("models_used", [])),
        },
    }
