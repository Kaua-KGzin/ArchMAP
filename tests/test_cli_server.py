from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from archmap.cli import server as cli_server


class StubState:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.report = {"path": str(self.path), "status": "initial"}
        self.reanalyze_calls = 0
        self.history_calls: list[tuple[str, int]] = []

    def set_path(self, new_path: Path) -> None:
        self.path = Path(new_path).resolve()
        self.report = {"path": str(self.path), "status": "updated"}

    def reanalyze(self) -> None:
        self.reanalyze_calls += 1
        self.report = {
            "path": str(self.path),
            "status": "reanalyzed",
            "count": self.reanalyze_calls,
        }

    def history(self, *, ref: str = "HEAD", limit: int = 12) -> dict:
        self.history_calls.append((ref, limit))
        return {
            "repoRoot": str(self.path),
            "ref": ref,
            "windowSize": 1,
            "snapshots": [],
        }


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


def request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
) -> tuple[int, dict | None]:
    body = None
    headers: dict[str, str] = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=body, method=method, headers=headers)
    try:
        with urlopen(request) as response:
            response_body = response.read().decode("utf-8")
            parsed = json.loads(response_body) if response_body else None
            return response.status, parsed
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8")
        parsed = json.loads(response_body) if response_body else None
        return exc.code, parsed


def test_report_state_from_path_and_reanalyze(monkeypatch, tmp_path) -> None:
    calls: list[Path] = []

    def fake_analyze_project(path: Path, **kwargs) -> dict:
        calls.append(Path(path))
        return {"analyzed": str(Path(path))}

    monkeypatch.setattr(cli_server, "analyze_project", fake_analyze_project)

    state = cli_server.ReportState.from_path(tmp_path)
    next_path = tmp_path / "nested"
    next_path.mkdir()

    state.set_path(next_path)

    assert state.path == next_path.resolve()
    assert state.report == {"analyzed": str(next_path.resolve())}
    assert calls == [tmp_path.resolve(), next_path.resolve()]


def test_resolve_static_dir_prefers_frozen_bundle(monkeypatch, tmp_path) -> None:
    bundle_root = tmp_path / "bundle"
    static_dir = bundle_root / "web-ui" / "static"
    static_dir.mkdir(parents=True)

    monkeypatch.setattr(cli_server.sys, "frozen", True, raising=False)
    monkeypatch.setattr(cli_server.sys, "_MEIPASS", str(bundle_root), raising=False)

    assert cli_server.resolve_static_dir() == static_dir


