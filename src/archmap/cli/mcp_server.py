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
_cache_key: dict[str, str] = {}


def _fingerprint(project_path: str) -> str:
    # Same fingerprint archmap's on-disk cache uses (config + every source
    # file's mtime/size) — catches source edits, not just .archmap.toml
    # changes, so a long-lived MCP session doesn't serve stale data after
    # the AI assistant edits files.
    from archmap.cache import compute_fingerprint
    from archmap.config import load_project_config

    root = Path(project_path).resolve()
    config = load_project_config(root)
    return compute_fingerprint(root, config)


def _get_analysis(project_path: str) -> Any:
    fingerprint = _fingerprint(project_path)
    if project_path not in _cache or _cache_key.get(project_path) != fingerprint:
        from archmap import analyze_project
        _cache[project_path] = analyze_project(project_path)
        _cache_key[project_path] = fingerprint
    return _cache[project_path]


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

    node = next((n for n in nodes if n["id"] == file or n["label"] == file), None)
    if node is None:
        node = next((n for n in nodes if n["id"].endswith(file) or file.endswith(n["id"])), None)
    if node is None:
        return {"error": f"File '{file}' not found in the dependency graph."}

    # Every node — file or package — already carries a precomputed impact
    # field from analyze_graph(); no need to recompute it here.
    impact = node.get("impact") or {"impactedFiles": [], "impactCount": 0, "risk": "low"}

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


def _tool_trace_reachability(project_path: str, entrypoint: str, max_depth: int | None) -> dict:
    result = _get_analysis(project_path)
    from archmap.core.analyzer.reachability_analyzer import trace_reachability

    return trace_reachability(result, entrypoint, max_depth=max_depth)


def _tool_diff_architecture(
    project_path: str, repo: str, base_ref: str, head_ref: str
) -> dict:
    from archmap.core.analyzer import analyze_git_ref, diff_reports

    repo_path = repo or project_path
    base_report = analyze_git_ref(repo_path, base_ref)
    base_report["ref"] = base_ref
    head_report = analyze_git_ref(repo_path, head_ref)
    head_report["ref"] = head_ref
    return diff_reports(base_report, head_report)


def _tool_get_network_exposure(
    project_path: str,
    target: str,
    ports: str | None,
    top_ports: int | None,
    use_nmap: bool | None,
    timeout: float,
) -> dict:
    from archmap.config import load_project_config
    from archmap.core.exposure import correlate_exposure
    from archmap.core.exposure.endpoint_scanner import scan_endpoint_references
    from archmap.core.netscan import run_netscan

    scan_result = run_netscan(
        target,
        ports_spec=ports,
        top_ports=top_ports,
        use_nmap=use_nmap,
        timeout=timeout,
    )
    analysis_result = _get_analysis(project_path)
    config = load_project_config(project_path)
    endpoint_refs = scan_endpoint_references(project_path, config)
    return correlate_exposure(
        scan_result, analysis_result, endpoint_refs, config["network"]["rules"]
    )


def _tool_get_project_memory(project_path: str) -> dict:
    from archmap.core.memory import generate_memory_digest

    result = _get_analysis(project_path)
    return {"memory": generate_memory_digest(result)}


def _resolve_inside(project_path: str, user_path: str) -> Path:
    """Resolve ``user_path`` against the project root and refuse anything outside it.

    File-reading tools (inspect, hexdump, strings) take paths from the model,
    and a prompt-injected model could ask for ``~/.ssh/id_rsa``. Symlinks are
    resolved first, so a link inside the project can't point the tool outside.
    """
    root = Path(project_path).resolve()
    candidate = Path(user_path)
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(
            f"'{user_path}' is outside the project root {root}; start `archmap mcp` "
            "in a directory that contains it"
        )
    if not resolved.exists():
        raise ValueError(f"'{user_path}' does not exist")
    return resolved


def _tool_get_relevant_context(
    project_path: str, task: str, budget_tokens: int, max_files: int
) -> dict:
    from archmap.core.context.relevance import rank_relevant_files

    return rank_relevant_files(
        _get_analysis(project_path),
        task,
        budget_tokens=max(500, min(int(budget_tokens), 200_000)),
        max_files=max(1, min(int(max_files), 50)),
    )


def _tool_get_analysis_quality(project_path: str) -> dict:
    result = _get_analysis(project_path)
    quality = dict(result.get("metrics", {}).get("analysisQuality", {}))
    quality.pop("timingsMs", None)
    return quality


