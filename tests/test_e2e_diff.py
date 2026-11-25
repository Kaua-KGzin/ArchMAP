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


def test_snapshot_round_trip_on_sample_project(tmp_path, capsys):
    """`analyze --format both` output must be accepted by `diff --snapshot-a/-b`."""
    import json
    from pathlib import Path

    from archmap.cli.main import main

    sample = Path(__file__).resolve().parents[1] / "examples" / "sample-project"
    snap_a = tmp_path / "a.json"
    snap_b = tmp_path / "b.json"
    for snap in (snap_a, snap_b):
        code = main(["analyze", str(sample), "--format", "both", "--out", str(snap),
                     "--out-mermaid", str(tmp_path / "g.mmd"), "--quiet"])
        assert code == 0
    capsys.readouterr()

    code = main(["diff", "--snapshot-a", str(snap_a), "--snapshot-b", str(snap_b), "--json"])
    assert code == 0
    diff = json.loads(capsys.readouterr().out)
    assert diff["architecture"]["healthDelta"] == 0


def _two_snapshots(tmp_path):
    from pathlib import Path

    from archmap.cli.main import main

    sample = Path(__file__).resolve().parents[1] / "examples" / "sample-project"
    paths = []
    for name in ("base.json", "head.json"):
        out = tmp_path / name
        assert main(["analyze", str(sample), "--format", "json", "--out", str(out),
                     "--quiet"]) == 0
        paths.append(str(out))
    return paths


def test_cli_diff_markdown_to_file(tmp_path, capsys):
    from archmap.cli.main import main
    from archmap.exporters.pr_report import PR_REPORT_MARKER

    base, head = _two_snapshots(tmp_path)
    capsys.readouterr()
    report = tmp_path / "report.md"
    code = main(["diff", "--snapshot-a", base, "--snapshot-b", head,
                 "--format", "markdown", "--out", str(report)])
    assert code == 0
    text = report.read_text(encoding="utf-8")
    assert text.startswith(PR_REPORT_MARKER)
    assert "`base.json`" in text and "`head.json`" in text
    assert "No architecture changes detected." in text
    assert "Report written to" in capsys.readouterr().out


def test_cli_diff_json_flag_still_works(tmp_path, capsys):
    import json

    from archmap.cli.main import main

    base, head = _two_snapshots(tmp_path)
    capsys.readouterr()
    assert main(["diff", "--snapshot-a", base, "--snapshot-b", head, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["findingsComparable"] is True


def test_cli_diff_format_json_to_file(tmp_path, capsys):
    import json

    from archmap.cli.main import main

    base, head = _two_snapshots(tmp_path)
    out = tmp_path / "d.json"
    assert main(["diff", "--snapshot-a", base, "--snapshot-b", head,
                 "--format", "json", "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["findings"]["unchanged"] >= 0
