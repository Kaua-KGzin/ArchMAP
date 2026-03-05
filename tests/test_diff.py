from __future__ import annotations

import subprocess
from pathlib import Path

from archmap.core.analyzer.diff_analyzer import analyze_git_ref, diff_reports


def test_diff_reports_detects_dependency_and_cycle_changes(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    _git(repo, "init")
    _git(repo, "config", "user.email", "archmap@example.com")
    _git(repo, "config", "user.name", "ArchMAP Test")

    (repo / "a.py").write_text("from b import fn\n", encoding="utf-8")
    (repo / "b.py").write_text("def fn():\n    return 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")

    (repo / "b.py").write_text("import a\n\ndef fn():\n    return 2\n", encoding="utf-8")
    (repo / "c.py").write_text("import a\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "head")

    base_report = analyze_git_ref(repo, "HEAD~1")
    base_report["ref"] = "HEAD~1"
    head_report = analyze_git_ref(repo, "HEAD")
    head_report["ref"] = "HEAD"

    diff = diff_reports(base_report, head_report)

    assert diff["edges"]["delta"] > 0
    assert diff["cycles"]["delta"] == 1
    assert "deltaPercent" in diff["complexity"]


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
