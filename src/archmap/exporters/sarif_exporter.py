from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from archmap import __version__
from archmap.utils.file_utils import ensure_parent_dir

# SARIF rule IDs
_RULE_CIRCULAR = "ARCH001"
_RULE_LAYER = "ARCH002"
_RULE_GOD_MODULE = "ARCH003"
_RULE_DEP_EXPLOSION = "ARCH004"
_RULE_CUSTOM = "ARCH005"

_RULES = [
    {
        "id": _RULE_CIRCULAR,
        "name": "CircularDependency",
        "shortDescription": {"text": "Circular dependency between modules"},
        "fullDescription": {
            "text": (
                "Two or more files form a directed cycle. "
                "Circular dependencies make code harder to test, reason about, and refactor."
            )
        },
        "helpUri": "https://github.com/Kaua-KGzin/ArchMAP/blob/main/docs/rules.md#ARCH001",
        "defaultConfiguration": {"level": "warning"},
        "properties": {"tags": ["architecture", "coupling"]},
    },
    {
        "id": _RULE_LAYER,
        "name": "LayerViolation",
        "shortDescription": {"text": "Forbidden inter-layer dependency"},
        "fullDescription": {
            "text": (
                "A dependency flows against a configured architectural rule "
                "(e.g. core -> cli is forbidden)."
            )
        },
        "helpUri": "https://github.com/Kaua-KGzin/ArchMAP/blob/main/docs/rules.md#ARCH002",
        "defaultConfiguration": {"level": "error"},
        "properties": {"tags": ["architecture", "layers"]},
    },
    {
        "id": _RULE_GOD_MODULE,
        "name": "GodModule",
        "shortDescription": {"text": "Module with excessive coupling"},
        "fullDescription": {
            "text": (
                "A file imports a disproportionately large number of other modules, "
                "becoming a coupling bottleneck."
            )
        },
        "helpUri": "https://github.com/Kaua-KGzin/ArchMAP/blob/main/docs/rules.md#ARCH003",
        "defaultConfiguration": {"level": "note"},
        "properties": {"tags": ["architecture", "complexity"]},
    },
    {
        "id": _RULE_DEP_EXPLOSION,
        "name": "DependencyExplosion",
        "shortDescription": {"text": "Explosive growth in outgoing dependencies"},
        "fullDescription": {
            "text": (
                "A file's outgoing dependency count is far above the project average, "
                "indicating an abstraction or responsibility leak."
            )
        },
        "helpUri": "https://github.com/Kaua-KGzin/ArchMAP/blob/main/docs/rules.md#ARCH004",
        "defaultConfiguration": {"level": "note"},
        "properties": {"tags": ["architecture", "complexity"]},
    },
    {
        "id": _RULE_CUSTOM,
        "name": "CustomRuleViolation",
        "shortDescription": {"text": "Custom architecture rule violated"},
        "fullDescription": {
            "text": (
                "A dependency violates an allow/forbid rule defined in .archmap.toml."
            )
        },
        "helpUri": "https://github.com/Kaua-KGzin/ArchMAP/blob/main/docs/rules.md#ARCH005",
        "defaultConfiguration": {"level": "error"},
        "properties": {"tags": ["architecture", "custom-rules"]},
    },
]


def export_graph_as_sarif(report: dict, output_path: str | Path) -> Path:
    target = Path(output_path).resolve()
    ensure_parent_dir(target)

    results = _build_results(report)
    document = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "ArchMAP",
                        "version": __version__,
                        "informationUri": "https://github.com/Kaua-KGzin/ArchMAP",
                        "rules": _RULES,
                    }
                },
                "originalUriBaseIds": {
                    "%SRCROOT%": {"uri": _path_to_uri(report.get("projectRoot", "."))}
                },
                "results": results,
                "properties": {
                    "generatedAt": datetime.now(UTC).isoformat(),
                    "projectRoot": report.get("projectRoot", "."),
                    "filesAnalyzed": report.get("metrics", {}).get("filesAnalyzed", 0),
                    "healthScore": report.get("architecture", {})
                    .get("health", {})
                    .get("score", 0),
                },
            }
        ],
    }

    target.write_text(f"{json.dumps(document, indent=2)}\n", encoding="utf-8")
    return target


