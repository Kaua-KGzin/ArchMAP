"""Tests for human_analyzer and project_explainer coverage."""
from __future__ import annotations

from archmap.core.analyzer.human_analyzer import analyze_human
from archmap.core.analyzer.project_explainer import explain_project

# --- human_analyzer ---

def test_analyze_human_ok() -> None:
    report = {
        "metrics": {},
        "architecture": {"health": {"score": 85}},
        "cycles": [],
        "risks": {
            "god_modules": [],
            "layer_violations": [],
            "dependency_explosions": [],
        },
    }

    result = analyze_human(report)
    assert result["status"] == "ok"
    assert result["score"] == 85


def test_analyze_human_warning() -> None:
    report = {
        "metrics": {},
        "architecture": {"health": {"score": 55}},
        "cycles": [],
        "risks": {
            "god_modules": [],
            "layer_violations": [],
            "dependency_explosions": [],
        },
    }

    result = analyze_human(report)
    assert result["status"] == "warning"


def test_analyze_human_critical() -> None:
    report = {
        "metrics": {},
        "architecture": {"health": {"score": 30}},
        "cycles": [],
        "risks": {
            "god_modules": [],
            "layer_violations": [],
            "dependency_explosions": [],
        },
    }

    result = analyze_human(report)
    assert result["status"] == "critical"


def test_analyze_human_with_cycles() -> None:
    report = {
        "metrics": {},
        "architecture": {"health": {"score": 50}},
        "cycles": [["a.py", "b.py"]],
        "risks": {
            "god_modules": [],
            "layer_violations": [],
            "dependency_explosions": [],
        },
    }

    result = analyze_human(report)
    assert any("círculo" in p for p in result["problems"])


def test_analyze_human_with_god_modules() -> None:
    report = {
        "metrics": {},
        "architecture": {"health": {"score": 60}},
        "cycles": [],
        "risks": {
            "god_modules": [{"file": "big_file.py", "outgoing": 30}],
            "layer_violations": [],
            "dependency_explosions": [],
        },
    }

    result = analyze_human(report)
    assert any("divindades" in p for p in result["problems"])
    assert any("big_file" in a for a in result["actions"])


def test_analyze_human_with_layer_violations() -> None:
    report = {
        "metrics": {},
        "architecture": {"health": {"score": 60}},
        "cycles": [],
        "risks": {
            "god_modules": [],
            "layer_violations": [{"source": "a", "target": "b"}],
            "dependency_explosions": [],
        },
    }

    result = analyze_human(report)
    assert any("camadas" in p for p in result["problems"])


def test_analyze_human_with_explosions() -> None:
    report = {
        "metrics": {},
        "architecture": {"health": {"score": 60}},
        "cycles": [],
        "risks": {
            "god_modules": [],
            "layer_violations": [],
            "dependency_explosions": [{"file": "hub.py"}],
        },
    }

    result = analyze_human(report)
    assert any("quase tudo" in p for p in result["problems"])


# --- project_explainer ---

def test_explain_project_api_layered() -> None:
    nodes = [
        {"type": "file", "folder": "controllers/users"},
        {"type": "file", "folder": "services/auth"},
        {"type": "file", "folder": "models/user"},
    ]
    edges = []

    result = explain_project(nodes, edges)
    assert result["architecture"] == "Modular API (Layered)"
    assert result["patterns"]["api"] is True
    assert result["patterns"]["logic"] is True
    assert result["patterns"]["database"] is True


def test_explain_project_web_app() -> None:
    nodes = [
        {"type": "file", "folder": "components/header"},
        {"type": "file", "folder": "templates/index"},
    ]
    edges = []

    result = explain_project(nodes, edges)
    assert result["architecture"] == "Web Application"
    assert result["patterns"]["ui"] is True


def test_explain_project_cli_tool() -> None:
    nodes = [
        {"type": "file", "folder": "cli/main"},
        {"type": "file", "folder": "commands/run"},
    ]
    edges = []

    result = explain_project(nodes, edges)
    assert result["architecture"] == "CLI Tool"
    assert result["patterns"]["cli"] is True


def test_explain_project_domain_driven() -> None:
    nodes = [
        {"type": "file", "folder": "core/engine"},
        {"type": "file", "folder": "utils/helpers"},
    ]
    edges = []

    result = explain_project(nodes, edges)
    assert result["architecture"] == "Domain-Driven / Clean Architecture"


def test_explain_project_general() -> None:
    nodes = [
        {"type": "file", "folder": "src/main"},
        {"type": "file", "folder": "lib/stuff"},
    ]
    edges = []

    result = explain_project(nodes, edges)
    assert result["architecture"] == "General Project"


def test_explain_project_empty() -> None:
    result = explain_project([], [])
    assert result["architecture"] == "General Project"
    assert result["simple"]
    assert result["technical"]


def test_explain_project_technical_with_known_folders() -> None:
    nodes = [
        {"type": "file", "folder": "controllers/api"},
        {"type": "file", "folder": "services/auth"},
        {"type": "file", "folder": "utils/helpers"},
        {"type": "file", "folder": "cli/main"},
    ]
    edges = []

    result = explain_project(nodes, edges)
    assert "controllers" in result["technical"] or "cli" in result["technical"]
