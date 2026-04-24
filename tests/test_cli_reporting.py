from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from archmap.cli import reporting


def test_export_outputs_writes_requested_formats(monkeypatch, tmp_path) -> None:
    calls: list[tuple[str, str]] = []

    def fake_json_export(report: dict, output: str) -> Path:
        assert report == {"graph": True}
        calls.append(("json", output))
        return Path(output)

    def fake_mermaid_export(report: dict, output: str) -> Path:
        assert report == {"graph": True}
        calls.append(("mermaid", output))
        return Path(output)

    def fake_cytoscape_export(report: dict, output: str) -> Path:
        assert report == {"graph": True}
        calls.append(("cytoscape", output))
        return Path(output)

    monkeypatch.setattr(reporting, "export_graph_as_json", fake_json_export)
    monkeypatch.setattr(reporting, "export_graph_as_mermaid", fake_mermaid_export)
    monkeypatch.setattr(reporting, "export_graph_as_cytoscape", fake_cytoscape_export)

    result = reporting.export_outputs(
        report={"graph": True},
        output_format="both",
        json_output=str(tmp_path / "graph.json"),
        mermaid_output=str(tmp_path / "graph.mmd"),
        cytoscape_output=str(tmp_path / "graph-cytoscape.json"),
        include_cytoscape=True,
    )

    assert result == {
        "jsonPath": str(tmp_path / "graph.json"),
        "mermaidPath": str(tmp_path / "graph.mmd"),
        "cytoscapePath": str(tmp_path / "graph-cytoscape.json"),
    }
    assert calls == [
        ("json", str(tmp_path / "graph.json")),
        ("mermaid", str(tmp_path / "graph.mmd")),
        ("cytoscape", str(tmp_path / "graph-cytoscape.json")),
    ]


def test_print_helpers_render_terminal_summary(capsys) -> None:
    report = {
        "metrics": {
            "filesAnalyzed": 7,
            "totalDependencies": 12,
            "circularDependencyCount": 1,
            "architectureHealthScore": 72,
            "architectureStyle": "modular_monolith",
            "coupling": {"averageInstability": 0.52},
            "complexity": [
                {
                    "file": "app.py",
                    "imports": 9,
                    "dependents": 6,
                    "totalConnections": 15,
                    "efferentCoupling": 9,
                    "afferentCoupling": 6,
                    "instability": 0.6,
                    "score": 0.83,
                },
                {
                    "file": "db.py",
                    "imports": 4,
                    "dependents": 2,
                    "totalConnections": 6,
                    "efferentCoupling": 4,
                    "afferentCoupling": 2,
                    "instability": 0.67,
                    "score": 0.42,
                },
            ],
        },
        "risks": {
            "top_risk_files": [
                {"file": "app.py", "riskScore": 91, "signals": ["cycle", "god-module"]},
                {"file": "db.py", "riskScore": 40, "signals": []},
            ]
        },
        "architecture": {
            "detectedStyle": {"name": "modular_monolith", "confidence": 0.72},
            "ruleViolations": [{"rule": "controller -> repository"}],
            "activeRules": {"forbid": ["controller -> repository"], "allow": []},
            "health": {"score": 72, "grade": "C"},
        }
    }

    reporting.print_summary(report)
    reporting.print_top_complexity(report, 2)
    reporting.print_top_risks(report, 2)
    reporting.print_export_summary(
        {
            "jsonPath": "out.json",
            "mermaidPath": "out.mmd",
            "cytoscapePath": "out-cytoscape.json",
        }
    )

    output = capsys.readouterr().out
    assert "[ok] 7 files analyzed" in output
    assert "[ok] 12 dependencies detected" in output
    assert "[ok] 1 circular dependencies detected" in output
    assert "[ok] Average instability 52%" in output
    assert "[ok] Architecture health 72/100 (C)" in output
    assert "[ok] Detected style: modular_monolith (72% confidence)" in output
    assert "[ok] 1 custom architecture rules configured" in output
    assert "[warn] 1 custom architecture rule violations detected" in output
    assert "Top complexity (imports/dependents):" in output
    assert "app.py: 9 imports, 6 dependents, 15 total, 60% instability (83% score)" in output
    assert "Top risk files:" in output
    assert "app.py: score 91 (cycle, god-module)" in output
    assert "db.py: score 40 (none)" in output
    assert "[info] JSON report exported to out.json" in output
    assert "[info] Mermaid graph exported to out.mmd" in output
    assert "[info] Cytoscape data exported to out-cytoscape.json" in output


