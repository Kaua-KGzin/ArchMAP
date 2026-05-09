from __future__ import annotations

import threading
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

from archmap.cli import server as cli_server
from archmap.cli.server import _build_badge_svg


# ── helpers ─────────────────────────────────────────────────────────────────

class StubState:
    def __init__(self, path: Path, report: dict | None = None) -> None:
        self.path = path.resolve()
        self.report = report or {}

    def history(self, *, ref: str = "HEAD", limit: int = 12) -> dict:
        return {"snapshots": [], "windowSize": 0, "ref": ref}


@contextmanager
def run_handler_server(handler: type, host: str = "127.0.0.1"):
    server = ThreadingHTTPServer((host, 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _make_report(score: int, grade: str) -> dict:
    return {"architecture": {"health": {"score": score, "grade": grade}}}


# ── _build_badge_svg unit tests ──────────────────────────────────────────────

def test_badge_svg_contains_score_and_grade():
    svg = _build_badge_svg(70, "C").decode()
    assert "70 C" in svg
    assert "ArchMAP" in svg


def test_badge_svg_grade_a_is_green():
    svg = _build_badge_svg(95, "A").decode()
    assert "#4c1" in svg


def test_badge_svg_grade_b():
    svg = _build_badge_svg(80, "B").decode()
    assert "#a3c51c" in svg


def test_badge_svg_grade_c():
    svg = _build_badge_svg(65, "C").decode()
    assert "#dfb317" in svg


def test_badge_svg_grade_d():
    svg = _build_badge_svg(50, "D").decode()
    assert "#fe7d37" in svg


def test_badge_svg_grade_f():
    svg = _build_badge_svg(20, "F").decode()
    assert "#e05d44" in svg


def test_badge_svg_unknown_grade_fallback():
    svg = _build_badge_svg(0, "?").decode()
    assert "#9f9f9f" in svg


def test_badge_svg_is_valid_xml():
    svg = _build_badge_svg(70, "C").decode()
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")


# ── /api/badge endpoint tests ────────────────────────────────────────────────

def test_badge_endpoint_returns_svg(tmp_path):
    state = StubState(tmp_path, _make_report(70, "C"))
    static_dir = tmp_path
    handler = cli_server.build_http_handler(state, static_dir)

    with run_handler_server(handler) as base_url:
        with urlopen(f"{base_url}/api/badge") as resp:
            assert resp.status == 200
            content_type = resp.headers.get("Content-Type", "")
            assert "image/svg+xml" in content_type
            body = resp.read().decode()
            assert "70 C" in body
            assert "ArchMAP" in body


def test_badge_endpoint_no_cache_headers(tmp_path):
    state = StubState(tmp_path, _make_report(90, "A"))
    static_dir = tmp_path
    handler = cli_server.build_http_handler(state, static_dir)

    with run_handler_server(handler) as base_url:
        with urlopen(f"{base_url}/api/badge") as resp:
            cache_control = resp.headers.get("Cache-Control", "")
            assert "no-cache" in cache_control


def test_badge_endpoint_missing_health_uses_defaults(tmp_path):
    state = StubState(tmp_path, {})
    static_dir = tmp_path
    handler = cli_server.build_http_handler(state, static_dir)

    with run_handler_server(handler) as base_url:
        with urlopen(f"{base_url}/api/badge") as resp:
            assert resp.status == 200
            body = resp.read().decode()
            assert "100" in body
            assert "A" in body
