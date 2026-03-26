from __future__ import annotations

import re
from pathlib import Path

from archmap.core.analyzer.risk_analyzer import DEFAULT_LAYER_ORDER
from archmap.utils.file_utils import normalize_file_id

GROUP_WRAPPERS = {"src", "app", "lib", "packages", "services"}
SERVICE_ENTRYPOINT_NAMES = {"main", "app", "server", "api", "service"}
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def analyze_architecture(
    nodes: list[dict],
    edges: list[dict],
    cycles: list[list[str]],
    risks: dict,
    layer_order: dict[str, int] | None = None,
    forbidden_rules: list[str] | None = None,
    allowed_rules: list[str] | None = None,
) -> dict:
    file_nodes = [node for node in nodes if node.get("type") == "file"]
    file_node_ids = {node["id"] for node in file_nodes}
    file_edges = [
        edge
        for edge in edges
        if edge.get("source") in file_node_ids and edge.get("target") in file_node_ids
    ]
    groups_by_file = {
        node["id"]: _logical_group(node["id"])
        for node in file_nodes
    }
    active_layer_order = _build_layer_order(layer_order)
    detected_layers = _detect_layers(file_nodes, active_layer_order)
    style = _detect_style(file_nodes, file_edges, groups_by_file, detected_layers)
    rule_violations = _detect_rule_violations(
        file_edges,
        forbidden_rules or [],
        allowed_rules or [],
    )
    health = _compute_health(
        cycles=cycles,
        risks=risks,
        rule_violations=rule_violations,
        file_edges=file_edges,
        groups_by_file=groups_by_file,
    )

    return {
        "detectedStyle": style,
        "detectedLayers": detected_layers,
        "activeRules": {
            "forbid": list(forbidden_rules or []),
            "allow": list(allowed_rules or []),
        },
        "ruleViolations": rule_violations,
        "health": health,
    }


def _build_layer_order(custom_layer_order: dict[str, int] | None) -> dict[str, int]:
    merged = dict(DEFAULT_LAYER_ORDER)
    if not custom_layer_order:
        return merged

    for key, value in custom_layer_order.items():
        merged[str(key).strip().casefold()] = int(value)

    return merged


def _detect_layers(file_nodes: list[dict], layer_order: dict[str, int]) -> list[str]:
    detected: set[str] = set()
    known_layers = set(layer_order)
    for node in file_nodes:
        detected.update(tag for tag in _file_tags(node["id"]) if tag in known_layers)

    return sorted(detected, key=lambda item: (-layer_order[item], item))


