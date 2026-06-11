"""Regression tests for the v1.0.1 correctness, performance and security fixes."""
from __future__ import annotations

from pathlib import Path

from archmap.cli import server as cli_server
from archmap.core.advisor.llm_advisor import _build_prompt
from archmap.core.analyzer.impact_analyzer import build_dependents_map, calculate_impact
from archmap.core.parser import parse_project
from archmap.exporters.mermaid_exporter import _to_mermaid_label
from test_cli_server import StubState, request_json, run_handler_server

# ---------------------------------------------------------------------------
# tsconfig path-alias resolution (product feature)
# ---------------------------------------------------------------------------


def _deps(result: dict, file_id: str) -> set[str]:
    entry = next(f for f in result["parsedFiles"] if f["id"] == file_id)
    return {d["id"] for d in entry["dependencies"]}


def test_tsconfig_paths_alias_resolves_to_internal_file() -> None:
    files = {
        "tsconfig.json": (
            '{\n'
            '  // path aliases\n'
            '  "compilerOptions": {\n'
            '    "baseUrl": ".",\n'
            '    "paths": { "@app/*": ["src/*"] },\n'
            '  }\n'
            '}\n'
        ),
        "src/app.ts": 'import { thing } from "@app/utils/helper";\n',
        "src/utils/helper.ts": "export const thing = 1;\n",
    }
    result = parse_project(".", virtual_files=files)
    deps = _deps(result, "src/app.ts")
    assert "src/utils/helper.ts" in deps
    assert "pkg:@app/utils/helper" not in deps


def test_tsconfig_baseurl_resolves_bare_specifier() -> None:
    files = {
        "tsconfig.json": '{"compilerOptions": {"baseUrl": "src"}}',
        "src/app.ts": 'import x from "utils/helper";\n',
        "src/utils/helper.ts": "export default 1;\n",
    }
    result = parse_project(".", virtual_files=files)
    assert "src/utils/helper.ts" in _deps(result, "src/app.ts")


def test_without_tsconfig_bare_specifier_is_a_package() -> None:
    files = {"src/app.ts": 'import x from "@app/utils/helper";\n'}
    result = parse_project(".", virtual_files=files)
    # Scoped specifier degrades to the npm-style scoped package name.
    assert "pkg:@app/utils" in _deps(result, "src/app.ts")
    assert not any(d.startswith("src/") for d in _deps(result, "src/app.ts"))


def test_malformed_tsconfig_falls_back_gracefully() -> None:
    files = {
        "tsconfig.json": "{ this is not valid json",
        "src/app.ts": 'import x from "@app/x";\n',
    }
    result = parse_project(".", virtual_files=files)
    # No crash; bare specifier degrades to a package node.
    assert "pkg:@app/x" in _deps(result, "src/app.ts")


# ---------------------------------------------------------------------------
# Impact analysis performance fix (shared dependents map)
# ---------------------------------------------------------------------------


def test_impact_with_shared_map_matches_standalone() -> None:
    edges = [
        {"source": "a.py", "target": "b.py"},
        {"source": "b.py", "target": "c.py"},
        {"source": "d.py", "target": "c.py"},
    ]
    shared = build_dependents_map(edges)
    for node in ("a.py", "b.py", "c.py", "d.py"):
        assert calculate_impact(node, edges, shared) == calculate_impact(node, edges)


def test_impact_transitive_dependents() -> None:
    edges = [
        {"source": "a.py", "target": "b.py"},
        {"source": "b.py", "target": "c.py"},
    ]
    impact = calculate_impact("c.py", edges)
    assert impact["impactedFiles"] == ["a.py", "b.py"]
    assert impact["impactCount"] == 2


def test_impact_risk_levels() -> None:
    # 6 dependents -> warning, 11 dependents -> critical
    warning_edges = [{"source": f"f{i}.py", "target": "hub.py"} for i in range(6)]
    assert calculate_impact("hub.py", warning_edges)["risk"] == "warning"

    critical_edges = [{"source": f"f{i}.py", "target": "hub.py"} for i in range(11)]
    assert calculate_impact("hub.py", critical_edges)["risk"] == "critical"

    assert calculate_impact("hub.py", [])["risk"] == "low"


def test_tsconfig_exact_alias_without_wildcard() -> None:
    files = {
        "tsconfig.json": (
            '{"compilerOptions": {"paths": {"@config": ["src/config/index.ts"]}}}'
        ),
        "src/main.ts": 'import cfg from "@config";\n',
        "src/config/index.ts": "export default {};\n",
    }
    result = parse_project(".", virtual_files=files)
    assert "src/config/index.ts" in _deps(result, "src/main.ts")


