"""MCP default time budget (120 s), precedence, and the reduction notice."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from archmap.cli import mcp_server
from archmap.cli.mcp_server import MCP_DEFAULT_TIME_BUDGET, _dispatch
from archmap.core.perf.synthetic import generate_project

TINY = 1e-9  # exhausted before the first reducible stage


def _call(project: Path, name: str, **arguments: Any) -> dict[str, Any]:
    message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    response = _dispatch(message, str(project))
    assert response is not None
    return response


def _payload(response: dict[str, Any]) -> Any:
    assert "result" in response, response
    return json.loads(response["result"]["content"][0]["text"])


def _quality(project: Path) -> dict[str, Any]:
    return mcp_server._cache[str(project)]["metrics"]["analysisQuality"]


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    mcp_server._cache.clear()
    mcp_server._cache_key.clear()
    generate_project(tmp_path, 20)
    return tmp_path


def test_default_budget_is_120_seconds() -> None:
    assert MCP_DEFAULT_TIME_BUDGET == 120.0


def test_default_budget_applies_and_is_announced_in_the_report(project: Path) -> None:
    payload = _payload(_call(project, "get_architecture_summary"))
    # Nothing was reduced, but the default budget is active: the spec wants a notice.
    assert payload["notice"] == (
        "Analysis ran under the default 120 s MCP time budget (mcp-default); nothing "
        "was reduced. Change it with the time_budget argument or [analysis.limits] "
        "time_budget_seconds in .archmap.toml; 0 means no limit."
    )
    assert _quality(project)["budget"] == {"seconds": 120.0, "source": "mcp-default"}


def test_no_default_notice_for_explicit_or_config_budget(project: Path) -> None:
    assert "notice" not in _payload(_call(project, "run_checks", time_budget=900))
    (project / ".archmap.toml").write_text("[analysis.limits]\ntime_budget_seconds = 3600\n")
    assert "notice" not in _payload(_call(project, "run_checks"))


def test_tiny_arg_budget_adds_notice_naming_stages(project: Path) -> None:
    payload = _payload(_call(project, "get_architecture_summary", time_budget=TINY))
    notice = payload["notice"]
    assert notice == (
        f"Analysis was reduced by the {TINY:g} s time budget (mcp-arg): impact, centrality. "
        "For a full run pass time_budget=0 or set [analysis.limits] time_budget_seconds "
        "in .archmap.toml."
    )
    # Original fields are untouched.
    assert "healthScore" in payload


def test_zero_arg_means_no_limit_and_no_notice(project: Path) -> None:
    payload = _payload(_call(project, "get_architecture_summary", time_budget=0))
    assert "notice" not in payload
    quality = _quality(project)
    assert "budget" not in quality
    assert "reductions" not in quality
    assert mcp_server._cache[str(project)]["metrics"]["centrality"]["method"] != "skipped"


def test_config_budget_beats_default(project: Path) -> None:
    (project / ".archmap.toml").write_text("[analysis.limits]\ntime_budget_seconds = 3600\n")
    _payload(_call(project, "get_architecture_summary"))
    assert _quality(project)["budget"] == {"seconds": 3600, "source": "config"}


def test_config_budget_reduction_names_config_source(project: Path) -> None:
    (project / ".archmap.toml").write_text("[analysis.limits]\ntime_budget_seconds = 0.000001\n")
    payload = _payload(_call(project, "run_checks"))
    assert "(config)" in payload["notice"]


def test_arg_beats_config(project: Path) -> None:
    (project / ".archmap.toml").write_text("[analysis.limits]\ntime_budget_seconds = 0.000001\n")
    payload = _payload(_call(project, "run_checks", time_budget=0))
    assert "notice" not in payload
    assert "budget" not in _quality(project)

    mcp_server._cache.clear()
    mcp_server._cache_key.clear()
    _payload(_call(project, "run_checks", time_budget=900))
    assert _quality(project)["budget"] == {"seconds": 900, "source": "mcp-arg"}


def test_in_memory_cache_reruns_reduced_but_reuses_full(project: Path) -> None:
    reduced = _payload(_call(project, "get_architecture_summary", time_budget=TINY))
    assert "notice" in reduced
    # A reduced result is never served to a call with another budget.
    full = _payload(_call(project, "get_architecture_summary", time_budget=0))
    assert "notice" not in full
    assert "budget" not in _quality(project)
    # A full result is valid for any budget: reused, re-stamped with this call's.
    again = _payload(_call(project, "get_architecture_summary", time_budget=TINY))
    assert "notice" not in again
    assert _quality(project)["budget"] == {"seconds": TINY, "source": "mcp-arg"}
    assert _quality(project)["reductions"] == []


@pytest.mark.parametrize("bad", [-1, -0.5, "10", True])
def test_invalid_time_budget_is_rejected(project: Path, bad: Any) -> None:
    response = _call(project, "get_architecture_summary", time_budget=bad)
    assert response["error"]["code"] == -32602
    assert "time_budget" in response["error"]["message"]
    assert str(project) not in mcp_server._cache


def test_schema_advertises_time_budget_on_analysis_tools_only() -> None:
    tools = {t["name"]: t for t in mcp_server._TOOLS}
    for name in mcp_server._ANALYSIS_TOOLS:
        prop = tools[name]["inputSchema"]["properties"]["time_budget"]
        assert prop["type"] == "number"
        assert prop["minimum"] == 0
    assert "time_budget" not in tools["hexdump"]["inputSchema"]["properties"]
    assert "time_budget" not in tools["audit_project"]["inputSchema"]["properties"]


def test_every_tool_that_runs_an_analysis_is_budgeted() -> None:
    import inspect

    source = inspect.getsource(mcp_server)
    callers = {
        t["name"] for t in mcp_server._TOOLS if f"_tool_{t['name']}" in source
    }
    assert mcp_server._ANALYSIS_TOOLS <= callers
