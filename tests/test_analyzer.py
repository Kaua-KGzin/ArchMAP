from __future__ import annotations

from collections.abc import Callable

from archmap.core.analyzer.dependency_graph import analyze_graph
from archmap.core.graph.graph_builder import build_graph

ParsedFileFactory = Callable[..., dict]
DependencyFactory = Callable[..., dict]


def test_analyzer_computes_cycles_complexity_and_critical_files(
    make_parsed_file: ParsedFileFactory,
    make_dependency: DependencyFactory,
) -> None:
    parsed_project = {
        "projectRoot": "/workspace",
        "parsedFiles": [
            make_parsed_file(
                "a.py",
                dependencies=[
                    make_dependency("b.py"),
                    make_dependency("pkg:requests"),
                ],
            ),
            make_parsed_file("b.py", dependencies=[make_dependency("a.py")]),
            make_parsed_file("c.py", dependencies=[make_dependency("a.py")]),
        ],
    }

    graph = build_graph(parsed_project)
    report = analyze_graph(graph)

    assert report["metrics"]["filesAnalyzed"] == 3
    assert report["metrics"]["circularDependencyCount"] == 1
    assert report["cycles"] == [["a.py", "b.py"]]

    by_id = {node["id"]: node for node in report["nodes"]}
    assert by_id["a.py"]["complexityImports"] == 2
    assert by_id["a.py"]["complexityDependents"] == 2
    assert by_id["a.py"]["complexityConnections"] == 4
    assert by_id["a.py"]["complexityScore"] == 1.0
    assert by_id["a.py"]["efferentCoupling"] == 2
    assert by_id["a.py"]["afferentCoupling"] == 2
    assert by_id["a.py"]["instability"] == 0.5
    assert by_id["b.py"]["complexityDependents"] == 1
    assert by_id["b.py"]["complexityImports"] == 1
    assert by_id["b.py"]["complexityScore"] == 0.5
    assert by_id["c.py"]["complexityConnections"] == 1
    assert by_id["c.py"]["complexityScore"] == 0.25

    most_critical = report["metrics"]["criticalFiles"][0]
    assert most_critical["file"] == "a.py"
    assert most_critical["dependents"] == 2
    top_complexity = report["metrics"]["complexity"][0]
    assert top_complexity == {
        "file": "a.py",
        "imports": 2,
        "dependents": 2,
        "totalConnections": 4,
        "efferentCoupling": 2,
        "afferentCoupling": 2,
        "instability": 0.5,
        "score": 1.0,
    }
    assert report["metrics"]["coupling"]["averageInstability"] == 0.666667
    assert report["metrics"]["coupling"]["mostStable"][0]["file"] == "a.py"
    assert report["metrics"]["coupling"]["mostVolatile"][0]["file"] == "c.py"

    assert report["metrics"]["architectureHealthScore"] == 88
    assert report["metrics"]["architectureStyle"] == "monolith"
    assert report["metrics"]["architectureRuleViolations"] == 0
    assert report["architecture"]["detectedStyle"]["name"] == "monolith"

    assert report["risks"]["top_risk_files"]