def test_jsconfig_is_used_when_tsconfig_absent() -> None:
    files = {
        "jsconfig.json": '{"compilerOptions": {"baseUrl": "src"}}',
        "src/app.js": 'import x from "lib/util";\n',
        "src/lib/util.js": "module.exports = 1;\n",
    }
    result = parse_project(".", virtual_files=files)
    assert "src/lib/util.js" in _deps(result, "src/app.js")


# ---------------------------------------------------------------------------
# Mermaid label escaping
# ---------------------------------------------------------------------------


def test_mermaid_label_escapes_breaking_characters() -> None:
    label = _to_mermaid_label('a[b]{c}\nd"e<f>')
    assert "\n" not in label
    assert "[" not in label and "]" not in label
    assert "{" not in label and "}" not in label
    assert "<" not in label and ">" not in label
    assert label.startswith('"') and label.endswith('"')


# ---------------------------------------------------------------------------
# Advisor field-name bug (layer violations rendered correctly)
# ---------------------------------------------------------------------------


def test_advisor_prompt_renders_layer_violations() -> None:
    report = {
        "metrics": {},
        "architecture": {},
        "cycles": [],
        "risks": {
            "layer_violations": [
                {
                    "source": "src/utils/log.py",
                    "target": "src/cli/main.py",
                    "sourceLayer": "utils",
                    "targetLayer": "cli",
                }
            ]
        },
    }
    prompt = _build_prompt(report)
    assert "utils -> cli: src/utils/log.py" in prompt
    assert "None -> None" not in prompt


# ---------------------------------------------------------------------------
# Security: sensitive POST endpoints gated to loopback
# ---------------------------------------------------------------------------


def _non_local_handler(tmp_path: Path):
    static_dir = tmp_path / "static"
    static_dir.mkdir(exist_ok=True)
    state = StubState(tmp_path / "project")
    handler = cli_server.build_http_handler(state, static_dir)
    handler._is_local_request = lambda self: False  # type: ignore[method-assign]
    return handler, state


def test_set_project_blocked_for_non_local_request(tmp_path) -> None:
    handler, state = _non_local_handler(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    with run_handler_server(handler) as base_url:
        status, payload = request_json(
            f"{base_url}/api/project", method="POST", payload={"path": str(other)}
        )
    assert status == 403
    assert payload == {"status": "error", "message": "only available on localhost"}
    assert state.path == (tmp_path / "project").resolve()


def test_reanalyze_blocked_for_non_local_request(tmp_path) -> None:
    handler, state = _non_local_handler(tmp_path)
    with run_handler_server(handler) as base_url:
        status, _ = request_json(f"{base_url}/api/reanalyze", method="POST")
    assert status == 403
    assert state.reanalyze_calls == 0


def test_advise_blocked_for_non_local_request(tmp_path) -> None:
    handler, _ = _non_local_handler(tmp_path)
    with run_handler_server(handler) as base_url:
        status, _ = request_json(
            f"{base_url}/api/advise", method="POST", payload={"provider": "ollama"}
        )
    assert status == 403


def test_advise_rejects_non_http_base_url(tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    state = StubState(tmp_path / "project")
    state.report = {"architecture": {}, "metrics": {}, "risks": {}, "cycles": []}
    handler = cli_server.build_http_handler(state, static_dir)
    with run_handler_server(handler) as base_url:
        status, payload = request_json(
            f"{base_url}/api/advise",
            method="POST",
            payload={"provider": "custom", "base_url": "file:///etc/passwd"},
        )
    assert status == 400
    assert "base_url" in payload["message"]


# ---------------------------------------------------------------------------
# Loopback helper + base_url validator
# ---------------------------------------------------------------------------


def test_is_loopback_host() -> None:
    assert cli_server._is_loopback_host("127.0.0.1")
    assert cli_server._is_loopback_host("localhost")
    assert cli_server._is_loopback_host("::1")
    assert not cli_server._is_loopback_host("0.0.0.0")
    assert not cli_server._is_loopback_host("192.168.1.5")


def test_is_safe_base_url() -> None:
    assert cli_server._is_safe_base_url("http://localhost:11434")
    assert cli_server._is_safe_base_url("https://api.openai.com")
    assert not cli_server._is_safe_base_url("file:///etc/passwd")
    assert not cli_server._is_safe_base_url("gopher://evil")
    assert not cli_server._is_safe_base_url("")
    assert not cli_server._is_safe_base_url("not-a-url")


def test_default_host_is_loopback() -> None:
    from archmap.cli.defaults import DEFAULT_HOST

    assert DEFAULT_HOST == "127.0.0.1"