def test_resolve_static_dir_prefers_packaged_resource(monkeypatch, tmp_path) -> None:
    packaged_static = tmp_path / "web-ui" / "static"
    packaged_static.mkdir(parents=True)

    monkeypatch.setattr(cli_server.sys, "frozen", False, raising=False)
    monkeypatch.delattr(cli_server.sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(cli_server.importlib.resources, "files", lambda _name: tmp_path)

    assert cli_server.resolve_static_dir() == packaged_static


def test_resolve_static_dir_falls_back_to_source_checkout(monkeypatch) -> None:
    fallback = Path(cli_server.__file__).resolve().parents[1] / "web-ui" / "static"

    monkeypatch.setattr(cli_server.sys, "frozen", False, raising=False)
    monkeypatch.delattr(cli_server.sys, "_MEIPASS", raising=False)

    def raise_type_error(_name: str):
        raise TypeError("resource access unavailable")

    monkeypatch.setattr(cli_server.importlib.resources, "files", raise_type_error)

    assert cli_server.resolve_static_dir() == fallback


def test_server_helpers_handle_browser_hosts() -> None:
    assert cli_server.can_open_browser("localhost") is True
    assert cli_server.can_open_browser("10.0.0.4") is False
    assert cli_server.browser_host("0.0.0.0") == "localhost"
    assert cli_server.browser_host("::") == "localhost"
    assert cli_server.browser_host("127.0.0.1") == "127.0.0.1"


def test_build_http_handler_serves_core_endpoints(tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    state = StubState(tmp_path / "project")
    handler = cli_server.build_http_handler(state, static_dir)

    with run_handler_server(handler) as base_url:
        status, graph = request_json(f"{base_url}/api/graph")
        assert status == 200
        assert graph == state.report

        status, project = request_json(f"{base_url}/api/project")
        assert status == 200
        assert project == {"path": str(state.path)}

        status, health = request_json(f"{base_url}/api/health")
        assert status == 200
        assert health == {"status": "ok"}

        status, history = request_json(f"{base_url}/api/history?limit=3&ref=HEAD")
        assert status == 200
        assert history == {
            "repoRoot": str(state.path),
            "ref": "HEAD",
            "windowSize": 1,
            "snapshots": [],
        }
        assert state.history_calls == [("HEAD", 3)]

        with urlopen(f"{base_url}/") as response:
            assert response.status == 200
            assert response.read().decode("utf-8") == "<html>ok</html>"


def test_build_http_handler_updates_project_and_reanalyzes(tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    state = StubState(tmp_path / "project")
    handler = cli_server.build_http_handler(state, static_dir)
    next_path = tmp_path / "next-project"
    next_path.mkdir()

    with run_handler_server(handler) as base_url:
        status, payload = request_json(
            f"{base_url}/api/project",
            method="POST",
            payload={"path": str(next_path)},
        )
        assert status == 200
        assert payload == {"status": "success", "path": str(next_path.resolve())}
        assert state.path == next_path.resolve()

        status, payload = request_json(f"{base_url}/api/reanalyze", method="POST")
        assert status == 200
        assert payload == {"status": "success", "path": str(next_path.resolve())}
        assert state.reanalyze_calls == 1
        assert state.report["status"] == "reanalyzed"


def test_build_http_handler_requires_project_path(tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    state = StubState(tmp_path / "project")
    handler = cli_server.build_http_handler(state, static_dir)

    with run_handler_server(handler) as base_url:
        status, payload = request_json(
            f"{base_url}/api/project",
            method="POST",
            payload={},
        )

    assert status == 400
    assert payload == {"status": "error", "message": "body.path is required"}


def test_build_http_handler_open_project_supports_cancel_and_success(tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    state = StubState(tmp_path / "project")
    handler = cli_server.build_http_handler(state, static_dir)

    handler._pick_directory = lambda self: (None, None)
    with run_handler_server(handler) as base_url:
        request = Request(f"{base_url}/api/open", data=b"", method="POST")
        with urlopen(request) as response:
            assert response.status == 204
            assert response.read() == b""

    next_path = tmp_path / "selected-project"
    next_path.mkdir()
    handler = cli_server.build_http_handler(state, static_dir)
    handler._pick_directory = lambda self: (next_path, None)
    with run_handler_server(handler) as base_url:
        status, payload = request_json(f"{base_url}/api/open", method="POST", payload={})

    assert status == 200
    assert payload == {"status": "success", "path": str(next_path.resolve())}
    assert state.path == next_path.resolve()


def test_build_http_handler_open_project_reports_picker_failure(tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    state = StubState(tmp_path / "project")
    handler = cli_server.build_http_handler(state, static_dir)
    message = (
        "Native folder picker unavailable in this environment. "
        "Enter the project path manually."
    )
    handler._pick_directory = lambda self: (
        None,
        message,
    )

    with run_handler_server(handler) as base_url:
        status, payload = request_json(f"{base_url}/api/open", method="POST", payload={})

    assert status == 501
    assert payload == {
        "status": "unsupported",
        "mode": "manual_path",
        "message": message,
    }


def test_build_http_handler_opens_selected_file_node(tmp_path, monkeypatch) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    project_root = tmp_path / "project"
    source_dir = project_root / "src"
    source_dir.mkdir(parents=True)
    target_file = source_dir / "app.py"
    target_file.write_text("print('ok')\n", encoding="utf-8")

    state = StubState(project_root)
    state.report = {
        "projectRoot": str(project_root),
        "nodes": [
            {
                "id": "src/app.py",
                "label": "app.py",
                "type": "file",
                "folder": "src",
            }
        ],
        "edges": [],
    }
    opened_paths: list[Path] = []
    monkeypatch.setattr(cli_server, "_open_local_path", lambda target: opened_paths.append(target))
    handler = cli_server.build_http_handler(state, static_dir)

    with run_handler_server(handler) as base_url:
        status, payload = request_json(
            f"{base_url}/api/open-file",
            method="POST",
            payload={"nodeId": "src/app.py"},
        )

    assert status == 200
    assert payload == {"status": "success", "path": str(target_file.resolve())}
    assert opened_paths == [target_file.resolve()]


def test_build_http_handler_rejects_nonexistent_path_in_set_project(tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    state = StubState(tmp_path / "project")
    handler = cli_server.build_http_handler(state, static_dir)

    with run_handler_server(handler) as base_url:
        status, payload = request_json(
            f"{base_url}/api/project",
            method="POST",
            payload={"path": str(tmp_path / "does-not-exist")},
        )

    assert status == 400
    assert payload["status"] == "error"
    assert "directory" in payload["message"]


def test_build_http_handler_rejects_file_path_in_set_project(tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    file_path = tmp_path / "somefile.py"
    file_path.write_text("x = 1\n", encoding="utf-8")
    state = StubState(tmp_path / "project")
    handler = cli_server.build_http_handler(state, static_dir)

    with run_handler_server(handler) as base_url:
        status, payload = request_json(
            f"{base_url}/api/project",
            method="POST",
            payload={"path": str(file_path)},
        )

    assert status == 400
    assert payload["status"] == "error"
    assert "directory" in payload["message"]


def test_build_http_handler_reanalyze_rate_limited(tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    state = StubState(tmp_path / "project")
    handler = cli_server.build_http_handler(state, static_dir)

    with run_handler_server(handler) as base_url:
        status1, _ = request_json(f"{base_url}/api/reanalyze", method="POST")
        status2, payload2 = request_json(f"{base_url}/api/reanalyze", method="POST")

    assert status1 == 200
    assert status2 == 429
    assert payload2["status"] == "error"
    assert "rate limit" in payload2["message"]


def test_build_http_handler_reanalyze_error_path(tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()

    class ErrorState(StubState):
        def reanalyze(self) -> None:
            raise RuntimeError("disk full")

    state = ErrorState(tmp_path / "project")
    handler = cli_server.build_http_handler(state, static_dir)

    with run_handler_server(handler) as base_url:
        status, payload = request_json(f"{base_url}/api/reanalyze", method="POST")

    assert status == 500
    assert payload["status"] == "error"
    assert "disk full" in payload["message"]


def test_build_http_handler_set_project_error_path(tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    class ErrorState(StubState):
        def set_path(self, new_path) -> None:
            raise RuntimeError("cannot read")

    state = ErrorState(project_dir)
    handler = cli_server.build_http_handler(state, static_dir)

    with run_handler_server(handler) as base_url:
        status, payload = request_json(
            f"{base_url}/api/project",
            method="POST",
            payload={"path": str(project_dir)},
        )

    assert status == 500
    assert payload["status"] == "error"
    assert "cannot read" in payload["message"]


def test_build_http_handler_history_error_path(tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()

    class ErrorState(StubState):
        def history(self, *, ref="HEAD", limit=12):
            raise RuntimeError("no git repo")

    state = ErrorState(tmp_path / "project")
    handler = cli_server.build_http_handler(state, static_dir)

    with run_handler_server(handler) as base_url:
        status, payload = request_json(f"{base_url}/api/history", method="GET")

    assert status == 500
    assert payload["status"] == "error"
    assert "no git repo" in payload["message"]


def test_build_http_handler_unknown_post_returns_404(tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    state = StubState(tmp_path / "project")
    handler = cli_server.build_http_handler(state, static_dir)

    with run_handler_server(handler) as base_url:
        request = Request(f"{base_url}/api/unknown-endpoint", data=b"", method="POST")
        try:
            with __import__("urllib.request", fromlist=["urlopen"]).urlopen(request):
                pass
        except __import__("urllib.error", fromlist=["HTTPError"]).HTTPError as exc:
            status = exc.code

    assert status == 404


def test_build_http_handler_history_cache_hit(tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    history_calls: list[tuple[str, int]] = []

    class CachingState(StubState):
        def __init__(self, path):
            super().__init__(path)
            self._cache: dict = {}

        def history(self, *, ref="HEAD", limit=12):
            key = (ref, limit)
            if key not in self._cache:
                history_calls.append((ref, limit))
                self._cache[key] = super().history(ref=ref, limit=limit)
            return self._cache[key]

    state = CachingState(tmp_path / "project")
    handler = cli_server.build_http_handler(state, static_dir)

    with run_handler_server(handler) as base_url:
        request_json(f"{base_url}/api/history?ref=HEAD&limit=5")
        request_json(f"{base_url}/api/history?ref=HEAD&limit=5")

    assert len(history_calls) == 1


def test_build_http_handler_security_headers_present(tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    state = StubState(tmp_path / "project")
    handler = cli_server.build_http_handler(state, static_dir)

    with run_handler_server(handler) as base_url:
        import urllib.request
        with urllib.request.urlopen(f"{base_url}/api/graph") as response:
            headers = dict(response.headers)

    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert "default-src 'self'" in headers.get("Content-Security-Policy", "")


def test_build_http_handler_open_project_error_on_set_path(tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    new_path = tmp_path / "next"
    new_path.mkdir()

    class ErrorState(StubState):
        def set_path(self, new_path) -> None:
            raise OSError("read-only filesystem")

    state = ErrorState(tmp_path / "project")
    handler = cli_server.build_http_handler(state, static_dir)
    handler._pick_directory = lambda self: (new_path, None)

    with run_handler_server(handler) as base_url:
        status, payload = request_json(f"{base_url}/api/open", method="POST", payload={})

    assert status == 500
    assert payload["status"] == "error"
    assert "read-only filesystem" in payload["message"]


def test_build_http_handler_open_file_error_on_open(tmp_path, monkeypatch) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    project_root = tmp_path / "project"
    source_dir = project_root / "src"
    source_dir.mkdir(parents=True)
    target_file = source_dir / "app.py"
    target_file.write_text("x = 1\n", encoding="utf-8")

    state = StubState(project_root)
    state.report = {
        "projectRoot": str(project_root),
        "nodes": [{"id": "src/app.py", "label": "app.py", "type": "file"}],
        "edges": [],
    }

    def raise_oserror(path):
        raise OSError("no editor found")

    monkeypatch.setattr(cli_server, "_open_local_path", raise_oserror)
    handler = cli_server.build_http_handler(state, static_dir)

    with run_handler_server(handler) as base_url:
        status, payload = request_json(
            f"{base_url}/api/open-file", method="POST", payload={"nodeId": "src/app.py"}
        )

    assert status == 500
    assert payload["status"] == "error"
    assert "no editor found" in payload["message"]


def test_build_http_handler_requires_valid_file_node_for_open_file(tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    project_root = tmp_path / "project"
    project_root.mkdir()
    state = StubState(project_root)
    state.report = {
        "projectRoot": str(project_root),
        "nodes": [
            {
                "id": "requests",
                "label": "requests",
                "type": "package",
            }
        ],
        "edges": [],
    }
    handler = cli_server.build_http_handler(state, static_dir)

    with run_handler_server(handler) as base_url:
        status, payload = request_json(
            f"{base_url}/api/open-file",
            method="POST",
            payload={},
        )
        assert status == 400
        assert payload == {"status": "error", "message": "body.nodeId is required"}

        status, payload = request_json(
            f"{base_url}/api/open-file",
            method="POST",
            payload={"nodeId": "requests"},
        )

    assert status == 404
    assert payload == {
        "status": "error",
        "message": "File node not found or unavailable: requests",
    }


def test_open_endpoints_forbidden_for_remote_clients(tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    state = StubState(tmp_path / "project")
    handler = cli_server.build_http_handler(state, static_dir)

    # Simulate a non-local client by patching _is_local_request on the class
    handler._is_local_request = lambda self: False  # type: ignore[method-assign]

    with run_handler_server(handler) as base_url:
        status_open, payload_open = request_json(f"{base_url}/api/open", method="POST")
        status_file, payload_file = request_json(f"{base_url}/api/open-file", method="POST")

    assert status_open == 403
    assert payload_open == {"status": "error", "message": "only available on localhost"}
    assert status_file == 403
    assert payload_file == {"status": "error", "message": "only available on localhost"}


def test_is_local_request_allows_loopback_addresses(tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    state = StubState(tmp_path / "project")
    handler = cli_server.build_http_handler(state, static_dir)

    for addr in ("127.0.0.1", "::1", "localhost"):
        instance = handler.__new__(handler)
        instance.client_address = (addr, 12345)
        assert instance._is_local_request() is True

    instance.client_address = ("192.168.1.10", 12345)
    assert instance._is_local_request() is False
