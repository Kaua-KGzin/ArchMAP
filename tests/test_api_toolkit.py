"""Tests for the web UI toolkit endpoints: context, inspect, hexdump, strings, audit."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from tests.binary_samples import build_elf
from tests.test_cli_server import request_json, run_handler_server

from archmap.cli import server as cli_server


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "billing").mkdir(parents=True)
    (root / "billing" / "__init__.py").write_text("")
    (root / "billing" / "invoice.py").write_text(
        "from billing import tax\n\ndef invoice_total(items):\n    return tax.apply(sum(items))\n"
    )
    (root / "billing" / "tax.py").write_text("def apply(value):\n    return value * 1.1\n")
    (root / "bin").mkdir()
    (root / "bin" / "tool").write_bytes(build_elf(e_type=2, stack_exec=True))
    (root / "notes.bin").write_bytes(b"\x00\x01visit https://example.org/x\x00")
    return root


@pytest.fixture()
def base_url(project: Path, tmp_path: Path):  # type: ignore[no-untyped-def]
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    state = cli_server.ReportState.from_path(project)
    handler = cli_server.build_http_handler(state, static_dir)
    with run_handler_server(handler) as url:
        yield url


def _post(base_url: str, path: str, payload: dict) -> tuple[int, dict]:
    status, body = request_json(f"{base_url}{path}", method="POST", payload=payload)
    assert body is not None
    return status, body


def test_context_endpoint(base_url: str) -> None:
    status, body = _post(base_url, "/api/context", {"task": "invoice total tax", "budget": 2000})
    assert status == 200
    files = [item["file"] for item in body["result"]["files"]]
    assert files[0] == "billing/invoice.py"
    assert "billing/tax.py" in files
    status, body = _post(base_url, "/api/context", {"task": ""})
    assert status == 400


def test_inspect_file_and_directory(base_url: str) -> None:
    status, body = _post(base_url, "/api/inspect", {"path": "bin/tool"})
    assert status == 200
    report = body["result"]
    assert report["kind"] == "file"
    assert report["relativePath"] == "bin/tool"
    assert {f["category"] for f in report["findings"]} >= {"executable_stack", "no_pie"}

    status, body = _post(base_url, "/api/inspect", {"path": "."})
    assert status == 200
    assert body["result"]["kind"] == "directory"
    assert body["result"]["byFormat"]["elf"] == 1


def test_hexdump_endpoint(base_url: str) -> None:
    status, body = _post(base_url, "/api/hexdump", {"path": "bin/tool", "length": 16})
    assert status == 200
    assert body["result"]["hexdump"].startswith("00000000  7f 45 4c 46")
    status, body = _post(base_url, "/api/hexdump", {"path": "bin/tool", "offset": -16})
    assert body["result"]["offset"] == body["result"]["size"] - 16
    status, body = _post(base_url, "/api/hexdump", {"path": "bin"})
    assert status == 400


def test_strings_endpoint(base_url: str) -> None:
    status, body = _post(base_url, "/api/strings", {"path": "notes.bin"})
    assert status == 200
    assert body["result"]["interesting"][0]["categories"] == ["url"]
    status, body = _post(base_url, "/api/strings", {"path": "notes.bin", "interesting": False})
    assert body["result"]["strings"][0]["value"] == "visit https://example.org/x"


def test_audit_endpoint(base_url: str, project: Path) -> None:
    (project / ".claude").mkdir()
    (project / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": ["Bash(*)"]}})
    )
    status, body = _post(base_url, "/api/audit", {})
    assert status == 200
    assert [f["id"] for f in body["result"]["findings"]] == ["AGENT-001"]


def test_paths_outside_project_are_refused(base_url: str, tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("x")
    for endpoint in ("/api/inspect", "/api/hexdump", "/api/strings"):
        status, body = _post(base_url, endpoint, {"path": str(secret)})
        assert status == 400
        assert "outside the project root" in body["message"]
    status, body = _post(base_url, "/api/inspect", {"path": "../secret.txt"})
    assert status == 400


def test_post_requires_json_content_type(base_url: str) -> None:
    """A cross-site form/`no-cors` POST can't set application/json (CSRF guard)."""
    request = Request(
        f"{base_url}/api/audit",
        data=b"{}",
        method="POST",
        headers={"Content-Type": "text/plain"},
    )
    with pytest.raises(HTTPError) as excinfo:
        urlopen(request)
    assert excinfo.value.code == 415


def test_toolkit_endpoints_are_local_only(project: Path, tmp_path: Path) -> None:
    static_dir = tmp_path / "static2"
    static_dir.mkdir()
    state = cli_server.ReportState.from_path(project)
    handler = cli_server.build_http_handler(state, static_dir)
    handler._is_local_request = lambda self: False  # type: ignore[method-assign]
    with run_handler_server(handler) as url:
        for endpoint in ("/api/context", "/api/inspect", "/api/audit"):
            status, _ = request_json(f"{url}{endpoint}", method="POST", payload={"path": "."})
            assert status == 403


def test_bounded_int() -> None:
    assert cli_server._bounded_int(None, 5, 1, 10) == 5
    assert cli_server._bounded_int("abc", 5, 1, 10) == 5
    assert cli_server._bounded_int(99, 5, 1, 10) == 10
    assert cli_server._bounded_int(-3, 5, 1, 10) == 1
