"""ArchMAP MCP Server — Model Context Protocol over stdio.

Exposes the ArchMAP analysis engine as a JSON-RPC 2.0 server so that
AI assistants (Claude Code, Cursor, Windsurf) can query the structural
context of a project before suggesting changes.

Transport: newline-delimited JSON over stdin/stdout.

Usage:
    archmap mcp [path]

Then register in ~/.claude/claude_desktop_config.json:
    {
      "mcpServers": {
        "archmap": {
          "command": "archmap",
          "args": ["mcp", "/path/to/project"]
        }
      }
    }
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from archmap import __version__
from archmap.core.parser.ts_engine import HAS_TREE_SITTER

# ---------------------------------------------------------------------------
# Result cache — avoids re-analyzing on every tool call
# ---------------------------------------------------------------------------

_cache: dict[str, Any] = {}
_cache_key: dict[str, float] = {}


def _config_mtime(project_path: str) -> float:
    try:
        return (Path(project_path) / ".archmap.toml").stat().st_mtime
    except OSError:
        return 0.0


def _get_analysis(project_path: str) -> Any:
    mtime = _config_mtime(project_path)
    if project_path not in _cache or _cache_key.get(project_path) != mtime:
        from archmap import analyze_project
        _cache[project_path] = analyze_project(project_path)
        _cache_key[project_path] = mtime
    return _cache[project_path]


def _invalidate(project_path: str) -> None:
    _cache.pop(project_path, None)
    _cache_key.pop(project_path, None)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _tool_get_architecture_summary(project_path: str) -> dict:
    result = _get_analysis(project_path)
    metrics = result.get("metrics", {})
    risks = result.get("risks", {})
    return {
        "projectPath": project_path,
        "healthScore": metrics.get("architectureHealthScore", 0),
        "totalFiles": metrics.get("filesAnalyzed", 0),
        "totalEdges": metrics.get("totalDependencies", 0),
        "cycleCount": metrics.get("circularDependencyCount", 0),
        "godModules": len(risks.get("god_modules", [])),
        "layerViolations": len(risks.get("layer_violations", [])),
        "dependencyExplosions": len(risks.get("dependency_explosions", [])),
        "resolutionRate": metrics.get("resolutionRate", None),
        "parserPrecision": "symbol" if HAS_TREE_SITTER else "file",
        "treeSitterAvailable": HAS_TREE_SITTER,
        "topRisks": risks.get("top_risk_files", [])[:5],
    }


def _tool_get_file_context(project_path: str, file: str) -> dict:
    result = _get_analysis(project_path)
    nodes: list[dict] = result.get("nodes", [])
    edges: list[dict] = result.get("edges", [])

    node = next((n for n in nodes if n["id"] == file or n["label"] == file), None)
    if node is None:
        # Fuzzy match on suffix
        node = next((n for n in nodes if n["id"].endswith(file) or file.endswith(n["id"])), None)
    if node is None:
        return {"error": f"File '{file}' not found in the dependency graph."}

    file_id = node["id"]
    outgoing = sorted({e["target"] for e in edges if e["source"] == file_id})
    incoming = sorted({e["source"] for e in edges if e["target"] == file_id})

    return {
        "file": file_id,
        "label": node.get("label", file_id),
        "language": node.get("language", "unknown"),
        "outgoing": outgoing,
        "outgoingCount": len(outgoing),
        "incoming": incoming,
        "incomingCount": len(incoming),
        "isCircular": node.get("isCircular", False),
        "instability": node.get("instability", None),
        "complexityScore": node.get("complexityScore", None),
    }


def _tool_impact_analysis(project_path: str, file: str) -> dict:
    result = _get_analysis(project_path)
    nodes: list[dict] = result.get("nodes", [])
    edges: list[dict] = result.get("edges", [])

    node = next((n for n in nodes if n["id"] == file or n["label"] == file), None)
    if node is None:
        node = next((n for n in nodes if n["id"].endswith(file) or file.endswith(n["id"])), None)
    if node is None:
        return {"error": f"File '{file}' not found in the dependency graph."}

    from archmap.core.analyzer.impact_analyzer import calculate_impact
    impact = calculate_impact(node["id"], edges)

    return {
        "file": node["id"],
        "impactedFiles": impact["impactedFiles"],
        "impactCount": impact["impactCount"],
        "risk": impact["risk"],
        "description": (
            f"Changing '{node['id']}' may affect {impact['impactCount']} "
            f"other file(s) — risk level: {impact['risk']}."
        ),
    }


def _tool_run_checks(project_path: str) -> dict:
    result = _get_analysis(project_path)
    risks = result.get("risks", {})
    metrics = result.get("metrics", {})

    cycles: list = result.get("cycles", [])
    god_modules: list = risks.get("god_modules", [])
    layer_violations: list = risks.get("layer_violations", [])
    explosions: list = risks.get("dependency_explosions", [])

    passed = not cycles and not god_modules and not layer_violations and not explosions
    return {
        "passed": passed,
        "healthScore": metrics.get("architectureHealthScore", 0),
        "cycles": cycles[:10],
        "cycleCount": len(cycles),
        "godModules": god_modules[:10],
        "godModuleCount": len(god_modules),
        "layerViolations": layer_violations[:10],
        "layerViolationCount": len(layer_violations),
        "dependencyExplosions": explosions[:10],
        "dependencyExplosionCount": len(explosions),
    }


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

_TOOLS = [
    {
        "name": "get_architecture_summary",
        "description": (
            "Returns a high-level architectural health summary for the project: "
            "health score, file count, cycle count, god modules, layer violations, "
            "and the top 5 riskiest files. Call this first to orient yourself."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Absolute path to the project root (default: server startup path).",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_file_context",
        "description": (
            "Returns the dependency context of a single file: which files it imports "
            "(outgoing) and which files import it (incoming). Use before editing a file "
            "to understand its blast radius and coupling."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "description": "Relative or absolute path of the file to inspect.",
                },
                "project_path": {
                    "type": "string",
                    "description": "Absolute path to the project root (default: server startup path).",
                },
            },
            "required": ["file"],
        },
    },
    {
        "name": "impact_analysis",
        "description": (
            "Computes the transitive blast radius of changing a file: all files that "
            "depend on it (directly or transitively). Use before refactoring to know "
            "what else might break."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "description": "Relative or absolute path of the file to analyze.",
                },
                "project_path": {
                    "type": "string",
                    "description": "Absolute path to the project root (default: server startup path).",
                },
            },
            "required": ["file"],
        },
    },
    {
        "name": "run_checks",
        "description": (
            "Runs all architectural quality checks (cycles, god modules, layer violations, "
            "dependency explosions) and returns a pass/fail report. Use in CI context or "
            "before opening a PR to confirm the change does not degrade architecture."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Absolute path to the project root (default: server startup path).",
                }
            },
            "required": [],
        },
    },
]


# ---------------------------------------------------------------------------
# JSON-RPC dispatch
# ---------------------------------------------------------------------------

def _ok(req_id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _dispatch(message: dict, default_path: str) -> dict | None:
    method: str = message.get("method", "")
    req_id: Any = message.get("id")
    params: dict = message.get("params") or {}

    # Notifications have no id and need no response
    if req_id is None and method in ("notifications/initialized",):
        return None

    if method == "initialize":
        return _ok(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "archmap", "version": __version__},
        })

    if method == "tools/list":
        return _ok(req_id, {"tools": _TOOLS})

    if method == "tools/call":
        tool_name: str = params.get("name", "")
        args: dict = params.get("arguments") or {}
        project_path = str(args.get("project_path") or default_path)

        try:
            if tool_name == "get_architecture_summary":
                data = _tool_get_architecture_summary(project_path)
            elif tool_name == "get_file_context":
                file = args.get("file", "")
                if not file:
                    return _err(req_id, -32602, "'file' argument is required")
                data = _tool_get_file_context(project_path, file)
            elif tool_name == "impact_analysis":
                file = args.get("file", "")
                if not file:
                    return _err(req_id, -32602, "'file' argument is required")
                data = _tool_impact_analysis(project_path, file)
            elif tool_name == "run_checks":
                data = _tool_run_checks(project_path)
            else:
                return _err(req_id, -32601, f"Unknown tool: '{tool_name}'")
        except Exception as exc:  # noqa: BLE001
            return _err(req_id, -32603, f"Tool execution failed: {exc}")

        return _ok(req_id, {
            "content": [{"type": "text", "text": json.dumps(data, indent=2)}],
        })

    if req_id is not None:
        return _err(req_id, -32601, f"Method not found: '{method}'")
    return None


# ---------------------------------------------------------------------------
# Server loop
# ---------------------------------------------------------------------------

def run_mcp_server(project_path: str) -> int:
    """Run the MCP server loop until stdin closes or KeyboardInterrupt."""
    resolved = str(Path(project_path).resolve())

    print(
        f"[archmap-mcp] Server started. Project: {resolved} | "
        f"Tree-sitter: {'enabled' if HAS_TREE_SITTER else 'disabled (regex fallback)'}",
        file=sys.stderr,
    )

    # Reconfigure stdout to line-buffered so responses flush immediately
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            error_resp = _err(None, -32700, f"Parse error: {exc}")
            print(json.dumps(error_resp), flush=True)
            continue

        resp = _dispatch(message, resolved)
        if resp is not None:
            print(json.dumps(resp), flush=True)

    return 0