def test_print_history_output_renders_timeline_and_culprits(capsys) -> None:
    history = {
        "ref": "HEAD",
        "windowSize": 2,
        "snapshots": [
            {
                "commit": "abc123",
                "shortCommit": "abc123",
                "subject": "base",
                "dependencies": 4,
                "cycles": 0,
                "health": 90,
                "style": "monolith",
                "ruleViolations": 0,
            },
            {
                "commit": "def456",
                "shortCommit": "def456",
                "subject": "head",
                "dependencies": 7,
                "cycles": 1,
                "health": 72,
                "style": "modular_monolith",
                "ruleViolations": 2,
            },
        ],
        "trend": {
            "healthDelta": -18,
            "cycleDelta": 1,
            "dependencyDelta": 3,
            "ruleViolationsDelta": 2,
            "complexityDeltaPercent": 10.0,
            "instabilityDeltaPercent": 5.5,
            "fromStyle": "monolith",
            "toStyle": "modular_monolith",
            "styleChanged": True,
        },
        "cycles": [
            {
                "cycle": ["a.py", "b.py"],
                "introducedIn": {"shortCommit": "def456", "subject": "head"},
                "suspectedOwner": {
                    "author": "ArchMAP Test",
                    "file": "b.py",
                    "shortCommit": "def456",
                },
            }
        ],
        "hotspots": [
            {
                "file": "a.py",
                "riskScore": 91,
                "signals": ["cycle"],
                "lastTouched": {"author": "ArchMAP Test", "shortCommit": "def456"},
            }
        ],
    }

    reporting.print_history_output(history)

    output = capsys.readouterr().out
    assert "History window: 2 snapshot(s) from HEAD" in output
    assert "Health 90 -> 72 (-18)" in output
    assert "Cycles 0 -> 1 (+1)" in output
    assert "Dependencies 4 -> 7 (+3)" in output
    assert "Style monolith -> modular_monolith" in output
    assert "Current cycle origins:" in output
    assert "introduced in def456 (head)" in output
    assert "last touched by ArchMAP Test on b.py [def456]" in output
    assert "Architectural hotspots:" in output
    assert "a.py: score 91 (cycle)" in output


def test_print_helpers_skip_empty_sections(capsys) -> None:
    report = {
        "metrics": {
            "filesAnalyzed": 1,
            "totalDependencies": 0,
            "circularDependencyCount": 0,
            "complexity": [],
        },
        "risks": {"top_risk_files": []},
    }

    reporting.print_top_complexity(report, 0)
    reporting.print_top_complexity(report, 5)
    reporting.print_top_risks(report, 0)
    reporting.print_top_risks(report, 5)
    reporting.print_export_summary(
        {"jsonPath": None, "mermaidPath": None, "cytoscapePath": None}
    )

    assert capsys.readouterr().out == ""


def test_print_diff_output_as_json(capsys) -> None:
    diff_result = {
        "edges": {"delta": 0},
        "cycles": {"delta": 0},
        "complexity": {"deltaPercent": 0.0},
        "files": {"delta": 0, "added": [], "removed": [], "changed": []},
        "riskSummary": {
            "layerViolationsDelta": 0,
            "godModulesDelta": 0,
            "dependencyExplosionsDelta": 0,
        },
    }

    reporting.print_diff_output("main", "feature", diff_result, as_json=True)

    output = capsys.readouterr().out
    assert json.loads(output) == diff_result


