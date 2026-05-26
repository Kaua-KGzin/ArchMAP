"""Tests for the MCP server (archmap mcp command)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from archmap.cli.mcp_server import _dispatch, _tool_get_architecture_summary, _tool_get_file_context, _tool_impact_analysis, _tool_run_checks


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FAKE_METRICS = {
    "filesAnalyzed": 10,
    "totalDependencies": 25,
    "circularDependencyCount": 1,
    "architectureHealthScore": 72,
    "resolutionRate": 0.95,
}

_FAKE_RISKS = {
    "god_modules": [{"file": "src/core.py", "outgoing": 20}],
    "layer_violations": [],
    "dependency_explosions": [],
    "top_risk_files": [{"file": "src/core.py", "riskScore": 50}],
}

_FAKE_NODES = [
    {
        "id": "src/app.py",
        "label": "src/app.py",
        "type": "file",
        "language": "python",
        "folder": "src",
        "outgoing": 3,
        "incoming": 1,
        "isCircular": False,
        "complexityScore": 5.0,
        "instability": 0.75,
        "impact": {"nodeId": "src/app.py", "impactedFiles": ["src/main.py"], "impactCount": 1, "risk": "ok"},
    },
    {
        "id": "src/main.py",
        "label": "src/main.py",
        "type": "file",
        "language": "python",
        "folder": "src",
        "outgoing": 1,
        "incoming": 0,
        "isCircular": False,
        "complexityScore": 1.0,
        "instability": 1.0,
        "impact": {"nodeId": "src/main.py", "impactedFiles": [], "impactCount": 0, "risk": "low"},
    },
]

_FAKE_EDGES = [
    {"id": "e1", "source": "src/main.py", "target": "src/app.py", "isCircular": False},
    {"id": "e2", "source": "src/app.py", "target": "src/utils.py", "isCircular": False},
]

_FAKE_CYCLES = [["src/a.py", "src/b.py"]]

_FAKE_RESULT: dict[str, Any] = {
    "metrics": _FAKE_METRICS,
    "risks": _FAKE_RISKS,
    "nodes": _FAKE_NODES,
    "edges": _FAKE_EDGES,
    "cycles": _FAKE_CYCLES,
}


@pytest.fixture()
def mock_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "archmap.cli.mcp_server._get_analysis",
        lambda _path: _FAKE_RESULT,
    )


# ---------------------------------------------------------------------------
# Tool tests
# ---------------------------------------------------------------------------

def test_get_architecture_summary(mock_analysis: None) -> None:
    result = _tool_get_architecture_summary("/fake/project")
    assert result["healthScore"] == 72
    assert result["totalFiles"] == 10
    assert result["totalEdges"] == 25
    assert result["cycleCount"] == 1
    assert result["godModules"] == 1
    assert result["layerViolations"] == 0
    assert result["resolutionRate"] == pytest.approx(0.95)
    assert "treeSitterAvailable" in result
    assert result["parserPrecision"] in ("symbol", "file")


def test_get_file_context_found(mock_analysis: None) -> None:
    result = _tool_get_file_context("/fake/project", "src/app.py")
    assert result["file"] == "src/app.py"
    assert "src/utils.py" in result["outgoing"]
    assert "src/main.py" in result["incoming"]
    assert result["incomingCount"] == 1
    assert result["outgoingCount"] == 1


def test_get_file_context_not_found(mock_analysis: None) -> None:
    result = _tool_get_file_context("/fake/project", "nonexistent.py")
    assert "error" in result


def test_get_file_context_fuzzy_match(mock_analysis: None) -> None:
    result = _tool_get_file_context("/fake/project", "app.py")
    assert result["file"] == "src/app.py"


def test_impact_analysis_found(mock_analysis: None) -> None:
    result = _tool_impact_analysis("/fake/project", "src/app.py")
    assert result["file"] == "src/app.py"
    assert "impactedFiles" in result
    assert "impactCount" in result
    assert result["risk"] in ("low", "ok", "warning", "critical")


def test_impact_analysis_not_found(mock_analysis: None) -> None:
    result = _tool_impact_analysis("/fake/project", "ghost.py")
    assert "error" in result


def test_run_checks_with_issues(mock_analysis: None) -> None:
    result = _tool_run_checks("/fake/project")
    assert result["passed"] is False
    assert result["cycleCount"] == 1
    assert result["godModuleCount"] == 1
    assert result["layerViolationCount"] == 0
    assert result["healthScore"] == 72


# ---------------------------------------------------------------------------
# Dispatch / protocol tests
# ---------------------------------------------------------------------------

def test_dispatch_initialize() -> None:
    msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    resp = _dispatch(msg, "/fake")
    assert resp is not None
    assert resp["result"]["protocolVersion"] == "2024-11-05"
    assert resp["result"]["serverInfo"]["name"] == "archmap"


def test_dispatch_tools_list() -> None:
    msg = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    resp = _dispatch(msg, "/fake")
    assert resp is not None
    tools = resp["result"]["tools"]
    names = [t["name"] for t in tools]
    assert "get_architecture_summary" in names
    assert "get_file_context" in names
    assert "impact_analysis" in names
    assert "run_checks" in names


def test_dispatch_unknown_method() -> None:
    msg = {"jsonrpc": "2.0", "id": 3, "method": "unknown/method", "params": {}}
    resp = _dispatch(msg, "/fake")
    assert resp is not None
    assert "error" in resp
    assert resp["error"]["code"] == -32601


def test_dispatch_notification_no_response() -> None:
    msg = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    resp = _dispatch(msg, "/fake")
    assert resp is None


def test_dispatch_tools_call_missing_file() -> None:
    msg = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"name": "get_file_context", "arguments": {}},
    }
    resp = _dispatch(msg, "/fake")
    assert resp is not None
    assert "error" in resp
    assert resp["error"]["code"] == -32602


def test_dispatch_tools_call_unknown_tool() -> None:
    msg = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": "does_not_exist", "arguments": {}},
    }
    resp = _dispatch(msg, "/fake")
    assert resp is not None
    assert "error" in resp
    assert resp["error"]["code"] == -32601


def test_dispatch_tools_call_summary(mock_analysis: None) -> None:
    msg = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {"name": "get_architecture_summary", "arguments": {}},
    }
    resp = _dispatch(msg, "/fake/project")
    assert resp is not None
    content = resp["result"]["content"]
    assert len(content) == 1
    data = json.loads(content[0]["text"])
    assert data["healthScore"] == 72
