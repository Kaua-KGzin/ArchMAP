from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from archmap.cli import commands
from archmap.cli.main import main
from archmap.core import analyze_project
from archmap.core.perf.progress import Progress


def _project(tmp_path: Path) -> Path:
    (tmp_path / "a.py").write_text("import b\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("x = 1\n", encoding="utf-8")
    return tmp_path


def test_progress_prints_stage_count_and_eta() -> None:
    out = io.StringIO()
    now = [0.0]
    progress = Progress(out, estimate_seconds=30.0, clock=lambda: now[0])
    progress.stage("parse")
    now[0] += 0.6
    progress.advance(4210, 12345)
    text = out.getvalue()
    assert "parse" in text
    assert "left" in text
    assert "4,210/12,345" in text
    progress.close()


def test_progress_throttles_to_half_second() -> None:
    now = [0.0]
    out = io.StringIO()
    progress = Progress(out, 10.0, clock=lambda: now[0])
    progress.stage("parse")
    for i in range(1, 50):
        now[0] += 0.01
        progress.advance(i, 100)
    assert out.getvalue().count("\r") == 1
    now[0] += 0.6
    progress.advance(60, 100)
    assert out.getvalue().count("\r") == 2


def test_close_without_output_writes_nothing() -> None:
    out = io.StringIO()
    Progress(out, 1.0).close()
    assert out.getvalue() == ""


def test_analyze_project_reports_progress_without_changing_report(tmp_path: Path) -> None:
    root = _project(tmp_path)
    out = io.StringIO()
    with_progress = analyze_project(root, use_cache=False, progress=Progress(out, 5.0))
    plain = analyze_project(root, use_cache=False)
    assert "parse" in out.getvalue()
    assert with_progress["nodes"] == plain["nodes"]
    assert with_progress["edges"] == plain["edges"]


def test_cli_non_tty_prints_no_progress(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _project(tmp_path)
    assert main(["analyze", str(root), "--no-cache"]) == 0
    assert "[archmap]" not in capsys.readouterr().err


def test_cli_json_format_progress_on_stderr_only_and_report_is_valid_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    out_file = tmp_path / "r.json"
    # Force progress on: faked TTY and an estimate above the 5 s threshold.
    monkeypatch.setattr("sys.stderr.isatty", lambda: True, raising=False)
    monkeypatch.setattr("archmap.core.perf.estimate.estimate_project",
                        lambda *a, **k: {"seconds": {"expected": 30.0}})
    assert main(["analyze", str(root), "--no-cache", "--format", "json",
                 "--out", str(out_file)]) == 0
    captured = capsys.readouterr()
    assert "[archmap]" in captured.err  # progress was really active
    assert "[archmap]" not in captured.out  # and never leaked onto stdout
    assert "\r" not in captured.out
    json.loads(out_file.read_text(encoding="utf-8"))


def test_cli_progress_goes_to_stderr_when_tty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    monkeypatch.setattr("sys.stderr.isatty", lambda: True, raising=False)
    monkeypatch.setattr("archmap.core.perf.progress.MIN_EXPECTED_SECONDS", -1.0)
    assert main(["analyze", str(root), "--no-cache"]) == 0
    captured = capsys.readouterr()
    assert "[archmap]" in captured.err
    assert "[archmap]" not in captured.out


def test_cli_quiet_never_shows_progress(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    monkeypatch.setattr("sys.stderr.isatty", lambda: True, raising=False)
    monkeypatch.setattr("archmap.core.perf.progress.MIN_EXPECTED_SECONDS", -1.0)
    assert main(["analyze", str(root), "--no-cache", "--quiet"]) == 0
    assert "[archmap]" not in capsys.readouterr().err


def test_cli_short_runs_show_no_progress(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    monkeypatch.setattr("sys.stderr.isatty", lambda: True, raising=False)
    assert main(["analyze", str(root), "--no-cache"]) == 0
    assert "[archmap]" not in capsys.readouterr().err
    assert commands.Progress is Progress


def test_estimate_json_stdout_is_json_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    monkeypatch.setattr("sys.stderr.isatty", lambda: True, raising=False)
    assert main(["analyze", str(root), "--estimate", "--format", "json"]) == 0
    json.loads(capsys.readouterr().out)


# --- ETA covers the stages after parsing ------------------------------------


def _last_line(out: io.StringIO) -> str:
    return out.getvalue().split("\r")[-1].strip()


def _seconds_left(line: str) -> int:
    import re

    match = re.search(r"~(\d+) s left", line)
    assert match, line
    return int(match.group(1))


def test_parse_eta_includes_the_later_stages() -> None:
    from archmap.core.perf.estimate import STAGE_SHARES
    from archmap.core.perf.progress import LATER_STAGES

    out = io.StringIO()
    now = [0.0]
    progress = Progress(out, estimate_seconds=100.0, clock=lambda: now[0])
    progress.stage("parse")
    now[0] += 10.0
    progress.advance(50, 100)  # 10 s for half: ~10 s of parsing left
    later = 100.0 * sum(STAGE_SHARES[s] for s in LATER_STAGES)
    assert _seconds_left(_last_line(out)) == round(10.0 + later)


def test_eta_keeps_decreasing_through_the_later_stages() -> None:
    from archmap.core.perf.progress import LATER_STAGES

    out = io.StringIO()
    now = [0.0]
    progress = Progress(out, estimate_seconds=150.0, clock=lambda: now[0])
    progress.stage("parse")
    now[0] += 1.0
    progress.advance(100, 100)
    etas = [_seconds_left(_last_line(out))]
    progress.stage("analyze")
    etas.append(_seconds_left(_last_line(out)))
    for name in LATER_STAGES:
        now[0] += 1.0
        progress.stage(name)
        line = _last_line(out)
        assert line.startswith(f"[archmap] {name} · ")
        etas.append(_seconds_left(line))
    assert etas == sorted(etas, reverse=True)
    assert etas[0] > etas[-1]


def test_analyze_project_shows_each_later_stage(tmp_path: Path) -> None:
    from archmap.core.perf.progress import LATER_STAGES

    root = _project(tmp_path)
    out = io.StringIO()
    analyze_project(root, use_cache=False, progress=Progress(out, 50.0))
    text = out.getvalue()
    for name in LATER_STAGES:
        assert f"{name} · ~" in text


def test_closed_stream_never_aborts_analysis(tmp_path: Path) -> None:
    class Closed(io.StringIO):
        def write(self, _s: str) -> int:
            raise OSError("stderr is gone")

    root = _project(tmp_path)
    progress = Progress(Closed(), 50.0)
    report = analyze_project(root, use_cache=False, progress=progress)
    progress.close()
    assert report["nodes"]

    really_closed = io.StringIO()
    really_closed.close()
    late = Progress(really_closed, 50.0)
    late.stage("parse")
    late.advance(1, 2)
    late.close()