def test_format_diff_output_renders_top_changed_files() -> None:
    diff_result = {
        "edges": {"delta": 3},
        "cycles": {"delta": -1},
        "complexity": {"deltaPercent": 12.5},
        "architecture": {
            "healthDelta": -7,
            "ruleViolationsDelta": 2,
            "styleChanged": True,
            "baseStyle": "monolith",
            "headStyle": "modular_monolith",
        },
        "files": {
            "delta": 1,
            "added": ["new.py"],
            "removed": [],
            "changed": [
                {
                    "file": "src/app.py",
                    "outgoingDelta": 2,
                    "incomingDelta": -1,
                    "totalConnectionsDelta": 1,
                    "complexityDelta": 0.125,
                    "riskScoreDelta": 4,
                    "addedDependencies": ["pkg:requests"],
                    "removedDependencies": [],
                }
            ],
        },
        "riskSummary": {
            "layerViolationsDelta": 2,
            "godModulesDelta": 0,
            "dependencyExplosionsDelta": -4,
        },
    }

    output = reporting.format_diff_output("main", "feature", diff_result)

    assert output.splitlines() == [
        "Comparing main -> feature",
        "+3 dependencies",
        "-1 circular dependencies",
        "complexity +12.50%",
        "health -7",
        "+2 layer violations",
        "+0 god modules",
        "-4 dependency explosions",
        "+2 custom rule violations",
        "style monolith -> modular_monolith",
        "+1 files",
        "Top file deltas:",
        "  - src/app.py: out +2, in -1, complexity +12.50%, risk +4",
    ]


def test_evaluate_quality_gates_returns_empty_when_disabled() -> None:
    report = {"metrics": {}, "risks": {}, "architecture": {}}
    args = Namespace(
        fail_on_cycles=False,
        fail_on_layer_violations=False,
        fail_on_god_modules=False,
        fail_on_dependency_explosions=False,
        fail_on_custom_rules=False,
        fail_on_risks=False,
        min_health=None,
    )

    assert reporting.evaluate_quality_gates(report, args) == []


def test_evaluate_quality_gates_triggers_cycle_gate() -> None:
    report = {
        "metrics": {"circularDependencyCount": 2},
        "risks": {},
        "architecture": {},
    }
    args = Namespace(
        fail_on_cycles=True,
        fail_on_layer_violations=False,
        fail_on_god_modules=False,
        fail_on_dependency_explosions=False,
        fail_on_custom_rules=False,
        fail_on_risks=False,
        min_health=None,
    )

    failures = reporting.evaluate_quality_gates(report, args)
    assert len(failures) == 1
    assert "cycle gate" in failures[0]
    assert "2" in failures[0]


def test_evaluate_quality_gates_triggers_min_health_gate() -> None:
    report = {
        "metrics": {},
        "risks": {},
        "architecture": {"health": {"score": 55}},
    }
    args = Namespace(
        fail_on_cycles=False,
        fail_on_layer_violations=False,
        fail_on_god_modules=False,
        fail_on_dependency_explosions=False,
        fail_on_custom_rules=False,
        fail_on_risks=False,
        min_health=70,
    )

    failures = reporting.evaluate_quality_gates(report, args)
    assert len(failures) == 1
    assert "health gate" in failures[0]
    assert "55" in failures[0]
    assert "70" in failures[0]


def test_evaluate_quality_gates_triggers_fail_on_risks_gate() -> None:
    report = {
        "metrics": {"circularDependencyCount": 1},
        "risks": {
            "layer_violations": [{"rule": "a -> b"}],
            "god_modules": [],
            "dependency_explosions": [],
        },
        "architecture": {"ruleViolations": []},
    }
    args = Namespace(
        fail_on_cycles=False,
        fail_on_layer_violations=False,
        fail_on_god_modules=False,
        fail_on_dependency_explosions=False,
        fail_on_custom_rules=False,
        fail_on_risks=True,
        min_health=None,
    )

    failures = reporting.evaluate_quality_gates(report, args)
    assert len(failures) == 1
    assert "risk gate" in failures[0]


