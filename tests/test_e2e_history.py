import shutil

import pytest

from archmap.core.analyzer.history_analyzer import analyze_git_history


@pytest.mark.skipif(shutil.which("git") is None, reason="git not found")
def test_history_evolution(tmp_git_repo):
    tmp_git_repo.commit_file("a.py", "pass", "commit 1")
    tmp_git_repo.commit_file("b.py", "import a", "commit 2")
    tmp_git_repo.commit_file("c.py", "import a", "commit 3")

    history = analyze_git_history(tmp_git_repo.root, limit=10)

    assert history["windowSize"] == 3
    assert len(history["snapshots"]) == 3

    # Check progression
    snapshots = history["snapshots"]
    # In history_analyzer, it lists from oldest to newest (HEAD)
    assert snapshots[0]["files"] == 1
    assert snapshots[1]["files"] == 2
    assert snapshots[2]["files"] == 3

    # Check dependencies count (0, 1, 2)
    assert snapshots[0]["dependencies"] == 0
    assert snapshots[1]["dependencies"] == 1
    assert snapshots[2]["dependencies"] == 2

@pytest.mark.skipif(shutil.which("git") is None, reason="git not found")
def test_history_empty_repo(tmp_git_repo):
    # No commits, just git init
    history = analyze_git_history(tmp_git_repo.root)
    assert history["windowSize"] == 0
    assert history["snapshots"] == []
