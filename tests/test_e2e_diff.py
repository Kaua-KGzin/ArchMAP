import shutil

import pytest

from archmap.core.analyzer.diff_analyzer import analyze_git_ref, diff_reports


@pytest.mark.skipif(shutil.which("git") is None, reason="git not found")
def test_diff_circular_dependency(tmp_git_repo):
    # Commit 1: Linear
    tmp_git_repo.commit_file("a.py", "import b", "add a")
    tmp_git_repo.commit_file("b.py", "pass", "add b")
    v1 = tmp_git_repo.run("rev-parse", "HEAD").strip()

    # Commit 2: Circular
    v2 = tmp_git_repo.commit_file("b.py", "import a", "add circularity")

    report1 = analyze_git_ref(tmp_git_repo.root, v1)
    report2 = analyze_git_ref(tmp_git_repo.root, v2)

    diff = diff_reports(report1, report2)

    # Check that circular dependency count increased
    assert diff["cycles"]["delta"] == 1

    # Check that edges were added
    # Edge b -> a was added in v2
    assert any(e[0] == "b.py" and e[1] == "a.py" for e in diff["edges"]["added"])
