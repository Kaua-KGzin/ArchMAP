"""Budget coverage beyond ``analyze``: shared cache, diff, every CLI command, minors."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

import archmap
from archmap.cache import compute_fingerprint, load_cached_report
from archmap.cli import commands as cli_commands
from archmap.cli import mcp_server
from archmap.cli.main import main
from archmap.config import load_project_config
from archmap.core import analyze_project
from archmap.core.analyzer.centrality import build_centrality_findings
from archmap.core.analyzer.dependency_graph import _run_centrality
from archmap.core.analyzer.diff_analyzer import analyze_git_ref, ref_budget
from archmap.core.analyzer.impact_analyzer import (
    IMPACT_LIST_CAP,
    calculate_all_impacts,
    calculate_impact,
    full_impacted_files,
)
from archmap.core.exposure.correlate import correlate_exposure
from archmap.core.perf.budget import Budget
from archmap.core.perf.synthetic import generate_project

TINY = 1e-9
TINY_TOML = "[analysis.limits]\ntime_budget_seconds = 0.000001\n"


def _quality(report: dict[str, Any]) -> dict[str, Any]:
    return report["metrics"]["analysisQuality"]


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    mcp_server._cache.clear()
    mcp_server._cache_key.clear()
    mcp_server._cache_budget.clear()
    generate_project(tmp_path, 20)
    return tmp_path


def _no_reanalysis(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("expected a cache hit, but the project was parsed again")

    monkeypatch.setattr("archmap.core.parse_project", boom)


# --- 1. One cache entry shared by the CLI and the MCP server ----------------


def test_cli_written_cache_is_a_hit_for_mcp_default(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = analyze_project(project)  # CLI: no budget
    assert "budget" not in _quality(cli)
    _no_reanalysis(monkeypatch)
    mcp = mcp_server._get_analysis(str(project))  # MCP default: 120 s
    assert _quality(mcp)["budget"] == {"seconds": 120.0, "source": "mcp-default"}
    assert _quality(mcp)["reductions"] == []
    assert mcp["nodes"] == cli["nodes"]


def test_mcp_written_cache_is_a_hit_for_cli(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mcp = mcp_server._get_analysis(str(project))
    assert _quality(mcp)["budget"]["source"] == "mcp-default"
    _no_reanalysis(monkeypatch)
    cli = analyze_project(project)
    assert "budget" not in _quality(cli)
    assert "reductions" not in _quality(cli)
    assert cli["nodes"] == mcp["nodes"]


def test_cache_hit_is_restamped_with_an_explicit_budget(project: Path) -> None:
    analyze_project(project)
    hit = analyze_project(project, time_budget=900)
    assert _quality(hit)["budget"] == {"seconds": 900, "source": "cli"}
    assert _quality(hit)["reductions"] == []


def test_reduced_run_is_still_never_written(project: Path) -> None:
    reduced = analyze_project(project, time_budget=TINY)
    assert _quality(reduced)["reductions"]
    config = load_project_config(project)
    assert load_cached_report(project, compute_fingerprint(project, config)) is None
    # The next unbudgeted call is a full run, not the reduced one.
    full = analyze_project(project)
    assert "reductions" not in _quality(full)


def test_public_api_default_budget_source_is_api(project: Path) -> None:
    report = archmap.analyze_project(project, use_cache=False, time_budget=900)
    assert report["metrics"]["analysisQuality"]["budget"] == {  # type: ignore[typeddict-item]
        "seconds": 900,
        "source": "api",
    }


# --- 2. diff is budgeted ---------------------------------------------------


def test_ref_budget_is_half_and_zero_is_no_limit() -> None:
    assert ref_budget(10, "cli").seconds == 5
    assert ref_budget(10, "cli").source == "cli"
    assert ref_budget(0, "cli").seconds is None
    assert ref_budget(None, "config").seconds is None
    with pytest.raises(ValueError):
        ref_budget(-1, "cli")


def _fake_git_ref(seen: list[Budget | None]) -> Any:
    def fake(repo: Any, ref: str, budget: Budget | None = None) -> dict:
        seen.append(budget)
        return {"ref": ref, "metrics": {}}

    return fake


def _fake_diff(base: dict, head: dict) -> dict:
    return {"baseRef": base["ref"], "headRef": head["ref"]}


def test_cli_diff_flag_gives_each_ref_half(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: list[Budget | None] = []
    monkeypatch.setattr(cli_commands, "analyze_git_ref", _fake_git_ref(seen))
    monkeypatch.setattr(cli_commands, "diff_reports", _fake_diff)
    monkeypatch.setattr(cli_commands, "print_diff_output", lambda *a, **k: None)
    assert main(["diff", "A", "B", "--repo", str(tmp_path), "--time-budget", "30"]) == 0
    assert [(b.seconds, b.source) for b in seen if b] == [(15, "cli"), (15, "cli")]


def test_cli_diff_honours_config_budget(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / ".archmap.toml").write_text("[analysis.limits]\ntime_budget_seconds = 40\n")
    seen: list[Budget | None] = []
    monkeypatch.setattr(cli_commands, "analyze_git_ref", _fake_git_ref(seen))
    monkeypatch.setattr(cli_commands, "diff_reports", _fake_diff)
    monkeypatch.setattr(cli_commands, "print_diff_output", lambda *a, **k: None)
    assert main(["diff", "A", "B", "--repo", str(tmp_path)]) == 0
    assert [(b.seconds, b.source) for b in seen if b] == [(20, "config"), (20, "config")]

    seen.clear()
    (tmp_path / ".archmap.toml").unlink()
    assert main(["diff", "A", "B", "--repo", str(tmp_path)]) == 0
    assert [b.seconds for b in seen if b] == [None, None]  # CLI default: no budget


@pytest.mark.skipif(shutil.which("git") is None, reason="git not found")
def test_cli_diff_announces_reductions_per_ref(
    tmp_git_repo: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    tmp_git_repo.commit_file("a.py", "import b\n", "add a")
    tmp_git_repo.commit_file("b.py", "x = 1\n", "add b")
    root = str(tmp_git_repo.root)
    assert main(["diff", "HEAD~1", "HEAD", "--repo", root, "--json", "--time-budget", "1e-9"]) == 0
    captured = capsys.readouterr()
    lines = [line for line in captured.err.splitlines() if line.startswith("[budget] ")]
    assert any(line.startswith("[budget] HEAD~1: ") for line in lines)
    assert any(line.startswith("[budget] HEAD: ") for line in lines)
    assert "[budget]" not in captured.out
    json.loads(captured.out)


@pytest.mark.skipif(shutil.which("git") is None, reason="git not found")
def test_analyze_git_ref_records_reductions_under_budget(tmp_git_repo: Any) -> None:
    tmp_git_repo.commit_file("a.py", "import b\n", "add a")
    tmp_git_repo.commit_file("b.py", "x = 1\n", "add b")
    report = analyze_git_ref(tmp_git_repo.root, "HEAD", budget=ref_budget(TINY, "cli"))
    quality = _quality(report)
    assert quality["budget"] == {"seconds": TINY / 2, "source": "cli"}
    assert quality["reductions"]
    unbudgeted = analyze_git_ref(tmp_git_repo.root, "HEAD")
    assert "budget" not in _quality(unbudgeted)


def _mcp_diff(project: Path, **arguments: Any) -> dict[str, Any]:
    message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "diff_architecture", "arguments": arguments},
    }
    response = mcp_server._dispatch(message, str(project))
    assert response is not None and "result" in response, response
    return json.loads(response["result"]["content"][0]["text"])


def _budgeted_fake(seen: list[Budget | None], *, reduce: bool) -> Any:
    def fake(repo: Any, ref: str, budget: Budget | None = None) -> dict:
        seen.append(budget)
        quality: dict[str, Any] = {}
        if budget is not None and budget.active:
            quality["budget"] = budget.describe()
            quality["reductions"] = (
                [{"stage": "impact", "reason": "exhausted", "detail": "x"}] if reduce else []
            )
        return {"ref": ref, "metrics": {"analysisQuality": quality}}

    return fake


def test_mcp_diff_is_an_analysis_tool_with_time_budget_schema() -> None:
    assert "diff_architecture" in mcp_server._ANALYSIS_TOOLS
    tools = {t["name"]: t for t in mcp_server._TOOLS}
    assert "time_budget" in tools["diff_architecture"]["inputSchema"]["properties"]


def test_mcp_diff_precedence_and_notices(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[Budget | None] = []
    monkeypatch.setattr("archmap.core.analyzer.analyze_git_ref", _budgeted_fake(seen, reduce=False))
    monkeypatch.setattr("archmap.core.analyzer.diff_reports", _fake_diff)

    default = _mcp_diff(project)
    assert [(b.seconds, b.source) for b in seen if b] == [(60, "mcp-default")] * 2
    assert default["notice"].startswith("Analysis ran under the default 120 s MCP time budget")
    assert default["notice"].endswith("Each ref gets half of the budget.")

    seen.clear()
    unlimited = _mcp_diff(project, time_budget=0)
    assert [b.seconds for b in seen if b] == [None, None]
    assert "notice" not in unlimited

    seen.clear()
    (project / ".archmap.toml").write_text("[analysis.limits]\ntime_budget_seconds = 10\n")
    configured = _mcp_diff(project)
    assert [(b.seconds, b.source) for b in seen if b] == [(5, "config")] * 2
    assert "notice" not in configured

    seen.clear()
    explicit = _mcp_diff(project, time_budget=8)
    assert [(b.seconds, b.source) for b in seen if b] == [(4, "mcp-arg")] * 2
    assert "notice" not in explicit


def test_mcp_diff_reduction_notice(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[Budget | None] = []
    monkeypatch.setattr("archmap.core.analyzer.analyze_git_ref", _budgeted_fake(seen, reduce=True))
    monkeypatch.setattr("archmap.core.analyzer.diff_reports", _fake_diff)
    payload = _mcp_diff(project, time_budget=2)
    assert payload["notice"] == (
        "Analysis was reduced by the 2 s time budget (mcp-arg): impact. For a full run pass "
        "time_budget=0 or set [analysis.limits] time_budget_seconds in .archmap.toml. "
        "Each ref gets half of the budget."
    )


def test_mcp_diff_rejects_negative_time_budget(project: Path) -> None:
    message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "diff_architecture", "arguments": {"time_budget": -1}},
    }
    response = mcp_server._dispatch(message, str(project))
    assert response is not None
    assert response["error"]["code"] == -32602


# --- 3. Every CLI command announces reductions -----------------------------


def _budget_lines(err: str) -> list[str]:
    return [line for line in err.splitlines() if line.startswith("[budget] ")]


def test_explain_announces_reductions_on_stderr_only(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (project / ".archmap.toml").write_text(TINY_TOML)
    assert main(["explain", str(project), "--json"]) == 0
    captured = capsys.readouterr()
    assert _budget_lines(captured.err)
    assert "(config)" in _budget_lines(captured.err)[0]
    assert "[budget]" not in captured.out
    json.loads(captured.out)


def test_memory_print_announces_unless_quiet(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (project / ".archmap.toml").write_text(TINY_TOML)
    assert main(["memory", str(project), "--print"]) == 0
    captured = capsys.readouterr()
    assert _budget_lines(captured.err)
    assert "[budget]" not in captured.out

    assert main(["memory", str(project), "--print", "--quiet"]) == 0
    assert "[budget]" not in capsys.readouterr().err


def test_risk_announces_reductions(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (project / ".archmap.toml").write_text(TINY_TOML)
    report = analyze_project(project, use_cache=False, time_budget=0)
    target = next(n["id"] for n in report["nodes"] if n.get("type") == "file")
    capsys.readouterr()
    assert main(["risk", target, str(project), "--json"]) == 0
    assert _budget_lines(capsys.readouterr().err)


def test_no_budget_means_no_announcement(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["explain", str(project), "--json"]) == 0
    assert "[budget]" not in capsys.readouterr().err


# --- 7. Centrality early stop ----------------------------------------------


def test_centrality_stopped_before_any_source_is_reported_as_skipped() -> None:
    nodes = [f"n{i:03d}" for i in range(100)]
    edges = [(nodes[i], nodes[i + 1]) for i in range(99)]
    checks = {"n": 0}

    def exhausted() -> bool:
        # Not yet exhausted when the stage starts, exhausted at the first poll inside.
        checks["n"] += 1
        return checks["n"] > 1

    budget = Budget(3600, source="cli")
    budget.exhausted = exhausted  # type: ignore[method-assign]
    scores, meta = _run_centrality(nodes, edges, budget, {"discover": 1.0, "parse": 1.0})
    assert scores == {}
    assert meta["method"] == "skipped"
    assert len(budget.reductions) == 1
    detail = budget.reductions[0]["detail"]
    assert detail.startswith("skipped because the budget ran out before the first source file")
    assert "stopped after 0" not in detail


def test_centrality_early_stop_suppresses_bottleneck_findings() -> None:
    # Scores of a star through a hub: one clear bottleneck.
    nodes = ["hub"] + [f"leaf{i:02d}" for i in range(40)]
    scores = {"hub": 0.9, **{n: 0.0 for n in nodes if n != "hub"}}
    meta = {"method": "exact", "nodes": len(nodes), "connectedPairs": 400}
    assert build_centrality_findings(scores, meta)
    stopped = {**meta, "stoppedEarly": True, "sourcesProcessed": 16}
    assert build_centrality_findings(scores, stopped) == []


# --- 11/12. Impact lists under a reduced run --------------------------------


def _pkg_report(dependents: int, *, stop: bool) -> dict[str, Any]:
    files = [f"src/f{i:04d}.py" for i in range(dependents)]
    edges = [{"source": f, "target": "pkg:redis"} for f in files]
    ids = ["pkg:redis", *files]
    impacts = calculate_all_impacts(ids, edges, should_stop=(lambda: True) if stop else None)
    nodes = [{"id": "pkg:redis", "label": "redis", "type": "package",
              "impact": impacts["pkg:redis"]}]
    nodes += [{"id": f, "label": f, "type": "file", "impact": impacts[f]} for f in files]
    return {"nodes": nodes, "edges": edges}


def test_calculate_all_impacts_should_stop_flipping_mid_run() -> None:
    # A chain c000 <- c001 <- ... : every node impacts all later ones.
    names = [f"c{i:03d}" for i in range(40)]
    edges = [{"source": names[i + 1], "target": names[i]} for i in range(39)]
    full = calculate_all_impacts(names, edges)
    polls = {"n": 0}

    def flip() -> bool:
        polls["n"] += 1
        return polls["n"] > 10

    reduced = calculate_all_impacts(names, edges, should_stop=flip)
    exact_lists = 0
    for name in names:
        assert reduced[name]["impactCount"] == full[name]["impactCount"]
        assert reduced[name]["risk"] == full[name]["risk"]
        if reduced[name]["impactedFiles"] == full[name]["impactedFiles"]:
            exact_lists += 1
            assert "impactedFilesTruncated" not in reduced[name]
        else:
            # Dropped only after the flip: an empty, flagged list.
            assert reduced[name]["impactedFiles"] == []
            assert reduced[name]["impactedFilesTruncated"] is True
    # Components processed before the flip keep their lists (10 polls = 10 components).
    assert exact_lists >= 10
    assert exact_lists < len(names)


def test_impact_analysis_on_pkg_node_returns_full_list_under_reduced_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _pkg_report(250, stop=True)
    stored = report["nodes"][0]["impact"]
    assert stored["impactedFiles"] == []
    assert stored["impactedFilesTruncated"] is True
    monkeypatch.setattr("archmap.cli.mcp_server._get_analysis", lambda _p, _tb=None: report)
    result = mcp_server._tool_impact_analysis("/fake", "pkg:redis")
    assert len(result["impactedFiles"]) == 250
    assert result["impactCount"] == 250


def test_expose_on_pkg_node_returns_full_list_under_reduced_run() -> None:
    report = _pkg_report(250, stop=True)
    netscan = {
        "target": "10.0.0.1",
        "hosts": [{
            "ip": "10.0.0.1",
            "hostname": None,
            "openPorts": [{"port": 6379, "protocol": "tcp", "service": "redis",
                           "risk": {"level": "high", "reason": "x"}}],
        }],
    }
    match = correlate_exposure(netscan, report)["findings"][0]["matchedPackages"][0]
    assert match["impactCount"] == 250
    assert len(match["impactedFiles"]) == 250


def test_full_impacted_files_without_edges_falls_back_to_stored_list() -> None:
    report = _pkg_report(IMPACT_LIST_CAP + 50, stop=False)
    stored = report["nodes"][0]["impact"]["impactedFiles"]
    assert len(stored) == IMPACT_LIST_CAP
    trimmed = {"nodes": report["nodes"]}  # e.g. a snapshot without edges
    assert full_impacted_files(trimmed, "pkg:redis") == stored
    assert full_impacted_files({**trimmed, "edges": []}, "pkg:redis") == stored
    assert len(calculate_impact("pkg:redis", report["edges"])["impactedFiles"]) == 250
