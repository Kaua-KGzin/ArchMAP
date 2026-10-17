"""Tests for analysis-quality metrics (parse coverage, failures, confidence)."""

from __future__ import annotations

from pathlib import Path

import pytest

from archmap import analyze_project
from archmap.cli.args import build_parser
from archmap.cli.reporting import evaluate_quality_gates
from archmap.core.analyzer.quality import (
    MAX_FAILURE_FINDINGS,
    build_analysis_quality,
    build_quality_findings,
    empty_diagnostics,
)
from archmap.core.memory.digest import generate_memory_digest
from archmap.core.parser import parse_project
from archmap.core.parser.registry import registry


def _parsed(lang: str, total: int, resolved: int) -> dict:
    return {"language": lang, "importsTotal": total, "importsResolved": resolved}


def test_clean_project_has_full_confidence() -> None:
    quality = build_analysis_quality(None, [_parsed("python", 4, 4)])
    assert quality["coverage"] == 1.0
    assert quality["confidence"] == 1.0
    assert quality["confidenceLevel"] == "high"
    assert quality["warnings"] == []
    assert build_quality_findings(quality) == []


def test_failures_reduce_coverage_and_emit_findings() -> None:
    diag = empty_diagnostics()
    diag["discovered"] = 4
    diag["parseFailures"] = [{"file": "b.py", "language": "python", "error": "ValueError: x"}]
    diag["decodeErrors"] = ["c.py"]
    diag["oversized"] = ["d.py"]
    quality = build_analysis_quality(diag, [_parsed("python", 2, 2)])

    assert quality["coverage"] == 0.25
    assert quality["confidenceLevel"] == "low"
    assert quality["languages"]["python"]["failures"] == 1
    assert len(quality["warnings"]) == 3

    findings = build_quality_findings(quality)
    assert [f["category"] for f in findings] == [
        "parse_failure",
        "decode_failure",
        "oversized_skipped",
    ]
    assert [f["id"] for f in findings] == ["QUAL-001", "QUAL-002", "QUAL-003"]
    assert findings[0]["file"] == "b.py"
    assert all(f["domain"] == "quality" for f in findings)


def test_low_language_resolution_is_flagged() -> None:
    quality = build_analysis_quality(None, [_parsed("go", 10, 2), _parsed("python", 2, 0)])
    assert quality["resolutionRate"] == pytest.approx(2 / 12, abs=0.001)
    # python has too few imports to judge; go is flagged.
    findings = build_quality_findings(quality)
    assert [f["category"] for f in findings] == ["low_resolution"]
    assert findings[0]["message"].startswith("go:")


def test_failure_findings_are_capped() -> None:
    diag = empty_diagnostics()
    diag["parseFailures"] = [
        {"file": f"f{i:03d}.py", "language": "python", "error": "E"} for i in range(40)
    ]
    findings = build_quality_findings(build_analysis_quality(diag, []))
    assert len(findings) == MAX_FAILURE_FINDINGS + 1
    assert "15 more" in findings[-1]["message"]


def test_parse_project_records_failures_decode_errors_and_oversize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "ok.py").write_text("import os\n", encoding="utf-8")
    (tmp_path / "boom.py").write_text("import sys\n", encoding="utf-8")
    (tmp_path / "latin.py").write_bytes(b"x = '\xe9\xff'\n")
    (tmp_path / "big.py").write_text("x = 1\n" * 50, encoding="utf-8")
    (tmp_path / ".archmap.toml").write_text(
        "[analysis]\nmax_file_size_bytes = 100\n", encoding="utf-8"
    )

    python_parser = registry.get_parser("python")
    assert python_parser is not None
    original = python_parser.parse

    def flaky_parse(source: str):  # type: ignore[no-untyped-def]
        if "sys" in source:
            raise ValueError("synthetic failure")
        return original(source)

    monkeypatch.setattr(python_parser, "parse", flaky_parse)
    parsed = parse_project(tmp_path, parallel=False)
    diag = parsed["diagnostics"]

    assert [f["file"] for f in diag["parseFailures"]] == ["boom.py"]
    assert "ValueError: synthetic failure" in diag["parseFailures"][0]["error"]
    assert diag["decodeErrors"] == ["latin.py"]
    assert diag["oversized"] == ["big.py"]
    assert diag["discovered"] == 4
    assert set(diag["timingsMs"]) == {"discover", "parse"}


def test_analyze_project_exposes_quality(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("import b\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("x = 1\n", encoding="utf-8")
    report = analyze_project(tmp_path, use_cache=False)
    quality = report["metrics"]["analysisQuality"]  # type: ignore[typeddict-item]
    assert quality["filesParsed"] == 2
    assert quality["confidenceLevel"] == "high"
    assert "Analysis confidence: **high**" in generate_memory_digest(dict(report))


def test_quality_gates() -> None:
    report = {
        "metrics": {"analysisQuality": {"coverage": 0.8, "parseFailureCount": 3}},
    }
    parser = build_parser()
    args = parser.parse_args(["analyze", ".", "--min-coverage", "90", "--max-parse-failures", "2"])
    failures = evaluate_quality_gates(report, args)
    assert any("coverage gate failed: 80%" in f for f in failures)
    assert any("parse-failure gate failed: 3" in f for f in failures)
    lenient = parser.parse_args(["analyze", ".", "--min-coverage", "80"])
    assert evaluate_quality_gates(report, lenient) == []
