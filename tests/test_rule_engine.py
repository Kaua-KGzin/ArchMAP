from __future__ import annotations

from archmap.core.analyzer.rule_engine import detect_rule_violations, file_tags, rule_tokens


def test_file_tags_includes_path_segments_and_stem() -> None:
    tags = file_tags("src/frontend/widget.py")

    assert "frontend" in tags
    assert "widget" in tags
    assert "src" in tags


def test_rule_tokens_tokenizes_hyphenated_names() -> None:
    tokens = rule_tokens("ms-sql")

    assert "ms" in tokens
    assert "sql" in tokens
    assert "ms-sql" in tokens


def test_detect_rule_violations_flags_forbidden_edge() -> None:
    edges = [{"source": "src/frontend/widget.py", "target": "src/database/client.py"}]

    violations = detect_rule_violations(edges, ["frontend -> database"], [])

    assert len(violations) == 1
    assert violations[0]["kind"] == "forbid"


def test_detect_rule_violations_allows_non_matching_edge() -> None:
    edges = [{"source": "src/backend/service.py", "target": "src/database/client.py"}]

    violations = detect_rule_violations(edges, ["frontend -> database"], [])

    assert violations == []


def test_detect_rule_violations_flags_allow_rule_breach() -> None:
    edges = [{"source": "src/controller/user.py", "target": "src/database/client.py"}]

    violations = detect_rule_violations(edges, [], ["controller -> service"])

    assert len(violations) == 1
    assert violations[0]["kind"] == "allow"


def test_detect_rule_violations_no_rules_returns_empty() -> None:
    edges = [{"source": "a.py", "target": "b.py"}]

    assert detect_rule_violations(edges, [], []) == []


def test_detect_rule_violations_custom_target_tags_fn() -> None:
    edges = [{"source": "src/frontend/widget.py", "target": "postgresql"}]

    violations = detect_rule_violations(
        edges, ["frontend -> postgresql"], [], target_tags_fn=rule_tokens
    )

    assert len(violations) == 1
    assert violations[0]["target"] == "postgresql"
