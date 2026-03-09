from __future__ import annotations

from archmap.core.analyzer.dependency_graph import analyze_graph
from archmap.core.graph.graph_builder import build_graph


def test_analyzer_computes_cycles_complexity_and_critical_files() -> None:
    parsed_project = {
        "projectRoot": "/workspace",
        "parsedFiles": [
            {
                "id": "a.py",
                "label": "a.py",
                "language": "python",
                "dependencies": [
                    {"id": "b.py", "label": "b.py", "type": "file"},
                    {"id": "pkg:requests", "label": "requests", "type": "package"},
                ],
            },
            {
                "id": "b.py",
                "label": "b.py",
                "language": "python",
                "dependencies": [{"id": "a.py", "label": "a.py", "type": "file"}],
            },
            {
                "id": "c.py",
                "label": "c.py",
                "language": "python",
                "dependencies": [{"id": "a.py", "label": "a.py", "type": "file"}],
            },
        ],
    }

    graph = build_graph(parsed_project)
    report = analyze_graph(graph)

    assert report["metrics"]["filesAnalyzed"] == 3
    assert report["metrics"]["circularDependencyCount"] == 1
    assert report["cycles"] == [["a.py", "b.py"]]

    by_id = {node["id"]: node for node in report["nodes"]}
    assert by_id["a.py"]["complexityImports"] == 2
    assert by_id["a.py"]["complexityScore"] == 1.0
    assert by_id["b.py"]["complexityImports"] == 1
    assert by_id["c.py"]["complexityScore"] == 0.5

    most_critical = report["metrics"]["criticalFiles"][0]
    assert most_critical["file"] == "a.py"
    assert most_critical["dependents"] == 2

    assert report["risks"]["top_risk_files"]
