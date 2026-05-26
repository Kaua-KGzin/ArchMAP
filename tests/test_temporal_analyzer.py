"""Tests for temporal coupling analysis."""

from __future__ import annotations

import pytest

from archmap.core.analyzer.temporal_analyzer import _parse_git_log, analyze_temporal_coupling

# ---------------------------------------------------------------------------
# _parse_git_log
# ---------------------------------------------------------------------------


def test_parse_git_log_basic() -> None:
    raw = "abc123def456abc123def456abc123def456abc123\nfile_a.py\nfile_b.py\n\n"
    commits = _parse_git_log(raw)
    assert len(commits) == 1
    assert "file_a.py" in commits[0]
    assert "file_b.py" in commits[0]


def test_parse_git_log_multiple_commits() -> None:
    raw = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
        "a.py\nb.py\n\n"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
        "b.py\nc.py\n\n"
    )
    commits = _parse_git_log(raw)
    assert len(commits) == 2


def test_parse_git_log_single_file_commit_excluded() -> None:
    # Commits with only one file are excluded (no pairs possible)
    raw = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\nonly_file.py\n\n"
    commits = _parse_git_log(raw)
    assert commits == []


def test_parse_git_log_empty() -> None:
    assert _parse_git_log("") == []


# ---------------------------------------------------------------------------
# analyze_temporal_coupling
# ---------------------------------------------------------------------------


_FAKE_LOG = (
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
    "src/a.py\nsrc/b.py\n\n"
    "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
    "src/a.py\nsrc/b.py\n\n"
    "cccccccccccccccccccccccccccccccccccccccc\n"
    "src/a.py\nsrc/b.py\nsrc/c.py\n\n"
    "dddddddddddddddddddddddddddddddddddddddd\n"
    "src/x.py\nsrc/y.py\n\n"
)


@pytest.fixture()
def mock_git(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    monkeypatch.setattr(
        subprocess,
        "check_output",
        lambda *a, **kw: _FAKE_LOG,
    )


def test_analyze_returns_pairs(mock_git: None) -> None:
    result = analyze_temporal_coupling(".", min_commits=2)
    assert "pairs" in result
    assert result["totalCommitsScanned"] > 0
    pairs = result["pairs"]
    assert any(
        (p["fileA"] == "src/a.py" and p["fileB"] == "src/b.py")
        or (p["fileA"] == "src/b.py" and p["fileB"] == "src/a.py")
        for p in pairs
    )


def test_analyze_min_commits_filter(mock_git: None) -> None:
    result = analyze_temporal_coupling(".", min_commits=3)
    # (x.py, y.py) only co-change once, should be excluded
    pairs = result["pairs"]
    filenames = {(p["fileA"], p["fileB"]) for p in pairs}
    assert ("src/x.py", "src/y.py") not in filenames


def test_analyze_top_limit(mock_git: None) -> None:
    result = analyze_temporal_coupling(".", min_commits=1, top=1)
    assert len(result["pairs"]) <= 1


def test_analyze_coupling_strength_in_range(mock_git: None) -> None:
    result = analyze_temporal_coupling(".", min_commits=1)
    for p in result["pairs"]:
        assert 0.0 <= p["couplingStrength"] <= 1.0


def test_analyze_git_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    def raise_error(*a: object, **kw: object) -> str:
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(subprocess, "check_output", raise_error)
    result = analyze_temporal_coupling(".")
    assert "error" in result
    assert result["pairs"] == []


def test_analyze_git_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    def _raise(*a: object, **kw: object) -> str:
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(subprocess, "check_output", _raise)
    result = analyze_temporal_coupling(".")
    assert "error" in result


def test_analyze_metadata_fields(mock_git: None) -> None:
    result = analyze_temporal_coupling(".", min_commits=1, top=5)
    assert "totalCommitsScanned" in result
    assert "totalPairs" in result
    assert "minCommits" in result
    assert result["minCommits"] == 1


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_run_temporal_json(mock_git: None, capsys: pytest.CaptureFixture) -> None:
    import argparse

    from archmap.cli.commands import run_temporal

    args = argparse.Namespace(path=".", min_commits=1, top=10, json=True)
    rc = run_temporal(args)
    assert rc == 0
    import json

    out = capsys.readouterr().out
    data = json.loads(out)
    assert "pairs" in data


def test_run_temporal_text(mock_git: None, capsys: pytest.CaptureFixture) -> None:
    import argparse

    from archmap.cli.commands import run_temporal

    args = argparse.Namespace(path=".", min_commits=1, top=10, json=False)
    rc = run_temporal(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "Temporal" in out


def test_run_temporal_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    import argparse
    import subprocess

    from archmap.cli.commands import run_temporal

    def _raise(*a: object, **kw: object) -> str:
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(subprocess, "check_output", _raise)
    args = argparse.Namespace(path=".", min_commits=2, top=20, json=False)
    rc = run_temporal(args)
    assert rc == 1


def test_run_temporal_no_pairs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    import argparse
    import subprocess

    from archmap.cli.commands import run_temporal

    monkeypatch.setattr(subprocess, "check_output", lambda *a, **kw: "")
    args = argparse.Namespace(path=".", min_commits=2, top=20, json=False)
    rc = run_temporal(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "No significant" in out
