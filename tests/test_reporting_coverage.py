"""Tests for reporting.py - covering print functions, insights, explanations, etc."""
from __future__ import annotations

import json
from argparse import Namespace

from archmap.cli import reporting


def test_print_human_insights_full(capsys) -> None:
    report = {
        "insights": {
            "status": "warning",
            "message": "Complexity is rising.",
            "problems": ["Cycles detected", "God modules exist"],
            "actions": ["Break cycles", "Split large files"],
        }
    }

    reporting.print_human_insights(report)
    output = capsys.readouterr().out
    assert "[insight] Architectural reading" in output
    assert "WARNING" in output
    assert "Complexity is rising." in output
    assert "Cycles detected" in output
    assert "God modules exist" in output
    assert "Break cycles" in output
    assert "Split large files" in output


def test_print_human_insights_empty(capsys) -> None:
    reporting.print_human_insights({})
    assert capsys.readouterr().out == ""

    reporting.print_human_insights({"insights": None})
    assert capsys.readouterr().out == ""


def test_print_project_explanation_full(capsys) -> None:
    report = {
        "explanation": {
            "architecture": "CLI Tool",
            "simple": "This project is a command-line tool.",
            "technical": "The project is split into modules.",
        }
    }

    reporting.print_project_explanation(report)
    output = capsys.readouterr().out
    assert "[explain] Project summary" in output
    assert "Style: CLI Tool" in output
    assert "This project is a command-line tool." in output
    assert "Technical view:" in output
    assert "The project is split into modules." in output


def test_print_project_explanation_empty(capsys) -> None:
    reporting.print_project_explanation({})
    assert capsys.readouterr().out == ""


def test_print_project_explanation_no_technical(capsys) -> None:
    report = {
        "explanation": {
            "architecture": "General",
            "simple": "A project.",
            "technical": "",
        }
    }

    reporting.print_project_explanation(report)
    output = capsys.readouterr().out
    assert "Technical view:" not in output


def test_print_impact_analysis_full(capsys) -> None:
    report = {
        "nodes": [
            {
                "id": "src/app.py",
                "type": "file",
                "impact": {
                    "impactCount": 3,
                    "risk": "high",
                    "impactedFiles": ["a.py", "b.py", "c.py"],
                },
            }
        ]
    }

    reporting.print_impact_analysis(report, "src/app.py")
    output = capsys.readouterr().out
    assert "[risk] Impact analysis for src/app.py" in output
    assert "Change risk: HIGH" in output
    assert "Potentially impacted files: 3" in output
    assert "a.py" in output
    assert "b.py" in output


def test_print_impact_analysis_not_found(capsys) -> None:
    reporting.print_impact_analysis({"nodes": []}, "missing.py")
    output = capsys.readouterr().out
    assert "[error] File not found" in output


def test_print_impact_analysis_zero_impact(capsys) -> None:
    report = {
        "nodes": [
            {
                "id": "leaf.py",
                "type": "file",
                "impact": {
                    "impactCount": 0,
                    "risk": "low",
                    "impactedFiles": [],
                },
            }
        ]
    }

    reporting.print_impact_analysis(report, "leaf.py")
    output = capsys.readouterr().out
    assert "No downstream files were detected." in output


def test_print_impact_analysis_truncated(capsys) -> None:
    files = [f"file{i}.py" for i in range(20)]
    report = {
        "nodes": [
            {
                "id": "hub.py",
                "type": "file",
                "impact": {
                    "impactCount": 20,
                    "risk": "critical",
                    "impactedFiles": files,
                },
            }
        ]
    }

    reporting.print_impact_analysis(report, "hub.py", max_impacted=3)
    output = capsys.readouterr().out
    assert "... and 17 more files" in output


def test_print_risk_report(capsys) -> None:
    risk = {
        "file": "core/engine.py",
        "riskScore": 42,
        "signals": ["god_module", "circular_dependency"],
        "incoming": 8,
        "outgoing": 12,
        "impact": {
            "impactCount": 5,
            "impactedFiles": ["a.py", "b.py"],
        },
    }

    reporting.print_risk_report(risk, max_impacted=10)
    output = capsys.readouterr().out
    assert "[risk] core/engine.py" in output
    assert "Risk score: 42" in output
    assert "god_module, circular_dependency" in output
    assert "Incoming dependencies: 8" in output
    assert "Outgoing dependencies: 12" in output
    assert "Blast radius: 5 file(s)" in output