def _detect_style(
    file_nodes: list[dict],
    file_edges: list[dict],
    groups_by_file: dict[str, str],
    detected_layers: list[str],
) -> dict:
    group_count = len(set(groups_by_file.values()))
    cross_group_ratio = _cross_group_ratio(file_edges, groups_by_file)
    service_like_groups = _count_service_like_groups(file_nodes, groups_by_file)
    file_count = len(file_nodes)

    reasons = [
        f"{group_count} logical group(s) detected",
        f"{round(cross_group_ratio * 100)}% of file dependencies cross group boundaries",
    ]
    if detected_layers:
        reasons.append(f"layered folders detected: {', '.join(detected_layers)}")

    if group_count <= 1:
        confidence = 0.92 if file_count >= 1 else 0.5
        reasons.append("most code lives under a single logical group")
        return {
            "name": "monolith",
            "confidence": round(confidence, 2),
            "reasons": reasons,
        }

    if (
        group_count >= 3
        and service_like_groups >= max(2, group_count // 2)
        and cross_group_ratio <= 0.2
    ):
        reasons.append("multiple groups expose service-like entrypoints with low cross-coupling")
        confidence = min(0.95, 0.68 + ((1 - cross_group_ratio) * 0.2))
        return {
            "name": "microservice_like",
            "confidence": round(confidence, 2),
            "reasons": reasons,
        }

    reasons.append("multiple groups collaborate inside one deployable codebase")
    confidence = min(0.9, 0.6 + ((1 - cross_group_ratio) * 0.2))
    return {
        "name": "modular_monolith",
        "confidence": round(confidence, 2),
        "reasons": reasons,
    }


def _detect_rule_violations(
    file_edges: list[dict],
    forbidden_rules: list[str],
    allowed_rules: list[str],
) -> list[dict]:
    parsed_forbidden_rules = [_parse_rule(rule) for rule in forbidden_rules]
    active_forbidden_rules = [
        rule for rule in parsed_forbidden_rules if rule is not None
    ]
    parsed_allowed_rules = [_parse_rule(rule) for rule in allowed_rules]
    active_allowed_rules = [rule for rule in parsed_allowed_rules if rule is not None]
    violations: list[dict] = []

    allow_map = _build_allow_rule_map(active_allowed_rules)
    if not active_forbidden_rules and not allow_map:
        return violations

    for edge in file_edges:
        source_tags = _file_tags(edge["source"])
        target_tags = _file_tags(edge["target"])
        for source_rule, target_rule, rule_label in active_forbidden_rules:
            if not source_rule.issubset(source_tags):
                continue
            if not target_rule.issubset(target_tags):
                continue
            violations.append(
                {
                    "source": edge["source"],
                    "target": edge["target"],
                    "kind": "forbid",
                    "sourceTag": " ".join(sorted(source_rule)),
                    "targetTag": " ".join(sorted(target_rule)),
                    "rule": rule_label,
                    "message": (
                        f"{rule_label} is forbidden but {edge['source']} depends on "
                        f"{edge['target']}"
                    ),
                }
            )
        violations.extend(_allow_rule_violations(edge, source_tags, target_tags, allow_map))

    return violations


def _compute_health(
    *,
    cycles: list[list[str]],
    risks: dict,
    rule_violations: list[dict],
    file_edges: list[dict],
    groups_by_file: dict[str, str],
) -> dict:
    layer_violations = risks.get("layer_violations", [])
    god_modules = risks.get("god_modules", [])
    dependency_explosions = risks.get("dependency_explosions", [])
    cross_group_ratio = _cross_group_ratio(file_edges, groups_by_file)

    penalties = [
        (min(30, len(cycles) * 12), f"{len(cycles)} circular dependency group(s)"),
        (min(18, len(layer_violations) * 6), f"{len(layer_violations)} layer violation(s)"),
        (min(20, len(rule_violations) * 8), f"{len(rule_violations)} custom rule violation(s)"),
        (min(15, len(god_modules) * 5), f"{len(god_modules)} god module(s)"),
        (
            min(15, len(dependency_explosions) * 4),
            f"{len(dependency_explosions)} dependency explosion(s)",
        ),
    ]
    if len(set(groups_by_file.values())) > 1:
        penalties.append(
            (
                min(12, round(cross_group_ratio * 20)),
                f"{round(cross_group_ratio * 100)}% cross-group dependency ratio",
            )
        )

    score = 100 - sum(points for points, _ in penalties)
    score = max(0, min(100, score))
    grade = _grade_for_score(score)
    drivers = [label for points, label in penalties if points > 0]

    return {
        "score": score,
        "grade": grade,
        "summary": _health_summary(grade),
        "drivers": drivers,
    }


def _logical_group(file_id: str) -> str:
    parts = [
        part.casefold()
        for part in normalize_file_id(file_id).split("/")
        if part and part != "."
    ]
    if not parts or len(parts) == 1:
        return "."
    if parts[0] in GROUP_WRAPPERS and len(parts) > 1:
        return parts[1]
    return parts[0]


def _count_service_like_groups(file_nodes: list[dict], groups_by_file: dict[str, str]) -> int:
    by_group: dict[str, set[str]] = {}
    for node in file_nodes:
        group = groups_by_file[node["id"]]
        by_group.setdefault(group, set()).add(Path(node["id"]).stem.casefold())

    return sum(
        1
        for basenames in by_group.values()
        if basenames & SERVICE_ENTRYPOINT_NAMES
    )


def _cross_group_ratio(file_edges: list[dict], groups_by_file: dict[str, str]) -> float:
    if not file_edges:
        return 0.0

    cross_group_edges = sum(
        1
        for edge in file_edges
        if groups_by_file.get(edge["source"]) != groups_by_file.get(edge["target"])
    )
    return cross_group_edges / len(file_edges)


def _file_tags(file_id: str) -> set[str]:
    normalized = normalize_file_id(file_id).casefold()
    parts = [part for part in normalized.split("/") if part and part != "."]
    tags: set[str] = set(parts)

    for part in parts:
        tags.update(TOKEN_PATTERN.findall(part))
        stem = Path(part).stem.casefold()
        if stem:
            tags.add(stem)
            tags.update(TOKEN_PATTERN.findall(stem))

    return tags


def _parse_rule(rule: str) -> tuple[set[str], set[str], str] | None:
    if "->" not in rule:
        return None

    source, target = rule.split("->", 1)
    source_tag = source.strip().casefold()
    target_tag = target.strip().casefold()
    if not source_tag or not target_tag:
        return None

    source_tokens = _rule_tokens(source_tag)
    target_tokens = _rule_tokens(target_tag)
    if not source_tokens or not target_tokens:
        return None

    return source_tokens, target_tokens, f"{source_tag} -> {target_tag}"


def _build_allow_rule_map(
    allowed_rules: list[tuple[set[str], set[str], str]]
) -> dict[str, list[tuple[set[str], set[str], str]]]:
    grouped: dict[str, list[tuple[set[str], set[str], str]]] = {}
    for source_rule, target_rule, rule_label in allowed_rules:
        key = " ".join(sorted(source_rule))
        grouped.setdefault(key, []).append((source_rule, target_rule, rule_label))
    return grouped


def _allow_rule_violations(
    edge: dict,
    source_tags: set[str],
    target_tags: set[str],
    allow_map: dict[str, list[tuple[set[str], set[str], str]]],
) -> list[dict]:
    violations: list[dict] = []
    matched_source_groups = [
        source_rules
        for source_rules in allow_map.values()
        if source_rules and source_rules[0][0].issubset(source_tags)
    ]

    for source_rule_group in matched_source_groups:
        if any(target_rule.issubset(target_tags) for _, target_rule, _ in source_rule_group):
            continue

        allowed_targets = sorted(
            {
                " ".join(sorted(target_rule))
                for _, target_rule, _ in source_rule_group
            }
        )
        rule_labels = sorted({rule_label for _, _, rule_label in source_rule_group})
        source_rule = source_rule_group[0][0]
        violations.append(
            {
                "source": edge["source"],
                "target": edge["target"],
                "kind": "allow",
                "sourceTag": " ".join(sorted(source_rule)),
                "targetTag": " ".join(sorted(target_tags)),
                "rule": " | ".join(rule_labels),
                "message": (
                    f"{edge['source']} should only depend on {', '.join(allowed_targets)} "
                    f"but currently depends on {edge['target']}"
                ),
                "allowedTargets": allowed_targets,
            }
        )

    return violations


def _rule_tokens(value: str) -> set[str]:
    tokens = set(TOKEN_PATTERN.findall(value.casefold()))
    if value:
        tokens.add(value.casefold())
    return {token for token in tokens if token}


def _grade_for_score(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 45:
        return "D"
    return "F"


def _health_summary(grade: str) -> str:
    if grade == "A":
        return "Architecture looks healthy and enforceable."
    if grade == "B":
        return "Architecture is mostly healthy with manageable drift."
    if grade == "C":
        return "Architecture is serviceable but drift is accumulating."
    if grade == "D":
        return "Architecture needs active refactoring attention."
    return "Architecture is unstable and needs intervention."
