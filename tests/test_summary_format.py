from __future__ import annotations

from archmap.cli import reporting


def _base_report() -> dict:
    return {
        "metrics": {
            "filesAnalyzed": 15,
            "totalDependencies": 42,
            "circularDependencyCount": 2,
            "coupling": {"averageInstability": 0.4},
            "resolutionRate": 0.95,
            "unresolvedImportsTotal": 3,
            "complexity": [],
        },
        "risks": {},
        "architecture": {
            "health": {"score": 78, "grade": "C"},
            "detectedStyle": {"name": "layered", "confidence": 0.88},
            "ruleViolations": [],
            "activeRules": {"forbid": [], "allow": []},
        },
    }


def test_print_summary_default_is_text(capsys) -> None:
    reporting.print_summary(_base_report())
    out = capsys.readouterr().out
    assert "[ok] 15 files analyzed" in out
    assert "[ok] 42 dependencies detected" in out
    assert "Architecture health 78/100 (C)" in out


def test_print_summary_text_explicit(capsys) -> None:
    reporting.print_summary(_base_report(), summary_format="text")
    out = capsys.readouterr().out
    assert "[ok] 15 files analyzed" in out


def test_print_summary_table_contains_metrics(capsys) -> None:
    reporting.print_summary(_base_report(), summary_format="table")
    out = capsys.readouterr().out
    assert "Files analyzed" in out
    assert "15" in out
    assert "Architecture health" in out
    assert "78/100 (C)" in out


def test_print_summary_table_has_separators(capsys) -> None:
    reporting.print_summary(_base_report(), summary_format="table")
    out = capsys.readouterr().out
    assert "─" in out
    assert "[ok]" not in out
    assert "[warn]" not in out


def test_print_summary_table_has_header(capsys) -> None:
    reporting.print_summary(_base_report(), summary_format="table")
    out = capsys.readouterr().out
    assert "Metric" in out
    assert "Value" in out


def test_print_summary_markdown_is_table(capsys) -> None:
    reporting.print_summary(_base_report(), summary_format="markdown")
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if ln.startswith("|")]
    assert len(lines) >= 3
    assert "Metric" in lines[0]
    assert "Value" in lines[0]


def test_print_summary_markdown_contains_values(capsys) -> None:
    reporting.print_summary(_base_report(), summary_format="markdown")
    out = capsys.readouterr().out
    assert "Files analyzed" in out
    assert "15" in out
    assert "78/100 (C)" in out


def test_print_summary_markdown_separator_row(capsys) -> None:
    reporting.print_summary(_base_report(), summary_format="markdown")
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if ln.startswith("|")]
    separator = lines[1]
    assert "---" in separator or "─" in separator or "-" in separator


def test_print_summary_unknown_format_falls_back_to_text(capsys) -> None:
    reporting.print_summary(_base_report(), summary_format="unknown_format")
    out = capsys.readouterr().out
    assert "[ok] 15 files analyzed" in out


def test_build_summary_rows_coverage() -> None:
    rows = reporting._build_summary_rows(_base_report())
    keys = [r[0] for r in rows]
    assert "Files analyzed" in keys
    assert "Dependencies" in keys
    assert "Circular dependencies" in keys
    assert "Import resolution" in keys
    assert "Architecture health" in keys
    assert "Detected style" in keys