def test_print_simple_map_with_entries(capsys) -> None:
    simple_map = {
        "core": ["utils", "config"],
        "cli": [],
    }

    reporting.print_simple_map(simple_map)
    output = capsys.readouterr().out
    assert "[map] Simple architecture view" in output
    assert "core -> utils, config" in output
    assert "cli" in output


def test_print_simple_map_empty(capsys) -> None:
    reporting.print_simple_map({})
    output = capsys.readouterr().out
    assert "No cross-group dependencies detected." in output


def test_print_improve_report(capsys) -> None:
    suggestions = {
        "summary": "Project can be reorganized into 3 groups.",
        "groups": [
            {"name": "core", "count": 5},
            {"name": "utils", "count": 3},
        ],
        "moves": [
            {"source": "old/a.py", "target": "core/a.py"},
            {"source": "old/b.py", "target": "utils/b.py"},
        ],
    }

    reporting.print_improve_report(suggestions)
    output = capsys.readouterr().out
    assert "[improve] Automatic architecture suggestions" in output
    assert "Project can be reorganized into 3 groups." in output
    assert "/core (5 file(s))" in output
    assert "/utils (3 file(s))" in output
    assert "old/a.py -> core/a.py" in output


def test_print_improve_report_many_moves(capsys) -> None:
    suggestions = {
        "summary": "Big refactor.",
        "groups": [],
        "moves": [{"source": f"s{i}.py", "target": f"t{i}.py"} for i in range(15)],
    }

    reporting.print_improve_report(suggestions)
    output = capsys.readouterr().out
    assert "... and 3 more moves" in output


def test_evaluate_quality_gates_all_failing() -> None:
    report = {
        "metrics": {"circularDependencyCount": 2},
        "risks": {
            "layer_violations": [{"rule": "x"}],
            "god_modules": [{"file": "x"}],
            "dependency_explosions": [{"file": "x"}],
        },
        "architecture": {
            "ruleViolations": [{"rule": "a -> b"}],
            "health": {"score": 40},
        },
    }
    args = Namespace(
        fail_on_cycles=True,
        fail_on_layer_violations=True,
        fail_on_god_modules=True,
        fail_on_dependency_explosions=True,
        fail_on_custom_rules=True,
        fail_on_risks=True,
        min_health=60,
    )

    failures = reporting.evaluate_quality_gates(report, args)
    assert len(failures) >= 6
    assert any("cycle" in f for f in failures)
    assert any("layer" in f for f in failures)
    assert any("god" in f for f in failures)
    assert any("explosion" in f for f in failures)
    assert any("custom-rule" in f for f in failures)
    assert any("health" in f for f in failures)


def test_print_history_output_as_json(capsys) -> None:
    history = {"snapshots": [], "trend": {}}
    reporting.print_history_output(history, as_json=True)
    output = capsys.readouterr().out
    assert json.loads(output) == history


def test_print_diff_output_text(capsys) -> None:
    diff_result = {
        "edges": {"delta": 2},
        "cycles": {"delta": 0},
        "complexity": {"deltaPercent": 5.0},
        "files": {"delta": 0, "added": [], "removed": [], "changed": []},
        "riskSummary": {
            "layerViolationsDelta": 0,
            "godModulesDelta": 0,
            "dependencyExplosionsDelta": 0,
        },
    }

    reporting.print_diff_output("a", "b", diff_result, as_json=False)
    output = capsys.readouterr().out
    assert "Comparing a -> b" in output
    assert "+2 dependencies" in output


def test_signed_helpers() -> None:
    assert reporting.signed(5) == "+5"
    assert reporting.signed(-3) == "-3"
    assert reporting.signed(0) == "+0"
    assert reporting.signed_float(1.5) == "+1.50"
    assert reporting.signed_float(-0.5) == "-0.50"