def _build_results(report: dict) -> list[dict]:
    results: list[dict] = []
    project_root = report.get("projectRoot", ".")

    _append_cycle_results(results, report.get("cycles", []), project_root)
    _append_layer_results(results, report.get("risks", {}), project_root)
    _append_god_module_results(results, report.get("risks", {}), project_root)
    _append_explosion_results(results, report.get("risks", {}), project_root)
    _append_custom_rule_results(results, report.get("architecture", {}), project_root)

    return results


def _append_cycle_results(
    results: list[dict], cycles: list, project_root: str
) -> None:
    for cycle in cycles:
        if not cycle:
            continue
        members = cycle if isinstance(cycle, list) else cycle.get("members", [])
        if not members:
            continue

        path_display = " → ".join(members)
        if len(members) > 1:
            path_display += f" → {members[0]}"

        # Emit one result per file in the cycle, all sharing the same message
        for file_id in members:
            results.append(
                {
                    "ruleId": _RULE_CIRCULAR,
                    "level": "warning",
                    "message": {
                        "text": f"Circular dependency: {path_display}"
                    },
                    "locations": [_make_location(file_id, project_root)],
                    "relatedLocations": [
                        {
                            "id": idx,
                            "message": {"text": "Also part of this cycle"},
                            **_make_location(other, project_root),
                        }
                        for idx, other in enumerate(members)
                        if other != file_id
                    ],
                }
            )


def _append_layer_results(
    results: list[dict], risks: dict, project_root: str
) -> None:
    for violation in risks.get("layer_violations", []):
        source = violation.get("from", "")
        target_file = violation.get("to", "")
        rule_text = violation.get("rule", f"{source} -> {target_file}")
        results.append(
            {
                "ruleId": _RULE_LAYER,
                "level": "error",
                "message": {
                    "text": (
                        f"Layer violation: {source} → {target_file} "
                        f"(rule: {rule_text})"
                    )
                },
                "locations": [_make_location(source, project_root)],
            }
        )


def _append_god_module_results(
    results: list[dict], risks: dict, project_root: str
) -> None:
    for item in risks.get("god_modules", []):
        file_id = item.get("file", "")
        outgoing = item.get("outgoing", 0)
        results.append(
            {
                "ruleId": _RULE_GOD_MODULE,
                "level": "note",
                "message": {
                    "text": (
                        f"God module: '{file_id}' imports {outgoing} modules "
                        "(excessive coupling)"
                    )
                },
                "locations": [_make_location(file_id, project_root)],
            }
        )


def _append_explosion_results(
    results: list[dict], risks: dict, project_root: str
) -> None:
    for item in risks.get("dependency_explosions", []):
        file_id = item.get("file", "")
        outgoing = item.get("outgoing", 0)
        results.append(
            {
                "ruleId": _RULE_DEP_EXPLOSION,
                "level": "note",
                "message": {
                    "text": (
                        f"Dependency explosion: '{file_id}' has {outgoing} outgoing "
                        "dependencies (far above average)"
                    )
                },
                "locations": [_make_location(file_id, project_root)],
            }
        )


def _append_custom_rule_results(
    results: list[dict], architecture: dict, project_root: str
) -> None:
    for violation in architecture.get("ruleViolations", []):
        source = violation.get("from", "")
        target_file = violation.get("to", "")
        rule_text = violation.get("rule", f"{source} -> {target_file}")
        results.append(
            {
                "ruleId": _RULE_CUSTOM,
                "level": "error",
                "message": {
                    "text": (
                        f"Custom rule violated: {source} → {target_file} "
                        f"(rule: {rule_text})"
                    )
                },
                "locations": [_make_location(source, project_root)],
            }
        )


def _make_location(file_id: str, project_root: str) -> dict:
    return {
        "physicalLocation": {
            "artifactLocation": {
                "uri": file_id,
                "uriBaseId": "%SRCROOT%",
            }
        }
    }


def _path_to_uri(path: str) -> str:
    resolved = Path(path).resolve()
    uri = resolved.as_uri()
    if not uri.endswith("/"):
        uri += "/"
    return uri
