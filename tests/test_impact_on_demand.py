from __future__ import annotations

from typing import Any

import pytest

from archmap.cli.mcp_server import _tool_impact_analysis
from archmap.cli.reporting import print_impact_analysis
from archmap.core.analyzer.impact_analyzer import (
    calculate_all_impacts,
    full_impacted_files,
)
from archmap.core.exposure.correlate import correlate_exposure

DEPENDENTS = 250


def _report(dependents: int = DEPENDENTS) -> dict[str, Any]:
    files = [f"src/f{i:04d}.py" for i in range(dependents)]
    edges = [{"source": f, "target": "pkg:redis"} for f in files]
    ids = ["pkg:redis", *files]
    impacts = calculate_all_impacts(ids, edges)
    nodes = [
        {
            "id": "pkg:redis",
            "label": "redis",
            "type": "package",
            "impact": impacts["pkg:redis"],
        }
    ]
    nodes += [{"id": f, "label": f, "type": "file", "impact": impacts[f]} for f in files]
    return {"nodes": nodes, "edges": edges}


def test_full_impacted_files_recomputes_when_truncated() -> None:
    report = _report()
    stored = report["nodes"][0]["impact"]
    assert stored.get("impactedFilesTruncated") is True
    assert len(stored["impactedFiles"]) == 200
    assert len(full_impacted_files(report, "pkg:redis")) == DEPENDENTS


def test_full_impacted_files_returns_stored_when_not_truncated() -> None:
    report = _report(5)
    node = report["nodes"][0]
    assert full_impacted_files(report, "pkg:redis") == node["impact"]["impactedFiles"]
    assert len(full_impacted_files(report, "pkg:redis")) == 5


def test_mcp_impact_analysis_returns_full_list(monkeypatch: pytest.MonkeyPatch) -> None:
    report = _report()
    monkeypatch.setattr("archmap.cli.mcp_server._get_analysis", lambda _p: report)
    result = _tool_impact_analysis("/fake", "pkg:redis")
    assert len(result["impactedFiles"]) == DEPENDENTS
    assert result["impactCount"] == DEPENDENTS


def test_correlate_package_match_has_full_list() -> None:
    report = _report()
    netscan = {
        "target": "10.0.0.1",
        "hosts": [
            {
                "ip": "10.0.0.1",
                "hostname": None,
                "openPorts": [
                    {
                        "port": 6379,
                        "protocol": "tcp",
                        "service": "redis",
                        "risk": {"level": "high", "reason": "x"},
                    }
                ],
            }
        ],
    }
    result = correlate_exposure(netscan, report)
    match = result["findings"][0]["matchedPackages"][0]
    assert match["impactCount"] == DEPENDENTS
    assert len(match["impactedFiles"]) == DEPENDENTS


def test_print_impact_analysis_uses_count_for_remainder(capsys) -> None:
    report = _report()
    print_impact_analysis(report, "pkg:redis")
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[-1] == f"  - ... and {DEPENDENTS - 15} more files"
    assert sum(1 for line in lines if line.startswith("  - src/")) == 15


def test_print_impact_analysis_large_max_impacted_lists_everything(capsys) -> None:
    report = _report()
    print_impact_analysis(report, "pkg:redis", max_impacted=DEPENDENTS)
    out = capsys.readouterr().out
    assert out.count("  - src/") == DEPENDENTS
