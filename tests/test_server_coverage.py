"""Tests for server.py - covering HTTP handler paths, state, and helpers."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

from archmap.cli.server import (
    ReportState,
    _candidate_file_path,
    _describe_directory_picker_error,
    _open_local_path,
    _parse_history_limit,
    _resolve_node_file_path,
    browser_host,
    build_http_handler,
    can_open_browser,
    resolve_static_dir,
)


def test_report_state_from_path(tmp_path) -> None:
    (tmp_path / "app.py").write_text("import os\n", encoding="utf-8")
    state = ReportState.from_path(tmp_path)
    assert state.path == tmp_path.resolve()
    assert "nodes" in state.report


def test_report_state_set_path(tmp_path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    state = ReportState.from_path(tmp_path)

    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.py").write_text("y = 2\n", encoding="utf-8")
    state.set_path(sub)
    assert state.path == sub.resolve()


def test_report_state_reanalyze(tmp_path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    state = ReportState.from_path(tmp_path)
    state.history_cache[("HEAD", 12)] = {"cached": True}
    state.reanalyze()
    assert state.history_cache == {}


def test_report_state_notify_listeners(tmp_path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    state = ReportState.from_path(tmp_path)
    event = threading.Event()
    with state._listeners_lock:
        state._listeners.append(event)
    state.notify_listeners()
    assert event.is_set()


def test_resolve_static_dir() -> None:
    static_dir = resolve_static_dir()
    assert isinstance(static_dir, Path)


def test_can_open_browser(monkeypatch) -> None:
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("TERMUX_VERSION", raising=False)
    assert can_open_browser("localhost") is True
    assert can_open_browser("127.0.0.1") is True
    assert can_open_browser("0.0.0.0") is True
    assert can_open_browser("remote.example.com") is False


def test_browser_host() -> None:
    assert browser_host("0.0.0.0") == "localhost"
    assert browser_host("::") == "localhost"
    assert browser_host("127.0.0.1") == "127.0.0.1"


def test_parse_history_limit() -> None:
    assert _parse_history_limit("5") == 5
    assert _parse_history_limit("0") == 1
    assert _parse_history_limit("100") == 50
    assert _parse_history_limit("abc") == 12
    assert _parse_history_limit(None) == 12


def test_describe_directory_picker_error_import() -> None:
    exc = ImportError("no tkinter")
    msg = _describe_directory_picker_error(exc)
    assert "unavailable" in msg
    assert "manually" in msg.lower() or "manual" in msg.lower()


def test_describe_directory_picker_error_other() -> None:
    exc = RuntimeError("display not found")
    msg = _describe_directory_picker_error(exc)
    assert "display not found" in msg


def test_describe_directory_picker_error_empty_message() -> None:
    exc = RuntimeError()
    msg = _describe_directory_picker_error(exc)
    assert "unavailable" in msg.lower()


def test_candidate_file_path_directory(tmp_path) -> None:
    (tmp_path / "src" / "app.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")

    result = _candidate_file_path(tmp_path, "src/app.py")
    assert result is not None
    assert result.name == "app.py"


def test_candidate_file_path_traversal_blocked(tmp_path) -> None:
    result = _candidate_file_path(tmp_path, "../../../etc/passwd")
    assert result is None


def test_candidate_file_path_file_root(tmp_path) -> None:
    target = tmp_path / "single.py"
    target.write_text("x = 1\n", encoding="utf-8")

    result = _candidate_file_path(target, "single.py")
    assert result is not None


def test_candidate_file_path_file_root_mismatch(tmp_path) -> None:
    target = tmp_path / "single.py"
    target.write_text("x = 1\n", encoding="utf-8")

    result = _candidate_file_path(target, "other.py")
    assert result is None


def test_build_http_handler_returns_class(tmp_path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html></html>", encoding="utf-8")

    state = ReportState.from_path(tmp_path)
    handler_class = build_http_handler(state, static)
    assert handler_class is not None


def test_report_state_history_uses_cache(tmp_path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    state = ReportState.from_path(tmp_path)

    result1 = state.history(ref="HEAD", limit=5)
    result2 = state.history(ref="HEAD", limit=5)
    result3 = state.history(ref="main", limit=5)

    assert result1 == result2
    assert result3["ref"] == "main"
    assert result1 is result2  # same cached object


def test_resolve_node_file_path_returns_none_for_package_node(tmp_path) -> None:
    report = {
        "projectRoot": str(tmp_path),
        "nodes": [{"id": "requests", "type": "package"}],
    }

    result = _resolve_node_file_path(tmp_path, report, "requests")
    assert result is None


def test_resolve_node_file_path_returns_none_for_missing_file(tmp_path) -> None:
    report = {
        "projectRoot": str(tmp_path),
        "nodes": [{"id": "ghost.py", "type": "file"}],
    }

    result = _resolve_node_file_path(tmp_path, report, "ghost.py")
    assert result is None


def test_open_local_path_windows(tmp_path, monkeypatch) -> None:
    target = tmp_path / "app.py"
    target.write_text("x = 1\n", encoding="utf-8")

    opened: list[str] = []
    monkeypatch.setattr(sys, "platform", "win32")

    import archmap.cli.server as server_mod
    monkeypatch.setattr(server_mod.os, "startfile", lambda path: opened.append(path), raising=False)

    _open_local_path(target)
    assert len(opened) == 1


def test_open_local_path_darwin(tmp_path, monkeypatch) -> None:
    target = tmp_path / "app.py"
    target.write_text("x = 1\n", encoding="utf-8")

    popen_calls: list[list] = []
    monkeypatch.setattr(sys, "platform", "darwin")

    import archmap.cli.server as server_mod
    monkeypatch.setattr(
        server_mod.subprocess,
        "Popen",
        lambda cmd, **kwargs: popen_calls.append(cmd),
    )

    _open_local_path(target)
    assert popen_calls and popen_calls[0][0] == "open"


def test_open_local_path_linux(tmp_path, monkeypatch) -> None:
    target = tmp_path / "app.py"
    target.write_text("x = 1\n", encoding="utf-8")

    popen_calls: list[list] = []
    monkeypatch.setattr(sys, "platform", "linux")

    import archmap.cli.server as server_mod
    monkeypatch.setattr(
        server_mod.subprocess,
        "Popen",
        lambda cmd, **kwargs: popen_calls.append(cmd),
    )

    _open_local_path(target)
    assert popen_calls and popen_calls[0][0] == "xdg-open"


def test_candidate_file_path_file_root_traversal_blocked(tmp_path) -> None:
    target = tmp_path / "single.py"
    target.write_text("x = 1\n", encoding="utf-8")

    result = _candidate_file_path(target, "../../../etc/passwd")
    assert result is None
