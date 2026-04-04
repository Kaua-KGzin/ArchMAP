from __future__ import annotations

from collections.abc import Callable

from archmap.core.analyzer.dependency_graph import analyze_graph
from archmap.core.graph.graph_builder import build_graph

ParsedFileFactory = Callable[..., dict]
DependencyFactory = Callable[..., dict]


def test_analyze_graph_reports_custom_rule_violations_and_health(
    make_parsed_file: ParsedFileFactory,
    make_dependency: DependencyFactory,
) -> None:
    parsed_project = {
        "projectRoot": "/workspace",
        "parsedFiles": [
            make_parsed_file(
                "src/controller/users.py",
                dependencies=[make_dependency("src/repository/users.py")],
            ),
            make_parsed_file(
                "src/service/users.py",
                dependencies=[make_dependency("src/repository/users.py")],
            ),
            make_parsed_file("src/repository/users.py"),
        ],
    }

    graph = build_graph(parsed_project)
    report = analyze_graph(
        graph,
        layer_order={"controller": 5, "service": 4, "repository": 2},
        forbidden_rules=["controller -> repository"],
    )

    assert report["architecture"]["detectedStyle"]["name"] == "modular_monolith"
    assert report["architecture"]["detectedLayers"] == ["controller", "service", "repository"]
    assert report["architecture"]["activeRules"] == {
        "forbid": ["controller -> repository"],
        "allow": [],
    }
    assert report["architecture"]["ruleViolations"] == [
        {
            "source": "src/controller/users.py",
            "target": "src/repository/users.py",
            "kind": "forbid",
            "sourceTag": "controller",
            "targetTag": "repository",
            "rule": "controller -> repository",
            "message": (
                "controller -> repository is forbidden but src/controller/users.py "
                "depends on src/repository/users.py"
            ),
        }
    ]
    assert report["architecture"]["health"] == {
        "score": 80,
        "grade": "B",
        "summary": "Architecture is mostly healthy with manageable drift.",
        "drivers": ["1 custom rule violation(s)", "100% cross-group dependency ratio"],
    }


def test_analyze_graph_detects_microservice_like_topology(
    make_parsed_file: ParsedFileFactory,
    make_dependency: DependencyFactory,
) -> None:
    parsed_project = {
        "projectRoot": "/workspace",
        "parsedFiles": [
            make_parsed_file(
                "src/payments/main.py",
                dependencies=[make_dependency("src/payments/domain.py")],
            ),
            make_parsed_file("src/payments/domain.py"),
            make_parsed_file(
                "src/billing/main.py",
                dependencies=[make_dependency("src/billing/domain.py")],
            ),
            make_parsed_file("src/billing/domain.py"),
            make_parsed_file(
                "src/users/main.py",
                dependencies=[make_dependency("src/users/domain.py")],
            ),
            make_parsed_file("src/users/domain.py"),
        ],
    }

    graph = build_graph(parsed_project)
    report = analyze_graph(graph)

    style = report["architecture"]["detectedStyle"]
    assert style["name"] == "microservice_like"
    assert style["confidence"] >= 0.8


def test_analyze_graph_reports_allow_only_rule_violations(
    make_parsed_file: ParsedFileFactory,
    make_dependency: DependencyFactory,
) -> None:
    parsed_project = {
        "projectRoot": "/workspace",
        "parsedFiles": [
            make_parsed_file(
                "src/controller/users.py",
                dependencies=[make_dependency("src/repository/users.py")],
            ),
            make_parsed_file("src/repository/users.py"),
        ],
    }

    graph = build_graph(parsed_project)
    report = analyze_graph(
        graph,
        allowed_rules=["controller -> service"],
    )

    assert report["architecture"]["activeRules"] == {
        "forbid": [],
        "allow": ["controller -> service"],
    }
    violation = report["architecture"]["ruleViolations"][0]
    assert violation["kind"] == "allow"
    assert violation["source"] == "src/controller/users.py"
    assert violation["target"] == "src/repository/users.py"
    assert violation["allowedTargets"] == ["service"]
    assert violation["rule"] == "controller -> service"