def _tool_list_findings(
    project_path: str, domain: str | None, min_severity: str | None, limit: int
) -> dict:
    from archmap.core.analyzer.findings import SEVERITY_LEVELS

    findings = list(_get_analysis(project_path).get("findings", []))
    if domain:
        findings = [f for f in findings if f.get("domain") == domain]
    if min_severity in SEVERITY_LEVELS:
        floor = SEVERITY_LEVELS.index(str(min_severity))
        findings = [
            f for f in findings if SEVERITY_LEVELS.index(f.get("severity", "info")) >= floor
        ]
    return {"total": len(findings), "findings": findings[: max(1, min(int(limit), 500))]}


def _tool_inspect_path(project_path: str, path: str, include_strings: bool) -> dict:
    from archmap.core.binary.analyzer import inspect_file
    from archmap.core.inspect.inventory import inspect_directory

    target = _resolve_inside(project_path, path)
    if target.is_dir():
        result = inspect_directory(target, max_files=2000, include_strings=False)
        result["binaries"] = result["binaries"][:200]
        return result
    report = inspect_file(target, include_strings=include_strings, max_interesting_strings=50)
    # The per-block profile is for plotting; agents only need the summary numbers.
    report["entropy"] = {k: v for k, v in report["entropy"].items() if k != "profile"}
    return report


def _tool_hexdump(project_path: str, path: str, offset: int, length: int) -> dict:
    from archmap.core.binary.hexdump import hexdump
    from archmap.core.binary.reader import open_binary

    target = _resolve_inside(project_path, path)
    if not target.is_file():
        raise ValueError(f"'{path}' is not a file")
    with open_binary(target) as data:
        size = len(data)
        dump = hexdump(data, offset=int(offset), length=max(1, min(int(length), 4096)))
    return {"file": str(target), "size": size, "hexdump": dump}


def _tool_extract_strings(
    project_path: str, path: str, min_length: int, interesting_only: bool, limit: int
) -> dict:
    from archmap.core.binary.reader import open_binary
    from archmap.core.binary.strings import analyze_strings, extract_strings

    target = _resolve_inside(project_path, path)
    if not target.is_file():
        raise ValueError(f"'{path}' is not a file")
    cap = max(1, min(int(limit), 1000))
    with open_binary(target) as data:
        if interesting_only:
            return analyze_strings(data, min_length=int(min_length), max_interesting=cap)
        found = extract_strings(data, min_length=int(min_length), limit=cap)
    return {"file": str(target), "strings": found, "truncated": len(found) >= cap}


def _tool_audit_project(project_path: str) -> dict:
    from archmap.core.audit.project_audit import audit_project

    return audit_project(project_path)


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

_PROJECT_PATH_SCHEMA = {
    "type": "string",
    "description": "Absolute path to the project root (default: server startup path).",
}

