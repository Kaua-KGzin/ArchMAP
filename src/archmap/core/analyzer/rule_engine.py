from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from archmap.utils.file_utils import normalize_file_id

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

ParsedRule = tuple[set[str], set[str], str]


def file_tags(file_id: str) -> set[str]:
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


def rule_tokens(value: str) -> set[str]:
    tokens = set(TOKEN_PATTERN.findall(value.casefold()))
    if value:
        tokens.add(value.casefold())
    return {token for token in tokens if token}


def parse_rule(rule: str) -> ParsedRule | None:
    if "->" not in rule:
        return None

    source, target = rule.split("->", 1)
    source_tag = source.strip().casefold()
    target_tag = target.strip().casefold()
    if not source_tag or not target_tag:
        return None

    source_tokens = rule_tokens(source_tag)
    target_tokens = rule_tokens(target_tag)
    if not source_tokens or not target_tokens:
        return None

    return source_tokens, target_tokens, f"{source_tag} -> {target_tag}"


def build_allow_rule_map(allowed_rules: list[ParsedRule]) -> dict[str, list[ParsedRule]]:
    grouped: dict[str, list[ParsedRule]] = {}
    for source_rule, target_rule, rule_label in allowed_rules:
        key = " ".join(sorted(source_rule))
        grouped.setdefault(key, []).append((source_rule, target_rule, rule_label))
    return grouped


def allow_rule_violations(
    source: str,
    target: str,
    source_tags: set[str],
    target_tags: set[str],
    allow_map: dict[str, list[ParsedRule]],
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
                "source": source,
                "target": target,
                "kind": "allow",
                "sourceTag": " ".join(sorted(source_rule)),
                "targetTag": " ".join(sorted(target_tags)),
                "rule": " | ".join(rule_labels),
                "message": (
                    f"{source} should only depend on {', '.join(allowed_targets)} "
                    f"but currently depends on {target}"
                ),
                "allowedTargets": allowed_targets,
            }
        )

    return violations


def detect_rule_violations(
    edges: list[dict],
    forbidden_rules: list[str],
    allowed_rules: list[str],
    *,
    target_tags_fn: Callable[[str], set[str]] = file_tags,
) -> list[dict]:
    """Check `{source, target}` edges (file ids by default) against tag-based
    `"source-tag -> target-tag" `forbid`/`allow` rules.

    `target_tags_fn` lets callers tag the target side differently than the
    source side — e.g. network rules tag the source (a consumer file) by its
    folder/filename, but the target (a network service name) by its own
    tokens instead of treating it as a file path.
    """
    parsed_forbidden_rules = [parse_rule(rule) for rule in forbidden_rules]
    active_forbidden_rules = [rule for rule in parsed_forbidden_rules if rule is not None]
    parsed_allowed_rules = [parse_rule(rule) for rule in allowed_rules]
    active_allowed_rules = [rule for rule in parsed_allowed_rules if rule is not None]
    violations: list[dict] = []

    allow_map = build_allow_rule_map(active_allowed_rules)
    if not active_forbidden_rules and not allow_map:
        return violations

    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        source_tags = file_tags(source)
        target_tags = target_tags_fn(target)

        for source_rule, target_rule, rule_label in active_forbidden_rules:
            if not source_rule.issubset(source_tags):
                continue
            if not target_rule.issubset(target_tags):
                continue
            violations.append(
                {
                    "source": source,
                    "target": target,
                    "kind": "forbid",
                    "sourceTag": " ".join(sorted(source_rule)),
                    "targetTag": " ".join(sorted(target_rule)),
                    "rule": rule_label,
                    "message": (
                        f"{rule_label} is forbidden but {source} depends on {target}"
                    ),
                }
            )
        violations.extend(
            allow_rule_violations(source, target, source_tags, target_tags, allow_map)
        )

    return violations
