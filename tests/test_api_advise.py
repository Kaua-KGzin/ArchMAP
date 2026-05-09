from __future__ import annotations

import json
import threading
import urllib.error
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.request import Request, urlopen

from archmap.cli import server as cli_server


# ── helpers ──────────────────────────────────────────────────────────────────

class StubState:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.report = {"architecture": {"health": {"score": 70, "grade": "C"}}}

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


def post_json(url: str, payload: dict) -> tuple[int, dict | None]:
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


# ── /api/advise endpoint tests ────────────────────────────────────────────────

def _mock_ollama_response() -> MagicMock:
    data = {
        "choices": [{"message": {"content": "Refactor your god modules first."}}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 20},
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(data).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_advise_ollama_success(tmp_path):
    state = StubState(tmp_path)
    handler = cli_server.build_http_handler(state, tmp_path)

    with run_handler_server(handler) as base_url:
        with patch("urllib.request.urlopen", return_value=_mock_ollama_response()):
            status, data = post_json(
                f"{base_url}/api/advise",
                {"provider": "ollama", "model": "llama3", "base_url": "http://localhost:11434"},
            )

    assert status == 200
    assert data["status"] == "success"
    assert data["provider"] == "ollama"
    assert data["model"] == "llama3"
    assert "Refactor" in data["advice"]


def test_advise_default_provider_is_used_when_empty(tmp_path):
    state = StubState(tmp_path)
    handler = cli_server.build_http_handler(state, tmp_path)

    with run_handler_server(handler) as base_url:
        with patch("urllib.request.urlopen", return_value=_mock_ollama_response()):
            status, data = post_json(
                f"{base_url}/api/advise",
                {"provider": "ollama"},
            )

    assert status == 200
    assert data["provider"] == "ollama"


def test_advise_invalid_provider_returns_400(tmp_path):
    state = StubState(tmp_path)
    handler = cli_server.build_http_handler(state, tmp_path)

    with run_handler_server(handler) as base_url:
        status, data = post_json(f"{base_url}/api/advise", {"provider": "badprovider"})

    assert status == 400
    assert data["status"] == "error"
    assert "provider" in data["message"]


def test_advise_llm_error_returns_502(tmp_path):
    state = StubState(tmp_path)
    handler = cli_server.build_http_handler(state, tmp_path)

    with run_handler_server(handler) as base_url:
        with patch(
            "archmap.cli.server.advise_architecture",
            side_effect=RuntimeError("LLM API error 401: unauthorized"),
        ):
            status, data = post_json(f"{base_url}/api/advise", {"provider": "ollama"})

    assert status == 502
    assert data["status"] == "error"
    assert "401" in data["message"]


def test_advise_timeout_returns_504(tmp_path):
    state = StubState(tmp_path)
    handler = cli_server.build_http_handler(state, tmp_path)

    with run_handler_server(handler) as base_url:
        with patch(
            "archmap.cli.server.advise_architecture",
            side_effect=TimeoutError("timed out"),
        ):
            status, data = post_json(f"{base_url}/api/advise", {"provider": "ollama"})

    assert status == 504
    assert data["status"] == "error"


def test_advise_empty_body_uses_defaults(tmp_path):
    state = StubState(tmp_path)
    handler = cli_server.build_http_handler(state, tmp_path)

    with run_handler_server(handler) as base_url:
        with patch("urllib.request.urlopen", return_value=_mock_ollama_response()):
            status, data = post_json(f"{base_url}/api/advise", {"provider": "ollama"})

    assert status == 200
