from __future__ import annotations

import tomllib
from pathlib import Path
from typing import NotRequired, TypedDict

from archmap.utils.file_utils import normalize_file_id

__all__ = [
    "AnalysisConfig",
    "ArchitectureConfig",
    "ArchitectureRulesConfig",
    "BudgetsConfig",
    "ProjectConfig",
    "RiskConfig",
    "default_project_config",
    "load_project_config",
]

CONFIG_FILENAMES = (".archmap.toml", "archmap.toml")

_ABSOLUTE_MAX_COUPLING = 10_000  # sanity ceiling for budget values


class BudgetsConfig(TypedDict):
    max_outgoing_per_file: NotRequired[int | None]
    max_incoming_per_file: NotRequired[int | None]


class AnalysisConfig(TypedDict):
    ignore_dirs: list[str]
    max_file_size_bytes: int
    parallel: bool
    cache: bool
    budgets: BudgetsConfig


class ArchitectureRulesConfig(TypedDict):
    forbid: list[str]
    allow: list[str]


class ArchitectureConfig(TypedDict):
    rules: ArchitectureRulesConfig


class RiskConfig(TypedDict):
    layer_order: dict[str, int]


class ProjectConfig(TypedDict):
    analysis: AnalysisConfig
    architecture: ArchitectureConfig
    risks: RiskConfig


DEFAULT_MAX_FILE_SIZE_BYTES = 1_048_576
_ABSOLUTE_MAX_FILE_SIZE_BYTES = 104_857_600  # 100 MB hard ceiling


def default_project_config() -> ProjectConfig:
    return {
        "analysis": {
            "ignore_dirs": [],
            "max_file_size_bytes": DEFAULT_MAX_FILE_SIZE_BYTES,
            "parallel": True,
            "cache": True,
            "budgets": {},
        },
        "architecture": {"rules": {"forbid": [], "allow": []}},
        "risks": {"layer_order": {}},
    }


def load_project_config(
    project_root: str | Path,
    virtual_files: dict[str, str] | None = None,
) -> ProjectConfig:
    root = Path(project_root).resolve()
    payload = _read_config_payload(root, virtual_files)
    if payload is None:
        return default_project_config()

    parsed = tomllib.loads(payload)
    if not isinstance(parsed, dict):
        return default_project_config()

    analysis_section = parsed.get("analysis", {})
    architecture_section = parsed.get("architecture", {})
    risk_section = parsed.get("risk", {})
    risks_section = parsed.get("risks", {})
    rules_section = architecture_section.get("rules", {})
    layer_section = risks_section.get("layer_order", risk_section.get("layer_order", {}))
    budgets_section = (
        analysis_section.get("budgets", {}) if isinstance(analysis_section, dict) else {}
    )

    return {
        "analysis": {
            "ignore_dirs": _normalize_ignore_dirs(analysis_section),
            "max_file_size_bytes": _normalize_max_file_size(analysis_section),
            "parallel": _normalize_parallel(analysis_section),
            "cache": _normalize_bool_field(analysis_section, "cache", default=True),
            "budgets": _normalize_budgets(budgets_section),
        },
        "architecture": {
            "rules": {
                "forbid": _normalize_rule_list(rules_section, "forbid"),
                "allow": _normalize_rule_list(rules_section, "allow"),
            }
        },
        "risks": {
            "layer_order": _normalize_layer_order(layer_section),
        },
    }


def _read_config_payload(
    project_root: Path,
    virtual_files: dict[str, str] | None,
) -> str | None:
    if virtual_files is not None:
        normalized_files = {
            normalize_file_id(path): content
            for path, content in virtual_files.items()
        }
        for filename in CONFIG_FILENAMES:
            payload = normalized_files.get(filename)
            if payload is not None:
                return payload
        return None

    for filename in CONFIG_FILENAMES:
        config_path = project_root / filename
        if config_path.is_file():
            return config_path.read_text(encoding="utf-8")
    return None


def _normalize_ignore_dirs(section: object) -> list[str]:
    if not isinstance(section, dict):
        return []

    raw_values = section.get("ignore_dirs", section.get("extra_ignored_dirs", []))
    if not isinstance(raw_values, list):
        return []

    normalized: list[str] = []
    for value in raw_values:
        if not isinstance(value, str):
            continue
        cleaned = normalize_file_id(value).strip("/")
        if cleaned:
            normalized.append(cleaned)

    return normalized


def _normalize_max_file_size(section: object) -> int:
    if not isinstance(section, dict):
        return DEFAULT_MAX_FILE_SIZE_BYTES

    raw_value = section.get(
        "max_file_size_bytes",
        section.get("max_file_size", DEFAULT_MAX_FILE_SIZE_BYTES),
    )
    if isinstance(raw_value, bool) or not isinstance(raw_value, int):
        return DEFAULT_MAX_FILE_SIZE_BYTES

    return max(0, min(raw_value, _ABSOLUTE_MAX_FILE_SIZE_BYTES))


def _normalize_parallel(section: object) -> bool:
    if not isinstance(section, dict):
        return True
    val = section.get("parallel", True)
    return bool(val)


def _normalize_bool_field(section: object, key: str, *, default: bool) -> bool:
    if not isinstance(section, dict):
        return default
    val = section.get(key, default)
    return bool(val)


def _normalize_layer_order(section: object) -> dict[str, int]:
    if not isinstance(section, dict):
        return {}

    normalized: dict[str, int] = {}
    for key, value in section.items():
        if not isinstance(key, str):
            continue
        if not isinstance(value, int):
            continue
        normalized[key.strip().casefold()] = value

    return normalized


def _normalize_rule_list(section: object, key: str) -> list[str]:
    if not isinstance(section, dict):
        return []

    raw_values = section.get(key, [])
    if not isinstance(raw_values, list):
        return []

    normalized: list[str] = []
    for value in raw_values:
        if not isinstance(value, str):
            continue
        if "->" not in value:
            continue
        source, target = value.split("->", 1)
        source_tag = source.strip().casefold()
        target_tag = target.strip().casefold()
        if source_tag and target_tag:
            normalized.append(f"{source_tag} -> {target_tag}")

    return normalized


def _normalize_budgets(section: object) -> BudgetsConfig:
    if not isinstance(section, dict):
        return {}

    def _parse_budget_value(key: str) -> int | None:
        val = section.get(key)
        if val is None:
            return None
        if isinstance(val, bool) or not isinstance(val, int):
            return None
        return max(0, min(val, _ABSOLUTE_MAX_COUPLING))

    return {
        "max_outgoing_per_file": _parse_budget_value("max_outgoing_per_file"),
        "max_incoming_per_file": _parse_budget_value("max_incoming_per_file"),
    }
