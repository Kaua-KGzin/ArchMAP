"""Tests for the MCP tools added in v1.4.0 (context, quality, findings, RE, audit)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from tests.binary_samples import build_elf

from archmap.cli import mcp_server
from archmap.cli.mcp_server import _dispatch, _resolve_inside


def _call(project: Path, name: str, **arguments: Any) -> dict[str, Any]:
    message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    response = _dispatch(message, str(project))
    assert response is not None
    return response


def _payload(response: dict[str, Any]) -> Any:
    assert "result" in response, response
    return json.loads(response["result"]["content"][0]["text"])


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    mcp_server._cache.clear()
    mcp_server._cache_key.clear()
    (tmp_path / "payments").mkdir()
    (tmp_path / "payments" / "webhook.py").write_text(
        "from payments import retry\n\n"
        "def handle_webhook(event):\n"
        "    return retry.with_backoff(process_event, event)\n"
    )
    (tmp_path / "payments" / "retry.py").write_text(
        "def with_backoff(fn, *args):\n    return fn(*args)\n"
    )
    (tmp_path / "payments" / "__init__.py").write_text("")
    (tmp_path / "users.py").write_text("def create_user(name):\n    return name\n")
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "tool").write_bytes(build_elf(e_type=2, stack_exec=True))
    return tmp_path


def test_get_relevant_context(project: Path) -> None:
    result = _payload(_call(project, "get_relevant_context", task="webhook retry backoff"))
    files = [item["file"] for item in result["files"]]
    assert files[0] == "payments/webhook.py"
    assert "payments/retry.py" in files
    assert "users.py" not in files
    top = result["files"][0]
    assert top["snippets"] and top["snippets"][0]["line"] >= 1
    assert result["usedTokens"] <= result["budgetTokens"]


def test_get_relevant_context_requires_task(project: Path) -> None:
    assert _call(project, "get_relevant_context", task=" ")["error"]["code"] == -32602


def test_analysis_quality_and_findings(project: Path) -> None:
    quality = _payload(_call(project, "get_analysis_quality"))
    assert quality["confidenceLevel"] == "high"
    assert "timingsMs" not in quality
    findings = _payload(_call(project, "list_findings", min_severity="critical"))
    assert findings == {"total": 0, "findings": []}


def test_inspect_hexdump_strings(project: Path) -> None:
    report = _payload(_call(project, "inspect_path", path="bin/tool"))
    assert report["format"]["format"] == "elf"
    assert "profile" not in report["entropy"]
    assert {f["category"] for f in report["findings"]} >= {"executable_stack", "no_pie"}

    inventory = _payload(_call(project, "inspect_path", path="."))
    assert inventory["byFormat"]["elf"] == 1

    dump = _payload(_call(project, "hexdump", path="bin/tool", length=16))
    assert dump["hexdump"].startswith("00000000  7f 45 4c 46")

    strings = _payload(_call(project, "extract_strings", path="bin/tool", interesting_only=False))
    assert any("ld-linux" in s["value"] for s in strings["strings"])


def test_file_tools_are_confined_to_project(
    project: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    outside = tmp_path_factory.mktemp("outside") / "secret.txt"
    outside.write_text("top secret")
    for name in ("inspect_path", "hexdump", "extract_strings"):
        response = _call(project, name, path=str(outside))
        assert "outside the project root" in response["error"]["message"]
    response = _call(project, "hexdump", path="../" + outside.parent.name + "/secret.txt")
    assert "error" in response
    if hasattr(os, "symlink"):
        link = project / "escape"
        try:
            link.symlink_to(outside)
        except OSError:
            return
        response = _call(project, "hexdump", path="escape")
        assert "outside the project root" in response["error"]["message"]


def test_resolve_inside_missing_file(project: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        _resolve_inside(str(project), "nope.bin")


def test_audit_project_tool(project: Path) -> None:
    (project / ".claude").mkdir()
    (project / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"defaultMode": "bypassPermissions"}})
    )
    result = _payload(_call(project, "audit_project"))
    assert [f["category"] for f in result["findings"]] == ["permissions_bypassed"]
