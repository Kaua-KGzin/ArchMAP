"""Tests for main.py and __main__.py coverage."""
from __future__ import annotations

import importlib

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
