from __future__ import annotations

import subprocess
from pathlib import Path

from archmap.core.analyzer.history_analyzer import analyze_git_history


def test_analyze_git_history_reports_snapshots_cycle_origins_and_hotspots(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    _git(repo, "init")
    _git(repo, "config", "user.email", "archmap@example.com")
    _git(repo, "config", "user.name", "ArchMAP Test")

    (repo / "a.py").write_text("from b import fn\n", encoding="utf-8")
    (repo / "b.py").write_text("def fn():\n    return 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base graph")

    (repo / "b.py").write_text("import a\n\ndef fn():\n    return 2\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "introduce cycle")

    history = analyze_git_history(repo, limit=5)

    assert history["windowSize"] == 2
    assert len(history["snapshots"]) == 2
    assert history["trend"]["cycleDelta"] == 1
    assert history["trend"]["dependencyDelta"] >= 1

    cycle = history["cycles"][0]
    assert cycle["cycle"] == ["a.py", "b.py"]
    assert cycle["introducedIn"]["subject"] == "introduce cycle"
    assert cycle["ageCommits"] == 1
    assert cycle["suspectedOwner"]["author"] == "ArchMAP Test"
    assert {item["file"] for item in cycle["contributors"]} == {"a.py", "b.py"}

    hotspot_files = {item["file"] for item in history["hotspots"]}
    assert "a.py" in hotspot_files or "b.py" in hotspot_files


def _git(repo: Path, *args: str) -> None:
    process = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        message = process.stderr.strip() or process.stdout.strip() or "git command failed"
        raise RuntimeError(message)
