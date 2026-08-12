"""Tests for the MCP server (archmap mcp command)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from archmap.cli.mcp_server import (
    _dispatch,
    _get_analysis,
    _tool_diff_architecture,
    _tool_get_architecture_summary,
    _tool_get_file_context,
    _tool_get_network_exposure,
    _tool_impact_analysis,
    _tool_run_checks,
    _tool_trace_reachability,
)

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
        "impact": {
            "nodeId": "src/app.py",
            "impactedFiles": ["src/main.py"],
            "impactCount": 1,
            "risk": "ok",
        },
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


def test_trace_reachability_calls_analyzer(
    mock_analysis: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def fake_trace(report: dict, entrypoint: str, max_depth: int | None = None) -> dict:
        captured["report"] = report
        captured["entrypoint"] = entrypoint
        captured["max_depth"] = max_depth
        return {"entrypoint": entrypoint, "reachable": ["src/app.py"], "reachableCount": 1}

    monkeypatch.setattr(
        "archmap.core.analyzer.reachability_analyzer.trace_reachability", fake_trace
    )
    result = _tool_trace_reachability("/fake/project", "src/app.py", 3)
    assert result["reachableCount"] == 1
    assert captured["entrypoint"] == "src/app.py"
    assert captured["max_depth"] == 3
    assert captured["report"] is _FAKE_RESULT


def test_diff_architecture_uses_repo_and_refs(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_analyze_git_ref(repo_path: str, ref: str) -> dict:
        captured.setdefault("refs", []).append((repo_path, ref))
        return {"ref": ref, "metrics": {}}

    def fake_diff_reports(base_report: dict, head_report: dict) -> dict:
        captured["base_report"] = base_report
        captured["head_report"] = head_report
        return {"healthScoreDelta": 0}

    monkeypatch.setattr("archmap.core.analyzer.analyze_git_ref", fake_analyze_git_ref)
    monkeypatch.setattr("archmap.core.analyzer.diff_reports", fake_diff_reports)

    result = _tool_diff_architecture("/fake/project", "/fake/repo", "HEAD~1", "HEAD")
    assert result == {"healthScoreDelta": 0}
    assert captured["refs"] == [("/fake/repo", "HEAD~1"), ("/fake/repo", "HEAD")]
    assert captured["base_report"]["ref"] == "HEAD~1"
    assert captured["head_report"]["ref"] == "HEAD"


def test_diff_architecture_defaults_repo_to_project_path(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_repos: list[str] = []

    def fake_analyze_git_ref(repo_path: str, ref: str) -> dict:
        seen_repos.append(repo_path)
        return {}

    monkeypatch.setattr("archmap.core.analyzer.analyze_git_ref", fake_analyze_git_ref)
    monkeypatch.setattr("archmap.core.analyzer.diff_reports", lambda base, head: {})

    _tool_diff_architecture("/fake/project", "", "HEAD~1", "HEAD")
    assert seen_repos == ["/fake/project", "/fake/project"]


def test_get_network_exposure_calls_scan_and_correlate(
    mock_analysis: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def fake_run_netscan(
        target: str,
        ports_spec: str | None = None,
        top_ports: int | None = None,
        use_nmap: bool | None = None,
        timeout: float = 1.0,
    ) -> dict:
        captured["target"] = target
        captured["ports_spec"] = ports_spec
        captured["timeout"] = timeout
        return {"hosts": []}

    def fake_correlate_exposure(
        scan_result: dict, analysis_result: dict, endpoint_refs: list, network_rules: dict
    ) -> dict:
        captured["scan_result"] = scan_result
        captured["analysis_result"] = analysis_result
        captured["endpoint_refs"] = endpoint_refs
        captured["network_rules"] = network_rules
        return {"findings": [], "summary": {"openPorts": 0}}

    monkeypatch.setattr("archmap.core.netscan.run_netscan", fake_run_netscan)
    monkeypatch.setattr("archmap.core.exposure.correlate_exposure", fake_correlate_exposure)
    monkeypatch.setattr(
        "archmap.core.exposure.endpoint_scanner.scan_endpoint_references",
        lambda path, config: [],
    )

    result = _tool_get_network_exposure(
        "/fake/project", "192.168.1.10", "22,80", None, None, 0.5
    )
    assert result == {"findings": [], "summary": {"openPorts": 0}}
    assert captured["target"] == "192.168.1.10"
    assert captured["ports_spec"] == "22,80"
    assert captured["timeout"] == 0.5
    assert captured["analysis_result"] is _FAKE_RESULT


def test_get_analysis_recomputes_when_fingerprint_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    fingerprints = iter(["fp1", "fp1", "fp2"])

    monkeypatch.setattr(
        "archmap.cli.mcp_server._fingerprint", lambda _path: next(fingerprints)
    )

    def fake_analyze_project(path: str) -> dict:
        calls.append(path)
        return {"call": len(calls)}

    monkeypatch.setattr("archmap.analyze_project", fake_analyze_project)

    import archmap.cli.mcp_server as mcp_server

    mcp_server._cache.clear()
    mcp_server._cache_key.clear()

    first = _get_analysis("/fake/project-fp-test")
    second = _get_analysis("/fake/project-fp-test")
    assert first is second
    assert len(calls) == 1

    third = _get_analysis("/fake/project-fp-test")
    assert len(calls) == 2
    assert third["call"] == 2


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
    assert "trace_reachability" in names
    assert "diff_architecture" in names
    assert "get_network_exposure" in names
    assert len(names) == 7


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


def test_dispatch_trace_reachability_missing_entrypoint(mock_analysis: None) -> None:
    msg = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {"name": "trace_reachability", "arguments": {}},
    }
    resp = _dispatch(msg, "/fake/project")
    assert resp is not None
    assert resp["error"]["code"] == -32602


def test_dispatch_trace_reachability_round_trip(
    mock_analysis: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "archmap.core.analyzer.reachability_analyzer.trace_reachability",
        lambda report, entrypoint, max_depth=None: {
            "entrypoint": entrypoint,
            "reachableCount": 2,
        },
    )
    msg = {
        "jsonrpc": "2.0",
        "id": 8,
        "method": "tools/call",
        "params": {
            "name": "trace_reachability",
            "arguments": {"entrypoint": "src/app.py"},
        },
    }
    resp = _dispatch(msg, "/fake/project")
    assert resp is not None
    data = json.loads(resp["result"]["content"][0]["text"])
    assert data["reachableCount"] == 2


def test_dispatch_diff_architecture_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "archmap.core.analyzer.analyze_git_ref",
        lambda repo_path, ref: {"ref": ref},
    )
    monkeypatch.setattr(
        "archmap.core.analyzer.diff_reports",
        lambda base, head: {"healthScoreDelta": -1},
    )
    msg = {
        "jsonrpc": "2.0",
        "id": 9,
        "method": "tools/call",
        "params": {"name": "diff_architecture", "arguments": {}},
    }
    resp = _dispatch(msg, "/fake/project")
    assert resp is not None
    data = json.loads(resp["result"]["content"][0]["text"])
    assert data["healthScoreDelta"] == -1


def test_dispatch_get_network_exposure_missing_target(mock_analysis: None) -> None:
    msg = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {"name": "get_network_exposure", "arguments": {}},
    }
    resp = _dispatch(msg, "/fake/project")
    assert resp is not None
    assert resp["error"]["code"] == -32602


def test_dispatch_get_network_exposure_round_trip(
    mock_analysis: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "archmap.core.netscan.run_netscan",
        lambda target, **kwargs: {"hosts": [{"ip": target, "openPorts": []}]},
    )
    monkeypatch.setattr(
        "archmap.core.exposure.correlate_exposure",
        lambda scan_result, analysis_result, endpoint_refs, network_rules: {
            "findings": [],
            "summary": {"openPorts": 0},
        },
    )
    monkeypatch.setattr(
        "archmap.core.exposure.endpoint_scanner.scan_endpoint_references",
        lambda path, config: [],
    )
    msg = {
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {"name": "get_network_exposure", "arguments": {"target": "127.0.0.1"}},
    }
    resp = _dispatch(msg, "/fake/project")
    assert resp is not None
    data = json.loads(resp["result"]["content"][0]["text"])
    assert data["summary"]["openPorts"] == 0
