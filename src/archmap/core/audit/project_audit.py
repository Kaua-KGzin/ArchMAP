"""`archmap audit`: committed secrets (SEC-*) and AI-agent configuration risks (AGENT-*).

AI coding agents read project files as instructions and run the MCP servers,
hooks, and permissions a repository declares. That configuration is now part
of a project's attack surface, so it gets audited like code: deterministic,
offline checks, each finding carrying its evidence and a confidence score.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import unicodedata
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from archmap.core.analyzer.findings import SEVERITY_LEVELS
from archmap.core.audit.secrets import scan_text
from archmap.types import Finding
from archmap.utils.file_utils import DEFAULT_IGNORE_DIRS

MAX_AUDIT_FILE_BYTES = 1024 * 1024
MAX_AUDIT_FILES = 20_000
_EXTRA_SKIP_DIRS = {".archmap", ".venv", "venv", ".tox", ".mypy_cache", ".ruff_cache"}
_SKIP_SUFFIXES = {".lock", ".min.js", ".map", ".svg"}
_SKIP_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock"}

_MCP_CONFIGS = (".mcp.json", ".cursor/mcp.json", ".vscode/mcp.json", ".gemini/settings.json")
_CLAUDE_SETTINGS = (".claude/settings.json", ".claude/settings.local.json")
_INSTRUCTION_FILES = (
    "CLAUDE.md",
    "AGENTS.md",
    "GEMINI.md",
    ".cursorrules",
    ".windsurfrules",
    ".github/copilot-instructions.md",
)
_LOOPBACK = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
_INTERPRETERS = {
    "python", "python3", "node", "bash", "sh", "zsh", "pwsh", "powershell",
    "perl", "ruby", "deno", "bun", "npx", "uvx", "eval", "env",
}
_PIPE_TO_SHELL = re.compile(
    r"(?:curl|wget|iwr|Invoke-WebRequest)\b[^|;&]*\|\s*(?:sudo\s+)?(?:ba|z)?sh\b"
    r"|base64\s+(?:-d|--decode)[^|]*\|\s*(?:ba)?sh\b"
    r"|\beval\s+\"?\$\((?:curl|wget)",
    re.I,
)
_NETWORK_COMMAND = re.compile(r"\b(?:curl|wget|nc|ncat|Invoke-WebRequest|iwr)\b", re.I)
_SECRET_ENV_KEY = re.compile(r"(?i)(?:token|secret|password|passwd|api[_-]?key|auth)")
_ENV_REFERENCE = re.compile(r"^\$\{?[A-Za-z_][A-Za-z0-9_]*\}?$|^\$\{[^}]+\}$")
# Bidi overrides, zero-width characters, and Unicode tag characters: invisible
# in editors and diffs but read by models ("Rules File Backdoor").
_HIDDEN_CHARS = re.compile(
    "[​-‏‪-‮⁠-⁤⁦-⁩﻿\U000e0000-\U000e007f]"
)


def _lower_severity(severity: str) -> str:
    index = SEVERITY_LEVELS.index(severity) if severity in SEVERITY_LEVELS else 2
    return SEVERITY_LEVELS[max(0, index - 2)]


def _git_tracked(root: Path) -> set[str] | None:
    """Files git tracks, or ``None`` when ``root`` isn't a git work tree."""
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return {p for p in completed.stdout.decode("utf-8", "replace").split("\x00") if p}


def _iter_text_files(root: Path) -> Iterator[Path]:
    skip_dirs = {d.casefold() for d in DEFAULT_IGNORE_DIRS} | _EXTRA_SKIP_DIRS
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d.casefold() not in skip_dirs)
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            if filename in _SKIP_NAMES or any(filename.endswith(s) for s in _SKIP_SUFFIXES):
                continue
            try:
                if path.is_symlink() or path.stat().st_size > MAX_AUDIT_FILE_BYTES:
                    continue
            except OSError:
                continue
            yield path
            count += 1
            if count >= MAX_AUDIT_FILES:
                return


class _Collector:
    def __init__(self) -> None:
        self.secrets: list[Finding] = []
        self.agent: list[Finding] = []

    @staticmethod
    def _finding(
        finding_id: str,
        domain: str,
        *,
        category: str,
        severity: str,
        confidence: float,
        message: str,
        evidence: list[str],
        file: str,
    ) -> Finding:
        return Finding(
            id=finding_id,
            domain=domain,
            category=category,
            severity=severity,
            confidence=confidence,
            message=message,
            evidence=evidence,
            file=file,
        )

    def add_secret(self, **fields: Any) -> None:
        finding_id = f"SEC-{len(self.secrets) + 1:03d}"
        self.secrets.append(self._finding(finding_id, "security", **fields))

    def add_agent(self, **fields: Any) -> None:
        finding_id = f"AGENT-{len(self.agent) + 1:03d}"
        self.agent.append(self._finding(finding_id, "agent", **fields))


