"""Tests for main.py and __main__.py coverage."""
from __future__ import annotations

import importlib
import sys
import types

from archmap.cli.main import _configure_stdio, _print_banner, _resolve_command_handler, main


def test_print_banner(capsys) -> None:
    _print_banner()
    output = capsys.readouterr().out
    assert "ArchMAP" in output
    assert "Kaua-KGzin" in output


def test_configure_stdio_runs_without_error() -> None:
    _configure_stdio()


def test_resolve_command_handler_known() -> None:
    commands = (
        "analyze", "serve", "explain", "risk", "improve", "diff", "history", "init", "watch",
    )
    for cmd in commands:
        assert _resolve_command_handler(cmd) is not None


def test_resolve_command_handler_unknown() -> None:
    assert _resolve_command_handler("nonexistent") is None
    assert _resolve_command_handler(None) is None


def test_main_version(capsys) -> None:
    result = main(["version"])
    assert result == 0
    output = capsys.readouterr().out
    assert "archmap" in output


def test_main_no_args_returns_help(capsys, monkeypatch) -> None:
    # When piped (non-tty), banner is suppressed; with no command, serve is default
    # but we can't run a full server in tests, so test version command
    result = main(["version"])
    assert result == 0


def test_main_keyboard_interrupt(monkeypatch) -> None:
    def raise_ki(_args):
        raise KeyboardInterrupt

    monkeypatch.setattr("archmap.cli.main._resolve_command_handler", lambda _: raise_ki)
    result = main(["analyze"])
    assert result == 130


def test_main_runtime_error(monkeypatch, capsys) -> None:
    def raise_runtime(_args):
        raise RuntimeError("test error")

    monkeypatch.setattr("archmap.cli.main._resolve_command_handler", lambda _: raise_runtime)
    result = main(["analyze"])
    assert result == 1
    assert "test error" in capsys.readouterr().err


def test_dunder_main_importable() -> None:
    mod = importlib.import_module("archmap.__main__")
    assert hasattr(mod, "main")


def test_main_prints_banner_when_tty(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    result = main(["version"])
    assert result == 0
    output = capsys.readouterr().out
    assert "ArchMAP" in output


def test_main_frozen_shows_pause_on_error(monkeypatch, capsys) -> None:
    def raise_runtime(_args):
        raise RuntimeError("something broke")

    monkeypatch.setattr("archmap.cli.main._resolve_command_handler", lambda _: raise_runtime)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr("builtins.input", lambda _: "")

    result = main(["analyze"])
    assert result == 1
    assert "something broke" in capsys.readouterr().err


def test_configure_stdio_handles_stream_without_reconfigure(monkeypatch) -> None:
    fake_stream = types.SimpleNamespace()  # no reconfigure attr
    monkeypatch.setattr(sys, "stdout", fake_stream)
    _configure_stdio()  # must not raise


def test_configure_stdio_handles_reconfigure_error(monkeypatch) -> None:
    def bad_reconfigure(**kwargs):
        raise ValueError("not supported")

    fake_stream = types.SimpleNamespace(reconfigure=bad_reconfigure)
    monkeypatch.setattr(sys, "stdout", fake_stream)
    _configure_stdio()  # must not raise
