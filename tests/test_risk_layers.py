from __future__ import annotations

from collections.abc import Callable

from archmap.core.analyzer.risk_analyzer import detect_architectural_risks

NodeFactory = Callable[..., dict]
EdgeFactory = Callable[..., dict]


def test_layer_violations_detected_with_src_prefix_paths(
    make_file_node: NodeFactory,
    make_edge: EdgeFactory,
) -> None:
    nodes = [
        make_file_node("src/core/service.py", outgoing=1),
        make_file_node("src/cli/main.py", incoming=1),
    ]
    edges = [make_edge("src/core/service.py", "src/cli/main.py")]

    risks = detect_architectural_risks(nodes, edges, cycles=[])

    assert len(risks["layer_violations"]) == 1
    violation = risks["layer_violations"][0]
    assert violation["sourceLayer"] == "core"
    assert violation["targetLayer"] == "cli"


def test_same_layer_dependency_is_not_a_violation(
    make_file_node: NodeFactory,
    make_edge: EdgeFactory,
) -> None:
    nodes = [
        make_file_node("src/core/a.py", outgoing=1),
        make_file_node("src/core/b.py", incoming=1),
    ]
    edges = [make_edge("src/core/a.py", "src/core/b.py")]

    risks = detect_architectural_risks(nodes, edges, cycles=[])

    assert risks["layer_violations"] == []


def test_detect_architectural_risks_returns_empty_results_without_file_nodes() -> None:
    risks = detect_architectural_risks(nodes=[], edges=[], cycles=[], layer_order={"platform": 6})

    assert risks["god_modules"] == []
    assert risks["dependency_explosions"] == []
    assert risks["layer_violations"] == []
    assert risks["top_risk_files"] == []
    assert risks["thresholds"] == {
        "god_module_min_outgoing": 8,
        "dependency_explosion_min_connections": 12,
    }


def test_custom_layer_order_parameter_supports_new_layers(
    make_file_node: NodeFactory,
    make_edge: EdgeFactory,
) -> None:
    nodes = [
        make_file_node("src/domain/service.py", outgoing=1),
        make_file_node("src/platform/http.py", incoming=1),
    ]
    edges = [make_edge("src/domain/service.py", "src/platform/http.py")]

    default_risks = detect_architectural_risks(nodes, edges, cycles=[])
    custom_risks = detect_architectural_risks(
        nodes,
        edges,
        cycles=[],
        layer_order={"platform": 6, "domain": 3},
    )

    assert default_risks["layer_violations"] == []
    assert custom_risks["layer_violations"] == [
        {
            "source": "src/domain/service.py",
            "target": "src/platform/http.py",
            "sourceLayer": "domain",
            "targetLayer": "platform",
            "rule": "lower-level module should not depend on higher-level module",
        }
    ]


def test_top_risk_score_combines_cycle_thresholds_and_layer_violations(
    make_file_node: NodeFactory,
    make_edge: EdgeFactory,
) -> None:
    nodes = [
        make_file_node("src/core/service.py", incoming=3, outgoing=9),
        make_file_node("src/core/helper.py"),
        make_file_node("src/cli/main.py", incoming=1),
    ]
    edges = [make_edge("src/core/service.py", "src/cli/main.py")]

    risks = detect_architectural_risks(
        nodes,
        edges,
        cycles=[["src/core/service.py", "src/core/helper.py"]],
    )

    assert risks["god_modules"] == [{"file": "src/core/service.py", "outgoing": 9}]
    assert risks["dependency_explosions"] == [
        {
            "file": "src/core/service.py",
            "incoming": 3,
            "outgoing": 9,
            "totalConnections": 12,
        }
    ]
    assert risks["thresholds"] == {
        "god_module_min_outgoing": 9,
        "dependency_explosion_min_connections": 12,
    }
    assert risks["top_risk_files"][0] == {
        "file": "src/core/service.py",
        "riskScore": 43,
        "dependents": 3,
        "outgoing": 9,
        "signals": [
            "circular_dependency",
            "god_module",
            "dependency_explosion",
            "layer_violations:1",
        ],
    }