def audit_project(root: str | Path) -> dict[str, Any]:
    """Audit ``root`` for secrets and risky AI-agent configuration."""
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise NotADirectoryError(f"not a directory: {root_path}")
    tracked = _git_tracked(root_path)
    collector = _Collector()
    scanned = 0

    for path in _iter_text_files(root_path):
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in raw[:8192]:
            continue  # binary; `archmap inspect` handles those
        scanned += 1
        text = raw.decode("utf-8", errors="replace")
        rel = path.relative_to(root_path).as_posix()
        _scan_secrets(rel, text, tracked, collector)

    _audit_mcp_configs(root_path, collector)
    _audit_claude_settings(root_path, collector)
    _audit_hook_files(root_path, collector)
    _audit_instruction_files(root_path, collector)

    findings = collector.secrets + collector.agent
    return {
        "root": str(root_path),
        "filesScanned": scanned,
        "gitAware": tracked is not None,
        "secretFindings": len(collector.secrets),
        "agentFindings": len(collector.agent),
        "findings": findings,
        "limitations": [
            "Secrets are matched by pattern and never verified against a provider.",
            "Git history is not scanned; a secret removed from HEAD may still be in history.",
        ],
    }


def _scan_secrets(rel: str, text: str, tracked: set[str] | None, out: _Collector) -> None:
    committed = tracked is None or rel in tracked
    for match in scan_text(text, max_matches=20):
        severity = match["severity"] if committed else _lower_severity(match["severity"])
        status = (
            "tracked by git (committed)"
            if tracked is not None and committed
            else "not tracked by git (local only)"
            if tracked is not None
            else "git status unknown"
        )
        out.add_secret(
            category="secret",
            severity=severity,
            confidence=match["confidence"],
            message=f"{match['name']} in {rel}:{match['line']}",
            evidence=[f"File: {rel}:{match['line']}", f"Value (redacted): {match['redacted']}",
                      f"Rule: {match['rule']}", f"Status: {status}"],
            file=rel,
        )


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _audit_mcp_configs(root: Path, out: _Collector) -> None:
    for rel in _MCP_CONFIGS:
        config = _load_json(root / rel)
        if not isinstance(config, dict):
            continue
        servers = config.get("mcpServers") or config.get("servers") or {}
        if not isinstance(servers, dict):
            continue
        for name, server in servers.items():
            if isinstance(server, dict):
                _audit_mcp_server(rel, str(name), server, out)


def _audit_mcp_server(rel: str, name: str, server: dict[str, Any], out: _Collector) -> None:
    where = f"{rel} → mcpServers.{name}"
    url = server.get("url")
    if isinstance(url, str):
        parsed = urlparse(url)
        if parsed.scheme in ("http", "ws") and parsed.hostname not in _LOOPBACK:
            out.add_agent(
                category="mcp_insecure_transport", severity="medium", confidence=0.95,
                message=(
                    f"MCP server '{name}' uses unencrypted {parsed.scheme}:// "
                    f"to {parsed.hostname}"
                ),
                evidence=[f"Config: {where}", f"URL: {url}"], file=rel,
            )
    command = str(server.get("command", ""))
    args = [str(a) for a in server.get("args", []) if isinstance(a, (str, int, float))]
    if Path(command).name in ("npx", "uvx", "bunx", "pnpx") and args:
        package = next((a for a in args if not a.startswith("-")), "")
        bare = package.split("/", 1)[1] if package.startswith("@") and "/" in package else package
        if package and ("@" not in bare or package.endswith("@latest")):
            out.add_agent(
                category="mcp_unpinned_package", severity="low", confidence=0.85,
                message=f"MCP server '{name}' runs unpinned package '{package}' on every start",
                evidence=[f"Config: {where}", f"Command: {command} {' '.join(args)}",
                          "Pin an exact version so a compromised release isn't auto-executed"],
                file=rel,
            )
    for section in ("env", "headers"):
        values = server.get(section)
        if not isinstance(values, dict):
            continue
        for key, value in values.items():
            text = str(value)
            if _ENV_REFERENCE.match(text) or not text:
                continue
            literal_secret = bool(scan_text(text, max_matches=1)) or (
                _SECRET_ENV_KEY.search(str(key)) is not None and len(text) >= 8
            )
            if literal_secret:
                out.add_agent(
                    category="mcp_plaintext_secret", severity="high", confidence=0.85,
                    message=f"MCP server '{name}' has a plaintext credential in {section}.{key}",
                    evidence=[f"Config: {where}", "Use an environment-variable reference "
                              "(${VAR}) instead of a literal value"],
                    file=rel,
                )


