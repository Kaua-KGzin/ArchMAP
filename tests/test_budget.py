from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from archmap.cache import compute_fingerprint, load_cached_report
from archmap.cli.main import main
from archmap.config import load_project_config
from archmap.core import analyze_project
from archmap.core.analyzer.centrality import betweenness_centrality
from archmap.core.analyzer.dependency_graph import analyze_graph
from archmap.core.graph.graph_builder import build_graph
from archmap.core.parser import parse_project
from archmap.core.perf.budget import CENTRALITY_REDUCED_SAMPLES, Budget
from archmap.core.perf.synthetic import generate_project, generate_sources

EVIDENCE = (
    "Change it with --time-budget (CLI) or the time_budget argument (MCP, API), "
    "[analysis.limits] time_budget_seconds, or 0 for no limit"
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def _without_timings(report: dict[str, Any]) -> dict[str, Any]:
    clean = copy.deepcopy(report)
    clean["metrics"]["analysisQuality"].pop("timingsMs", None)
    return clean


@pytest.fixture(scope="module")
def big_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("big")
    generate_project(root, 1000)
    return root


# --- Budget object -------------------------------------------------------


def test_budget_tracks_remaining_and_exhaustion() -> None:
    clock = FakeClock()
    budget = Budget(10, source="cli", clock=clock)
    assert budget.remaining() == 10
    assert not budget.exhausted()
    assert budget.allows("centrality", 9.5)
    assert not budget.allows("centrality", 10.5)
    clock.now += 10
    assert budget.remaining() == 0
    assert budget.exhausted()
    assert not budget.allows("centrality", 0.0)


def test_budget_none_and_zero_mean_no_limit() -> None:
    for seconds in (None, 0, 0.0):
        budget = Budget(seconds, source="config")
        assert budget.seconds is None
        assert budget.remaining() is None
        assert not budget.exhausted()
        assert budget.allows("centrality", 1e9)
        assert budget.describe() is None


def test_budget_rejects_negative_and_unknown_source() -> None:
    with pytest.raises(ValueError, match=">= 0"):
        Budget(-1, source="cli")
    with pytest.raises(ValueError, match=">= 0"):
        Budget(float("nan"), source="cli")
    with pytest.raises(ValueError, match="source"):
        Budget(5, source="nowhere")  # type: ignore[arg-type]


def test_budget_records_reductions_and_formats_message() -> None:
    budget = Budget(0.5, source="mcp-default")
    budget.record("centrality", "exhausted", "skipped")
    assert budget.reductions == [
        {"stage": "centrality", "reason": "exhausted", "detail": "skipped"}
    ]
    assert budget.describe() == {"seconds": 0.5, "source": "mcp-default"}
    assert budget.message(budget.reductions[0]) == (
        "centrality was reduced by the 0.5 s time budget (mcp-default): skipped"
    )


# --- Reductions in a real run --------------------------------------------


def test_tiny_budget_reduces_and_is_not_cached(big_project: Path) -> None:
    report = analyze_project(big_project, time_budget=0.001)
    quality = report["metrics"]["analysisQuality"]
    stages = [r["stage"] for r in quality["reductions"]]
    assert stages == ["impact", "centrality"]
    assert quality["budget"] == {"seconds": 0.001, "source": "cli"}
    assert report["metrics"]["centrality"]["method"] == "skipped"
    assert all("betweenness" not in node for node in report["nodes"])
    # Counts and risk stay exact even though lists were dropped.
    full = analyze_project(big_project, use_cache=False)
    exact = {n["id"]: n["impact"] for n in full["nodes"]}
    dropped = 0
    for node in report["nodes"]:
        impact = node["impact"]
        assert impact["impactCount"] == exact[node["id"]]["impactCount"]
        assert impact["risk"] == exact[node["id"]]["risk"]
        if impact["impactCount"] and not impact["impactedFiles"]:
            assert impact["impactedFilesTruncated"] is True
            dropped += 1
    assert dropped > 0

    findings = [f for f in report["findings"] if f["category"] == "budget_reduction"]
    assert len(findings) == 2
    for finding, reduction in zip(findings, quality["reductions"], strict=True):
        assert finding["id"].startswith("QUAL-")
        assert finding["severity"] == "low"
        assert finding["message"] == (
            f"{reduction['stage']} was reduced by the 0.001 s time budget (cli): "
            f"{reduction['detail']}"
        )
        assert EVIDENCE in finding["evidence"]

    config = load_project_config(big_project)
    # A reduced run is never written: there is no cache entry at all.
    assert load_cached_report(big_project, compute_fingerprint(big_project, config)) is None


def test_no_budget_report_is_unchanged_and_cached(tmp_path: Path) -> None:
    generate_project(tmp_path, 120)
    plain = analyze_project(tmp_path, use_cache=False)
    quality = plain["metrics"]["analysisQuality"]
    assert "reductions" not in quality
    assert "budget" not in quality
    assert not [f for f in plain["findings"] if f["category"] == "budget_reduction"]

    zero = analyze_project(tmp_path, use_cache=False, time_budget=0)
    assert _without_timings(zero) == _without_timings(plain)

    generous = analyze_project(tmp_path, use_cache=False, time_budget=3600)
    assert generous["metrics"]["analysisQuality"]["reductions"] == []
    assert generous["metrics"]["analysisQuality"]["budget"] == {"seconds": 3600, "source": "cli"}
    generous["metrics"]["analysisQuality"].pop("reductions")
    generous["metrics"]["analysisQuality"].pop("budget")
    assert _without_timings(generous) == _without_timings(plain)

    cached_run = analyze_project(tmp_path)
    config = load_project_config(tmp_path)
    assert load_cached_report(tmp_path, compute_fingerprint(tmp_path, config)) == cached_run


def test_projected_overrun_samples_centrality() -> None:
    sources = generate_sources(200)
    graph = build_graph(parse_project(".", virtual_files=sources, parallel=False))
    # Discovery and parse "took" an hour, so centrality is projected to overrun.
    graph["diagnostics"]["timingsMs"] = {"discover": 1.8e6, "parse": 1.8e6}
    clock = FakeClock()
    budget = Budget(60, source="config", clock=clock)
    report = analyze_graph(graph, budget=budget)
    centrality = report["metrics"]["centrality"]
    assert centrality["method"] == "sampled"
    assert centrality["samples"] == CENTRALITY_REDUCED_SAMPLES
    assert [r["stage"] for r in budget.reductions] == ["centrality"]
    assert budget.reductions[0]["reason"] == "projected"
    assert report["metrics"]["analysisQuality"]["reductions"] == budget.reductions


def test_centrality_stops_early_every_16_sources() -> None:
    nodes = [f"n{i:03d}" for i in range(100)]
    edges = [(nodes[i], nodes[i + 1]) for i in range(99)]
    polls = {"n": 0}

    def stop() -> bool:
        polls["n"] += 1
        return polls["n"] > 2

    _, meta = betweenness_centrality(nodes, edges, should_stop=stop)
    assert meta["stoppedEarly"] is True
    assert meta["sourcesProcessed"] == 32
    _, full_meta = betweenness_centrality(nodes, edges)
    assert "stoppedEarly" not in full_meta


# --- Inputs: config, CLI, analyze_project ---------------------------------


def test_negative_explicit_budget_rejected(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n")
    with pytest.raises(ValueError, match=">= 0"):
        analyze_project(tmp_path, time_budget=-1)


def test_explicit_budget_beats_config(tmp_path: Path) -> None:
    generate_project(tmp_path, 20)
    (tmp_path / ".archmap.toml").write_text("[analysis.limits]\ntime_budget_seconds = 0.000001\n")
    from_config = analyze_project(tmp_path, use_cache=False)
    assert from_config["metrics"]["analysisQuality"]["budget"]["source"] == "config"
    assert from_config["metrics"]["analysisQuality"]["reductions"]
    unlimited = analyze_project(tmp_path, use_cache=False, time_budget=0)
    assert "budget" not in unlimited["metrics"]["analysisQuality"]


def test_cli_negative_time_budget_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["analyze", ".", "--time-budget", "-1"])
    assert exc.value.code == 2
    assert "must be 0 or more seconds" in capsys.readouterr().err


def test_cli_prints_budget_lines_unless_quiet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    generate_project(tmp_path, 30)
    out = tmp_path / "out.json"
    assert main(["analyze", str(tmp_path), "--time-budget", "0.000001", "--out", str(out)]) == 0
    err = capsys.readouterr().err
    lines = [line for line in err.splitlines() if line.startswith("[budget] ")]
    assert lines
    assert lines[0].startswith("[budget] impact was reduced by the 1e-06 s time budget (cli): ")

    assert main(
        ["analyze", str(tmp_path), "--time-budget", "0.000001", "--quiet", "--out", str(out)]
    ) == 0
    assert "[budget]" not in capsys.readouterr().err


def test_estimate_with_malformed_config_matches_analyze(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / ".archmap.toml").write_text("[analysis.limits]\ntime_budget_seconds = -3\n")
    message = "analysis.limits.time_budget_seconds must be >= 0"
    assert main(["analyze", str(tmp_path), "--estimate"]) == 1
    assert f"[error] {message}" in capsys.readouterr().err
    assert main(["analyze", str(tmp_path)]) == 1
    assert f"[error] {message}" in capsys.readouterr().err
