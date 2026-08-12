import shutil

import pytest

from archmap.core import analyze_project


@pytest.mark.skipif(shutil.which("git") is None, reason="git not found")
def test_analyze_git_repo(tmp_git_repo):
    tmp_git_repo.commit_file("main.py", "import utils", "initial commit")
    tmp_git_repo.commit_file("utils.py", "pass", "add utils")

    report = analyze_project(tmp_git_repo.root)

    assert report["metrics"]["filesAnalyzed"] == 2
    assert report["metrics"]["totalDependencies"] == 1
    # Check that main.py depends on utils.py
    edges = report["edges"]
    assert any(e["source"] == "main.py" and e["target"] == "utils.py" for e in edges)

@pytest.mark.skipif(shutil.which("git") is None, reason="git not found")
def test_analyze_empty_git_repo(tmp_git_repo):
    # No commits, just git init
    report = analyze_project(tmp_git_repo.root)
    assert report["metrics"]["filesAnalyzed"] == 0


def test_analyze_project_rejects_nonexistent_path(tmp_path):
    missing = tmp_path / "does-not-exist"

    with pytest.raises(FileNotFoundError, match="does not exist"):
        analyze_project(missing)