def _audit_claude_settings(root: Path, out: _Collector) -> None:
    for rel in _CLAUDE_SETTINGS:
        settings = _load_json(root / rel)
        if not isinstance(settings, dict):
            continue
        permissions = settings.get("permissions") or {}
        if isinstance(permissions, dict):
            if permissions.get("defaultMode") == "bypassPermissions":
                out.add_agent(
                    category="permissions_bypassed", severity="high", confidence=0.95,
                    message=f"{rel} sets defaultMode=bypassPermissions (no approval for any tool)",
                    evidence=[f"Config: {rel} → permissions.defaultMode"], file=rel,
                )
            for rule in permissions.get("allow", []) or []:
                severity = _permission_risk(str(rule))
                if severity:
                    out.add_agent(
                        category="broad_permission", severity=severity, confidence=0.9,
                        message=f"{rel} pre-approves '{_short(str(rule))}' "
                                "(arbitrary command execution without a prompt)",
                        evidence=[f"Config: {rel} → permissions.allow"], file=rel,
                    )
        if settings.get("enableAllProjectMcpServers") is True:
            out.add_agent(
                category="auto_enabled_mcp", severity="medium", confidence=0.9,
                message=f"{rel} auto-enables every MCP server a repository declares",
                evidence=[f"Config: {rel} → enableAllProjectMcpServers"], file=rel,
            )
        _audit_hooks(rel, settings.get("hooks"), out)


def _permission_risk(rule: str) -> str | None:
    rule = rule.strip()
    if rule in ("*", "Bash", "Bash(*)", "Bash(:*)"):
        return "high"
    match = re.match(r"^Bash\(\s*([^\s:)]+)\s*(?::\*|\*|\s\*)\s*\)$", rule)
    if match and Path(match.group(1)).name in _INTERPRETERS:
        return "medium"
    return None


def _short(text: str, limit: int = 80) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _iter_hook_commands(hooks: Any) -> Iterator[tuple[str, str]]:
    if not isinstance(hooks, dict):
        return
    for event, matchers in hooks.items():
        for matcher in matchers if isinstance(matchers, list) else []:
            entries = matcher.get("hooks", []) if isinstance(matcher, dict) else []
            for hook in entries if isinstance(entries, list) else []:
                if isinstance(hook, dict) and hook.get("type", "command") == "command":
                    args = [str(a) for a in hook.get("args", []) or []]
                    command = " ".join([str(hook.get("command", "")), *args])
                    yield str(event), command


def _audit_hooks(rel: str, hooks: Any, out: _Collector) -> None:
    for event, command in _iter_hook_commands(hooks):
        if _PIPE_TO_SHELL.search(command):
            out.add_agent(
                category="risky_hook", severity="high", confidence=0.9,
                message=f"{event} hook in {rel} pipes downloaded content into a shell",
                evidence=[f"Config: {rel} → hooks.{event}", f"Command: {_short(command)}"],
                file=rel,
            )
        elif _NETWORK_COMMAND.search(command):
            out.add_agent(
                category="network_hook", severity="medium", confidence=0.7,
                message=f"{event} hook in {rel} makes network calls on every trigger",
                evidence=[f"Config: {rel} → hooks.{event}", f"Command: {_short(command)}"],
                file=rel,
            )


def _audit_hook_files(root: Path, out: _Collector) -> None:
    """Plugin hook files (``**/hooks/hooks.json``), searched a few levels deep."""
    for path in sorted(root.glob("**/hooks/hooks.json")):
        rel = path.relative_to(root).as_posix()
        if rel.count("/") > 5 or any(part in _EXTRA_SKIP_DIRS for part in path.parts):
            continue
        data = _load_json(path)
        if isinstance(data, dict):
            _audit_hooks(rel, data.get("hooks"), out)


def _audit_instruction_files(root: Path, out: _Collector) -> None:
    for rel in _INSTRUCTION_FILES:
        path = root / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        hidden = _HIDDEN_CHARS.findall(text)
        # A single leading BOM is an encoding artifact, not hidden content.
        if text.startswith("﻿"):
            hidden = hidden[1:]
        if hidden:
            names = sorted({unicodedata.name(ch, f"U+{ord(ch):04X}") for ch in hidden})[:5]
            out.add_agent(
                category="hidden_unicode_instructions", severity="high", confidence=0.85,
                message=f"{rel} contains {len(hidden)} invisible Unicode character(s) "
                        "an agent will read but a reviewer won't see",
                evidence=[f"File: {rel}", f"Characters: {', '.join(names)}"],
                file=rel,
            )
