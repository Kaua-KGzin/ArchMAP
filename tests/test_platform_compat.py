from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from archmap.cli.server import (
    _has_display,
    _is_termux,
    _open_local_path,
    can_open_browser,
)

# ---------------------------------------------------------------------------
# _is_termux
# ---------------------------------------------------------------------------

def test_is_termux_via_env_var(monkeypatch):
    monkeypatch.setenv("TERMUX_VERSION", "0.118")
    assert _is_termux() is True


def test_is_termux_via_prefix(monkeypatch):
    monkeypatch.delenv("TERMUX_VERSION", raising=False)
    monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")
    assert _is_termux() is True


def test_is_termux_via_data_user_prefix(monkeypatch):
    monkeypatch.delenv("TERMUX_VERSION", raising=False)
    monkeypatch.setenv("PREFIX", "/data/user/0/com.termux/files/usr")
    assert _is_termux() is True


def test_is_not_termux_on_plain_linux(monkeypatch, tmp_path):
    monkeypatch.delenv("TERMUX_VERSION", raising=False)
    monkeypatch.delenv("PREFIX", raising=False)
    # Patch Path.exists to return False for Termux path
    with patch.object(Path, "exists", return_value=False):
        assert _is_termux() is False


def test_is_not_termux_with_normal_prefix(monkeypatch):
    monkeypatch.delenv("TERMUX_VERSION", raising=False)
    monkeypatch.setenv("PREFIX", "/usr/local")
    with patch.object(Path, "exists", return_value=False):
        assert _is_termux() is False


# ---------------------------------------------------------------------------
# _has_display
# ---------------------------------------------------------------------------

def test_has_display_with_x11(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert _has_display() is True


def test_has_display_with_wayland(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    assert _has_display() is True


def test_no_display_headless(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert _has_display() is False


# ---------------------------------------------------------------------------
# can_open_browser
# ---------------------------------------------------------------------------

def test_can_open_browser_localhost(monkeypatch):
    monkeypatch.delenv("TERMUX_VERSION", raising=False)
    monkeypatch.delenv("PREFIX", raising=False)
    monkeypatch.setenv("DISPLAY", ":0")
    with patch.object(Path, "exists", return_value=False):
        assert can_open_browser("localhost") is True
        assert can_open_browser("127.0.0.1") is True
        assert can_open_browser("0.0.0.0") is True


def test_cannot_open_browser_on_termux(monkeypatch):
    monkeypatch.setenv("TERMUX_VERSION", "0.118")
    assert can_open_browser("localhost") is False


def test_cannot_open_browser_headless_linux(monkeypatch):
    monkeypatch.delenv("TERMUX_VERSION", raising=False)
    monkeypatch.delenv("PREFIX", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    with patch.object(Path, "exists", return_value=False):
        if sys.platform.startswith("linux"):
            assert can_open_browser("localhost") is False


def test_cannot_open_browser_external_host(monkeypatch):
    monkeypatch.delenv("TERMUX_VERSION", raising=False)
    monkeypatch.delenv("PREFIX", raising=False)
    monkeypatch.setenv("DISPLAY", ":0")
    with patch.object(Path, "exists", return_value=False):
        assert can_open_browser("192.168.1.10") is False


# ---------------------------------------------------------------------------
# _open_local_path
# ---------------------------------------------------------------------------

def test_open_local_path_termux_calls_termux_open(monkeypatch, tmp_path):
    monkeypatch.setenv("TERMUX_VERSION", "0.118")
    f = tmp_path / "file.py"
    f.write_text("x = 1")

    launched = []

    def fake_popen(cmd, **kwargs):
        launched.append(cmd)

    with (
        patch("sys.platform", "linux"),
        patch("subprocess.Popen", side_effect=fake_popen),
    ):
        _open_local_path(f)

    assert launched[0][0] == "termux-open"
    assert str(f) in launched[0]


def test_open_local_path_termux_handles_missing_binary(monkeypatch, tmp_path):
    monkeypatch.setenv("TERMUX_VERSION", "0.118")
    f = tmp_path / "file.py"
    f.write_text("x = 1")

    def fake_popen(cmd, **kwargs):
        raise OSError("termux-open not found")

    with patch("subprocess.Popen", side_effect=fake_popen):
        # Should not raise
        _open_local_path(f)


def test_open_local_path_linux_xdg(monkeypatch, tmp_path):
    monkeypatch.delenv("TERMUX_VERSION", raising=False)
    monkeypatch.delenv("PREFIX", raising=False)

    f = tmp_path / "file.py"
    f.write_text("x = 1")
    launched = []

    def fake_popen(cmd, **kwargs):
        launched.append(cmd)

    with (
        patch.object(Path, "exists", return_value=False),
        patch("sys.platform", "linux"),
        patch("subprocess.Popen", side_effect=fake_popen),
    ):
        _open_local_path(f)

    assert any("xdg-open" in str(c) for c in launched)


def test_open_local_path_linux_handles_missing_xdg_open(monkeypatch, tmp_path):
    monkeypatch.delenv("TERMUX_VERSION", raising=False)
    monkeypatch.delenv("PREFIX", raising=False)

    f = tmp_path / "file.py"
    f.write_text("x = 1")

    def fake_popen(cmd, **kwargs):
        raise OSError("xdg-open not found")

    with (
        patch.object(Path, "exists", return_value=False),
        patch("sys.platform", "linux"),
        patch("subprocess.Popen", side_effect=fake_popen),
    ):
        # Should not raise
        _open_local_path(f)


# ---------------------------------------------------------------------------
# _pick_directory — headless graceful fallback
# ---------------------------------------------------------------------------

def test_pick_directory_falls_back_on_import_error():

    # We can't easily instantiate Handler without a real server, so test the
    # describe helper directly which is called on ImportError.
    from archmap.cli.server import _describe_directory_picker_error

    err = ImportError("No module named 'tkinter'")
    msg = _describe_directory_picker_error(err)
    assert "unavailable" in msg
    assert "manually" in msg


def test_pick_directory_falls_back_on_tcl_error():
    from archmap.cli.server import _describe_directory_picker_error

    # Simulate TclError (not ImportError / RuntimeError)
    class TclError(Exception):
        pass

    err = TclError("no display name and no $DISPLAY environment variable")
    msg = _describe_directory_picker_error(err)
    # Generic message should still be returned
    assert "unavailable" in msg or len(msg) > 0
