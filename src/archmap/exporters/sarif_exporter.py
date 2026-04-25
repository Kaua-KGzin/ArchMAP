from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from archmap.utils.file_utils import ensure_parent_dir

_SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
_SARIF_VERSION = "2.1.0"

_RULES = [
    {
        "id": "archmap/cycle",
        "name": "CircularDependency",
        "shortDescription": {"text": "Circular dependency cycle detected."},
        "helpUri": "https://archmap.dev/docs/rules/cycle",
        "defaultConfiguration": {"level": "warning"},
    },
    {
        "id": "archmap/rule-violation",
        "name": "ForbiddenDependency",
        "shortDescription": {"text": "Architecture rule violation: forbidden dependency."},
        "helpUri": "https://archmap.dev/docs/rules/rule-violation",
        "defaultConfiguration": {"level": "error"},
    },
    {
        "id": "archmap/high-risk",
        "name": "HighRiskFile",
        "shortDescription": {"text": "High-risk file (god module or dependency explosion)."},
        "helpUri": "https://archmap.dev/docs/rules/high-risk",
        "defaultConfiguration": {"level": "warning"},
    },
    {
        "id": "archmap/layer-violation",
        "name": "LayerViolation",
        "shortDescription": {"text": "Dependency violates the declared layer order."},
        "helpUri": "https://archmap.dev/docs/rules/layer-violation",
        "defaultConfiguration": {"level": "warning"},
    },
]


def export_graph_as_sarif(report: dict, output_path: str | Path) -> Path:
    target = Path(output_path).resolve()
    ensure_parent_dir(target)

    project_root = report.get("projectRoot", "")
    results: list[dict] = []

    results.extend(_cycle_results(report.get("cycles", []), project_root))
    results.extend(_rule_violation_results(report.get("architecture", {})))
    results.extend(_risk_results(report.get("risks", {}), project_root))
    results.extend(_layer_violation_results(report.get("risks", {})))

    sarif = {
        "$schema": _SARIF_SCHEMA,
        "version": _SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "ArchMAP",
                        "informationUri": "https://archmap.dev",
                        "rules": _RULES,
                    }
                },
                "originalUriBaseIds": {"PROJECTROOT": {"uri": _path_to_uri(project_root)}},
                "results": results,
                "invocations": [
                    {
                        "executionSuccessful": True,
                        "endTimeUtc": datetime.now(UTC).isoformat(),
                    }
                ],
            }
        ],
    }

    target.write_text(f"{json.dumps(sarif, indent=2)}\n", encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Result builders
# ---------------------------------------------------------------------------

def _cycle_results(cycles: list, project_root: str) -> list[dict]:
    results = []
    for cycle in cycles:
        if not cycle:
            continue
        first_file = cycle[0]
        path_str = "/".join(str(Path(first_file)).replace("\\", "/").split("/"))
        message = "Circular dependency: " + " → ".join(cycle) + " → " + cycle[0]
        results.append(
            {
                "ruleId": "archmap/cycle",
                "level": "warning",
                "message": {"text": message},
                "locations": [_file_location(path_str)],
            }
        )
    return results


def _rule_violation_results(architecture: dict) -> list[dict]:
    results = []
    for v in architecture.get("ruleViolations", []):
        source = str(v.get("source", "")).replace("\\", "/")
        message = v.get("message") or f"Forbidden dependency: {source} → {v.get('target', '')}"
        results.append(
            {
                "ruleId": "archmap/rule-violation",
                "level": "error",
                "message": {"text": message},
                "locations": [_file_location(source)],
                "relatedLocations": [
                    {
                        "id": 1,
                        "message": {"text": "Imported by forbidden rule"},
                        "physicalLocation": _physical_location(str(v.get("target", "")).replace("\\", "/")),
                    }
                ],
            }
        )
    return results


def _risk_results(risks: dict, project_root: str) -> list[dict]:
    results = []
    seen: set[str] = set()
    for category in ("god_modules", "dependency_explosions"):
        for item in risks.get(category, []):
            file_id = str(item.get("id", item) if isinstance(item, dict) else item).replace("\\", "/")
            if file_id in seen:
                continue
            seen.add(file_id)
            label = "god module" if category == "god_modules" else "dependency explosion"
            results.append(
                {
                    "ruleId": "archmap/high-risk",
                    "level": "warning",
                    "message": {"text": f"High-risk file ({label}): {file_id}"},
                    "locations": [_file_location(file_id)],
                }
            )
    return results


def _layer_violation_results(risks: dict) -> list[dict]:
    results = []
    for v in risks.get("layer_violations", []):
        source = str(v.get("source", "")).replace("\\", "/")
        target = str(v.get("target", "")).replace("\\", "/")
        results.append(
            {
                "ruleId": "archmap/layer-violation",
                "level": "warning",
                "message": {
                    "text": f"Layer violation: {source} depends on {target} (violates declared layer order)"
                },
                "locations": [_file_location(source)],
            }
        )
    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _file_location(file_id: str) -> dict:
    return {"physicalLocation": _physical_location(file_id)}


def _physical_location(file_id: str) -> dict:
    return {
        "artifactLocation": {
            "uri": file_id,
            "uriBaseId": "PROJECTROOT",
        },
        "region": {"startLine": 1},
    }


def _path_to_uri(path: str) -> str:
    p = Path(path).resolve()
    uri = p.as_uri()
    if not uri.endswith("/"):
        uri += "/"
    return uri
