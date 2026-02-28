from __future__ import annotations

import copy
import fnmatch
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_POLICY: dict[str, Any] = {
    "factcheck": {
        "strict_project_patterns": [],
        "forbidden_path_prefixes": ["${HOME}/.claude/plugins/cache/omc/"],
        "forbidden_path_substrings": ["/.omc/", ".omc-config.json"],
        "readonly_command_prefixes": [
            "ls ",
            "cat ",
            "find ",
            "grep ",
            "head ",
            "tail ",
            "stat ",
            "echo ",
            "wc ",
        ],
        "warn_on_cwd_mismatch": True,
        "enforce_cwd_parity_in_quick": False,
        "warn_on_unverified_gates": True,
        "warn_on_unverified_gates_when_no_source_files": False,
    },
    "sentinel": {
        "readiness": {
            "min_pass_rate": 0.60,
            "max_timeout_rate": 0.10,
            "max_warn_plus_fail_rate": 0.40,
            "min_reason_coverage_rate": 0.95,
        }
    },
}


@dataclass(frozen=True)
class FactcheckPolicy:
    strict_project_patterns: list[str]
    forbidden_path_prefixes: list[str]
    forbidden_path_substrings: list[str]
    readonly_command_prefixes: list[str]
    warn_on_cwd_mismatch: bool
    enforce_cwd_parity_in_quick: bool
    warn_on_unverified_gates: bool
    warn_on_unverified_gates_when_no_source_files: bool


@dataclass(frozen=True)
class SentinelReadinessPolicy:
    min_pass_rate: float
    max_timeout_rate: float
    max_warn_plus_fail_rate: float
    min_reason_coverage_rate: float


@dataclass(frozen=True)
class SentinelPolicy:
    readiness: SentinelReadinessPolicy


@dataclass(frozen=True)
class PortablePolicy:
    home: Path
    workspace: Path
    factcheck: FactcheckPolicy
    sentinel: SentinelPolicy


def _deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _expand_tokens(value: Any, home: Path, workspace: Path) -> Any:
    if isinstance(value, str):
        return (
            value.replace("${HOME}", str(home)).replace("${WORKSPACE}", str(workspace))
        )
    if isinstance(value, list):
        return [_expand_tokens(v, home, workspace) for v in value]
    if isinstance(value, dict):
        return {k: _expand_tokens(v, home, workspace) for k, v in value.items()}
    return value


def load_policy(
    config_path: Path | str | None = None,
    workspace: Path | str | None = None,
    env: dict[str, str] | None = None,
) -> PortablePolicy:
    runtime_env = env or dict(os.environ)
    home = Path(runtime_env.get("HOME", str(Path.home()))).expanduser().resolve()
    workspace_path = Path(workspace or runtime_env.get("OMC_WORKSPACE", os.getcwd())).resolve()

    merged = copy.deepcopy(DEFAULT_POLICY)
    if config_path is not None:
        cfg_path = Path(config_path).expanduser()
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        merged = _deep_merge(merged, raw)

    merged = _expand_tokens(merged, home, workspace_path)

    factcheck = merged["factcheck"]
    sentinel = merged["sentinel"]
    readiness = sentinel["readiness"]

    return PortablePolicy(
        home=home,
        workspace=workspace_path,
        factcheck=FactcheckPolicy(
            strict_project_patterns=list(factcheck["strict_project_patterns"]),
            forbidden_path_prefixes=list(factcheck["forbidden_path_prefixes"]),
            forbidden_path_substrings=list(factcheck["forbidden_path_substrings"]),
            readonly_command_prefixes=list(factcheck["readonly_command_prefixes"]),
            warn_on_cwd_mismatch=bool(factcheck["warn_on_cwd_mismatch"]),
            enforce_cwd_parity_in_quick=bool(factcheck["enforce_cwd_parity_in_quick"]),
            warn_on_unverified_gates=bool(factcheck["warn_on_unverified_gates"]),
            warn_on_unverified_gates_when_no_source_files=bool(
                factcheck["warn_on_unverified_gates_when_no_source_files"]
            ),
        ),
        sentinel=SentinelPolicy(
            readiness=SentinelReadinessPolicy(
                min_pass_rate=float(readiness["min_pass_rate"]),
                max_timeout_rate=float(readiness["max_timeout_rate"]),
                max_warn_plus_fail_rate=float(readiness["max_warn_plus_fail_rate"]),
                min_reason_coverage_rate=float(readiness["min_reason_coverage_rate"]),
            )
        ),
    )


def should_use_strict_mode(project_name: str, policy: PortablePolicy) -> bool:
    return any(
        fnmatch.fnmatch(project_name, pattern)
        for pattern in policy.factcheck.strict_project_patterns
    )