def test_print_human_insights_renders_problems_and_actions(capsys) -> None:
    report = {
        "insights": {
            "status": "warning",
            "message": "Architecture needs attention",
            "problems": ["Circular dependency in auth"],
            "actions": ["Extract shared types to break cycle"],
        }
    }

    reporting.print_human_insights(report)

    output = capsys.readouterr().out
    assert "[insight] Architectural reading" in output
    assert "Status: WARNING" in output
    assert "Circular dependency in auth" in output
    assert "Extract shared types to break cycle" in output


def test_print_human_insights_skips_empty_report(capsys) -> None:
    reporting.print_human_insights({})
    assert capsys.readouterr().out == ""


def test_print_project_explanation_renders_content(capsys) -> None:
    report = {
        "explanation": {
            "architecture": "Layered",
            "simple": "Three layers: api, services, core",
            "technical": "api -> services -> core with no back-edges",
        }
    }

    reporting.print_project_explanation(report)

    output = capsys.readouterr().out
    assert "[explain] Project summary" in output
    assert "Layered" in output
    assert "Three layers" in output
    assert "Technical view:" in output


def test_print_impact_analysis_no_downstream(capsys) -> None:
    report = {
        "nodes": [
            {
                "id": "src/leaf.py",
                "impact": {"impactedFiles": [], "impactCount": 0, "risk": "low"},
            }
        ]
    }

    reporting.print_impact_analysis(report, "src/leaf.py")

    output = capsys.readouterr().out
    assert "No downstream files" in output


def test_print_impact_analysis_file_not_found(capsys) -> None:
    reporting.print_impact_analysis({"nodes": []}, "missing.py")

    output = capsys.readouterr().out
    assert "[error]" in output
    assert "missing.py" in output


def test_print_risk_report_renders_payload(capsys) -> None:
    payload = {
        "file": "src/auth.py",
        "riskScore": 88,
        "signals": ["cycle", "god-module"],
        "incoming": 5,
        "outgoing": 7,
        "impact": {"impactCount": 3, "impactedFiles": ["a.py", "b.py", "c.py"]},
    }

    reporting.print_risk_report(payload, max_impacted=5)

    output = capsys.readouterr().out
    assert "[risk] src/auth.py" in output
    assert "Risk score: 88" in output
    assert "cycle, god-module" in output
    assert "Incoming dependencies: 5" in output
    assert "Outgoing dependencies: 7" in output
    assert "a.py" in output


def test_print_improve_report_renders_groups_and_moves(capsys) -> None:
    suggestions = {
        "summary": "2 groups suggested",
        "groups": [{"name": "auth", "count": 3}],
        "moves": [
            {"source": "src/a.py", "target": "auth/a.py"},
        ],
    }

    reporting.print_improve_report(suggestions)

    output = capsys.readouterr().out
    assert "[improve] Automatic architecture suggestions" in output
    assert "/auth (3 file(s))" in output
    assert "src/a.py -> auth/a.py" in output


def test_export_outputs_json_only(monkeypatch) -> None:
    from pathlib import Path as _Path

    exported: list[str] = []
    monkeypatch.setattr(
        reporting,
        "export_graph_as_json",
        lambda r, o: exported.append("json") or _Path(o),
    )

    result = reporting.export_outputs(
        report={"graph": True},
        output_format="json",
        json_output="out.json",
        mermaid_output="out.mmd",
        cytoscape_output="out-cytoscape.json",
        include_cytoscape=False,
    )

    assert result["jsonPath"] == "out.json"
    assert result["mermaidPath"] is None
    assert result["cytoscapePath"] is None
    assert exported == ["json"]


def test_export_outputs_mermaid_no_subgraphs(monkeypatch) -> None:
    captured: list[dict] = []

    def fake_mermaid(report, output, **kwargs):
        captured.append(kwargs)
        return __import__("pathlib").Path(output)

    monkeypatch.setattr(reporting, "export_graph_as_mermaid", fake_mermaid)

    reporting.export_outputs(
        report={},
        output_format="mermaid",
        json_output="out.json",
        mermaid_output="out.mmd",
        cytoscape_output="out-cytoscape.json",
        include_cytoscape=False,
        no_subgraphs=True,
    )

    assert captured[0].get("no_subgraphs") is True