_TOOLS = [
    {
        "name": "get_project_memory",
        "description": (
            "Returns a compact markdown digest of the project's architecture — health "
            "score, top risk files, cycles, layer/rule violations — the same content "
            "'archmap memory' writes to .archmap/memory.md. Call this first, before "
            "exploring the codebase with file reads or grep: it's a pre-computed "
            "snapshot that answers 'what's the state of this codebase' in one call "
            "instead of many, and stays cheap on repeat calls via the same fingerprint "
            "cache 'archmap analyze' uses."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": (
                        "Absolute path to the project root "
                        "(default: server startup path)."
                    ),
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_architecture_summary",
        "description": (
            "Returns a high-level architectural health summary for the project as "
            "structured JSON: health score, file count, cycle count, god modules, "
            "layer violations, and the top 5 riskiest files. Prefer 'get_project_memory' "
            "for a broader prose digest; use this when you need the numbers as data."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": (
                        "Absolute path to the project root "
                        "(default: server startup path)."
                    ),
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
                    "description": (
                        "Absolute path to the project root "
                        "(default: server startup path)."
                    ),
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
            "what else might break. Also works on external package dependencies "
            "(pass e.g. 'pkg:redis') to see which files depend on that package."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "description": (
                        "Relative or absolute path of the file to analyze, or a "
                        "package node id like 'pkg:redis'."
                    ),
                },
                "project_path": {
                    "type": "string",
                    "description": (
                        "Absolute path to the project root "
                        "(default: server startup path)."
                    ),
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
                    "description": (
                        "Absolute path to the project root "
                        "(default: server startup path)."
                    ),
                }
            },
            "required": [],
        },
    },
    {
        "name": "trace_reachability",
        "description": (
            "BFS from an entrypoint file through all its outgoing dependency edges: "
            "every file that entrypoint transitively pulls in, plus coverage stats. "
            "Use to understand what a given entrypoint actually depends on, or to spot "
            "dead code (files never reached from any known entrypoint)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "entrypoint": {
                    "type": "string",
                    "description": "Relative path or name of the entrypoint file.",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Only include files reachable within this many hops.",
                },
                "project_path": {
                    "type": "string",
                    "description": (
                        "Absolute path to the project root "
                        "(default: server startup path)."
                    ),
                },
            },
            "required": ["entrypoint"],
        },
    },
    {
        "name": "diff_architecture",
        "description": (
            "Compares architecture between two git refs (default HEAD~1 vs HEAD): "
            "health/complexity/cycle deltas, added/removed dependency edges, and "
            "per-file changes. Use before opening a PR to check whether a change "
            "degrades the architecture relative to its base."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "base_ref": {
                    "type": "string",
                    "description": "Base git ref to compare from (default: HEAD~1).",
                },
                "head_ref": {
                    "type": "string",
                    "description": "Head git ref to compare to (default: HEAD).",
                },
                "repo": {
                    "type": "string",
                    "description": (
                        "Path to the git repository (default: project_path/server "
                        "startup path)."
                    ),
                },
                "project_path": {
                    "type": "string",
                    "description": (
                        "Absolute path to the project root "
                        "(default: server startup path)."
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_network_exposure",
        "description": (
            "Scans a network target and cross-references open ports/services against "
            "this project's dependency graph: if an open port's service (e.g. Redis, "
            "PostgreSQL, MongoDB) matches a package the code actually imports, returns "
            "that package's blast radius alongside the port's network risk rating. Each "
            "finding carries a confidence score — an exact host:port literal found in "
            "the codebase (env files, connection URIs) scores much higher than a bare "
            "service-name-to-import guess — and, when '.archmap.toml' declares "
            "'[network.rules]', flags drift when a high-confidence connection violates "
            "a declared forbid/allow rule. IMPORTANT: only scan networks/hosts you own "
            "or are explicitly authorized to test — unauthorized scanning may be illegal."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": (
                        "Host/IP, hostname, CIDR block, or range to scan "
                        "(e.g. 192.168.1.10, 192.168.1.0/24, 192.168.1.1-50)."
                    ),
                },
                "ports": {
                    "type": "string",
                    "description": "Ports to scan, e.g. '22,80,443' or '1-1024'.",
                },
                "top_ports": {
                    "type": "integer",
                    "description": "Scan the N most common ports instead of 'ports'.",
                },
                "use_nmap": {
                    "type": "boolean",
                    "description": (
                        "Force the system nmap binary as the scan engine. "
                        "Default: used automatically when nmap is installed."
                    ),
                },
                "timeout": {
                    "type": "number",
                    "description": "Per-connection timeout in seconds (default: 1.0).",
                },
                "project_path": {
                    "type": "string",
                    "description": (
                        "Absolute path to the project root "
                        "(default: server startup path)."
                    ),
                },
            },
            "required": ["target"],
        },
    },
    {
        "name": "get_relevant_context",
        "description": (
            "Given a task description, returns the files to read for it, in order, "
            "packed into a token budget: BM25 over identifier-aware tokens (path "
            "segments weigh more), plus the direct imports/dependents of each match "
            "from the dependency graph. Each file comes with why it was picked, its "
            "blast radius, and its best-matching lines — often enough to skip reading "
            "it. Call this before exploring the codebase for a task."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "What you are about to do; include identifiers if known.",
                },
                "budget_tokens": {
                    "type": "integer",
                    "description": "Approximate tokens you can spend reading files (default 8000).",
                },
                "max_files": {"type": "integer", "description": "Maximum files (default 15)."},
                "project_path": _PROJECT_PATH_SCHEMA,
            },
            "required": ["task"],
        },
    },
    {
        "name": "get_analysis_quality",
        "description": (
            "How complete the dependency graph is: files discovered vs. parsed, parse "
            "and decode failures, oversized files skipped, per-language import "
            "resolution, and an overall confidence (high/medium/low). Check this before "
            "trusting 'no dependents' or a small blast radius."
        ),
        "inputSchema": {"type": "object", "properties": {"project_path": _PROJECT_PATH_SCHEMA}},
    },
    {
        "name": "list_findings",
        "description": (
            "All unified findings with stable IDs: ARCH-* (cycles, god modules, layer "
            "and rule violations) and QUAL-* (parse failures, low resolution). Filter "
            "by domain ('code' or 'quality') and minimum severity."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "enum": ["code", "quality"]},
                "min_severity": {
                    "type": "string",
                    "enum": ["info", "low", "medium", "high", "critical"],
                },
                "limit": {"type": "integer", "description": "Maximum findings (default 100)."},
                "project_path": _PROJECT_PATH_SCHEMA,
            },
        },
    },
    {
        "name": "inspect_path",
        "description": (
            "Static reverse-engineering inspection of a file or directory inside the "
            "project. Files: format identification (ELF, PE, Mach-O, WASM, APK/JAR, "
            "SQLite, archives, JSON/CSV, ...), hashes, headers, linked libraries, "
            "imports/exports, mitigations (NX/PIE/RELRO/canary, ASLR/DEP/CFG), packer "
            "hints, entropy, classified strings, data schema, and BIN-* findings. "
            "Directories: file inventory plus a binary-to-library linkage graph. "
            "Nothing is executed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File or directory (relative to the project root).",
                },
                "include_strings": {
                    "type": "boolean",
                    "description": "Extract and classify strings (default true).",
                },
                "project_path": _PROJECT_PATH_SCHEMA,
            },
            "required": ["path"],
        },
    },
    {
        "name": "hexdump",
        "description": (
            "Hex + ASCII dump of a byte range of a file inside the project (max 4096 "
            "bytes). Negative offsets count from the end of the file."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "offset": {"type": "integer", "description": "Start offset (default 0)."},
                "length": {"type": "integer", "description": "Bytes to dump (default 256)."},
                "project_path": _PROJECT_PATH_SCHEMA,
            },
            "required": ["path"],
        },
    },
    {
        "name": "extract_strings",
        "description": (
            "Printable ASCII/UTF-16LE strings from a file inside the project. With "
            "interesting_only (default), returns only URLs, IPs, paths, registry keys, "
            "crypto/toolchain markers, and secrets (redacted), with category counts."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "min_length": {"type": "integer", "description": "Minimum length (default 4)."},
                "interesting_only": {"type": "boolean", "description": "Default true."},
                "limit": {"type": "integer", "description": "Maximum strings (default 200)."},
                "project_path": _PROJECT_PATH_SCHEMA,
            },
            "required": ["path"],
        },
    },
    {
        "name": "audit_project",
        "description": (
            "Offline audit: secrets in project files (git-aware; committed secrets rank "
            "higher; values redacted) as SEC-* findings, and AI-agent configuration "
            "risks as AGENT-* findings — insecure or unpinned MCP servers, plaintext "
            "tokens, bypassed/broad permissions, hooks that pipe downloads into a "
            "shell, and invisible Unicode in CLAUDE.md/AGENTS.md/.cursorrules."
        ),
        "inputSchema": {"type": "object", "properties": {"project_path": _PROJECT_PATH_SCHEMA}},
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
            if tool_name == "get_project_memory":
                data = _tool_get_project_memory(project_path)
            elif tool_name == "get_architecture_summary":
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
            elif tool_name == "trace_reachability":
                entrypoint = args.get("entrypoint", "")
                if not entrypoint:
                    return _err(req_id, -32602, "'entrypoint' argument is required")
                data = _tool_trace_reachability(project_path, entrypoint, args.get("max_depth"))
            elif tool_name == "diff_architecture":
                data = _tool_diff_architecture(
                    project_path,
                    args.get("repo") or project_path,
                    args.get("base_ref") or "HEAD~1",
                    args.get("head_ref") or "HEAD",
                )
            elif tool_name == "get_network_exposure":
                target = args.get("target", "")
                if not target:
                    return _err(req_id, -32602, "'target' argument is required")
                data = _tool_get_network_exposure(
                    project_path,
                    target,
                    args.get("ports"),
                    args.get("top_ports"),
                    args.get("use_nmap"),
                    args.get("timeout", 1.0),
                )
            elif tool_name == "get_relevant_context":
                task = str(args.get("task", "")).strip()
                if not task:
                    return _err(req_id, -32602, "'task' argument is required")
                data = _tool_get_relevant_context(
                    project_path, task, args.get("budget_tokens", 8000), args.get("max_files", 15)
                )
            elif tool_name == "get_analysis_quality":
                data = _tool_get_analysis_quality(project_path)
            elif tool_name == "list_findings":
                data = _tool_list_findings(
                    project_path, args.get("domain"), args.get("min_severity"),
                    args.get("limit", 100),
                )
            elif tool_name in ("inspect_path", "hexdump", "extract_strings"):
                path = str(args.get("path", ""))
                if not path:
                    return _err(req_id, -32602, "'path' argument is required")
                if tool_name == "inspect_path":
                    data = _tool_inspect_path(
                        project_path, path, bool(args.get("include_strings", True))
                    )
                elif tool_name == "hexdump":
                    data = _tool_hexdump(
                        project_path, path, args.get("offset", 0), args.get("length", 256)
                    )
                else:
                    data = _tool_extract_strings(
                        project_path, path, args.get("min_length", 4),
                        bool(args.get("interesting_only", True)), args.get("limit", 200),
                    )
            elif tool_name == "audit_project":
                data = _tool_audit_project(project_path)
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
