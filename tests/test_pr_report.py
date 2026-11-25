"""Markdown rendering of the architecture delta posted on pull requests."""

from __future__ import annotations

from archmap.exporters.pr_report import MAX_CHARS, MAX_ROWS, PR_REPORT_MARKER, render_pr_report


def _finding(key: str, message: str, severity: str = "medium", **extra) -> dict:
    return {"key": key, "category": key.split("|")[0], "severity": severity,
            "message": message, **extra}


def _diff(new=(), resolved=(), lost=(), comparable=True, health=(80, 80), grades=("B", "B"),
          ratios=(None, None)) -> dict:
    diff: dict = {
        "architecture": {"baseHealth": health[0], "headHealth": health[1],
                         "healthDelta": health[1] - health[0]},
        "grades": {"base": grades[0], "head": grades[1]},
        "cycles": {"base": 0, "head": 0, "delta": 0},
        "findingsComparable": comparable,
        "tests": {"baseTestedRatio": ratios[0], "headTestedRatio": ratios[1],
                  "lostCoverage": list(lost)},
    }
    if comparable:
        new_list = list(new)
        diff["findings"] = {"new": new_list, "resolved": list(resolved), "unchanged": 0}
        diff["bottlenecks"] = {
            "new": [f for f in new_list if f["category"] == "structural_bottleneck"]
        }
    return diff


def _render(diff: dict) -> str:
    return render_pr_report(diff, base_label="abc1234", head_label="def5678")


def test_render_starts_with_marker() -> None:
    assert _render(_diff()).startswith(PR_REPORT_MARKER)


def test_render_summary_line_shows_health_and_grades() -> None:
    out = _render(_diff(health=(68, 64), grades=("C", "D")))
    assert "68 → 64" in out
    assert "(C → D)" in out


def test_render_lists_new_and_resolved() -> None:
    out = _render(_diff(
        new=[_finding("god_module|src/a.py", "God module: src/a.py", file="src/a.py")],
        resolved=[_finding("layer_violation|x|y", "cli → core", source="x", target="y")],
    ))
    assert "#### New findings (1)" in out
    assert "God module: src/a.py" in out
    assert "`src/a.py`" in out
    assert "#### Resolved (1)" in out
    assert "`x` → `y`" in out


def test_render_bottlenecks_and_lost_coverage_sections() -> None:
    out = _render(_diff(
        new=[_finding("structural_bottleneck|b.py", "Structural bottleneck: b.py", "high",
                      file="b.py")],
        lost=[{"file": "c.py", "testedBy": ["tests/test_c.py"]}],
        ratios=(0.729, 0.701),
    ))
    assert "#### New structural bottlenecks (1)" in out
    assert "#### Lost test coverage (1)" in out
    assert "`tests/test_c.py`" in out
    assert "72.9% → 70.1%" in out


def test_render_empty_delta() -> None:
    assert "No architecture changes detected." in _render(_diff())


def test_render_marks_incomparable_base() -> None:
    out = _render(_diff(comparable=False))
    assert "predates finding comparison" in out
    assert "No architecture changes detected." not in out


def test_render_caps_rows_and_size() -> None:
    many = [_finding(f"god_module|f{i}.py", "x" * 400, file=f"f{i}.py") for i in range(200)]
    out = _render(_diff(new=many))
    assert out.count("| medium |") == MAX_ROWS
    assert f"…and {200 - MAX_ROWS} more" in out
    assert len(out) <= MAX_CHARS


def test_render_escapes_pipes() -> None:
    out = _render(_diff(new=[_finding("god_module|a.py", "a | b", file="a.py")]))
    assert "a \\| b" in out


def test_render_footer_has_labels() -> None:
    out = _render(_diff())
    assert "`abc1234`" in out and "`def5678`" in out
