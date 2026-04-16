"""Tests for server.py - covering HTTP handler paths, state, and helpers."""
from __future__ import annotations

import threading
from pathlib import Path

from archmap.cli.server import (
    ReportState,
    _candidate_file_path,
    _describe_directory_picker_error,
    _parse_history_limit,
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


def test_can_open_browser() -> None:
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
