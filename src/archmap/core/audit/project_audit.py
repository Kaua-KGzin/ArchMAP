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
from archmap.utils.file_utils import DEFAULT_IGNORE_DIRS, is_vendored_path

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


# The analyzer skips tests/, examples/ and build output to keep the *graph*
# clean, but a secret committed there is just as leaked, so the audit only
# skips dependency trees and caches, and scans build output when git tracks it.
_AUDIT_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".pytest_cache", ".codeatlas", "bower_components",
} | _EXTRA_SKIP_DIRS
_BUILD_DIRS = {
    d.casefold() for d in DEFAULT_IGNORE_DIRS
} - {d.casefold() for d in _AUDIT_SKIP_DIRS} - {"tests", "examples"}


def _iter_text_files(root: Path, tracked: set[str] | None = None) -> Iterator[Path]:
    skip_dirs = {d.casefold() for d in _AUDIT_SKIP_DIRS}
    tracked_dirs = (
        {p.rsplit("/", 1)[0] for p in tracked if "/" in p} if tracked is not None else set()
    )
    tracked_prefixes = {
        "/".join(parts[:i]) for d in tracked_dirs for parts in [d.split("/")]
        for i in range(1, len(parts) + 1)
    }
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        kept = []
        for d in sorted(dirnames):
            folded = d.casefold()
            if folded in skip_dirs:
                continue
            if folded in _BUILD_DIRS:
                rel = d if rel_dir == "." else f"{rel_dir}/{d}"
                if rel not in tracked_prefixes:
                    continue  # untracked build output: regenerated, not shipped from git
            kept.append(d)
        dirnames[:] = kept
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
        self.code: list[Finding] = []
        self.taint: list[Finding] = []
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
        **extra: Any,
    ) -> Finding:
        finding = Finding(
            id=finding_id,
            domain=domain,
            category=category,
            severity=severity,
            confidence=confidence,
            message=message,
            evidence=evidence,
            file=file,
        )
        finding.update(extra)  # type: ignore[typeddict-item]
        return finding

    def add_secret(self, **fields: Any) -> None:
        finding_id = f"SEC-{len(self.secrets) + 1:03d}"
        self.secrets.append(self._finding(finding_id, "security", **fields))

    def add_code(self, **fields: Any) -> None:
        finding_id = f"CODE-{len(self.code) + 1:03d}"
        self.code.append(self._finding(finding_id, "security", **fields))

    def add_taint(self, **fields: Any) -> None:
        finding_id = f"TAINT-{len(self.taint) + 1:03d}"
        self.taint.append(self._finding(finding_id, "security", **fields))

    def add_agent(self, **fields: Any) -> None:
        finding_id = f"AGENT-{len(self.agent) + 1:03d}"
        self.agent.append(self._finding(finding_id, "agent", **fields))


def audit_project(
    root: str | Path, *, include_code: bool = True, include_taint: bool = True
) -> dict[str, Any]:
    """Audit ``root`` for secrets, insecure code, tainted data flows and agent configuration."""
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise NotADirectoryError(f"not a directory: {root_path}")
    tracked = _git_tracked(root_path)
    collector = _Collector()
    scanned = 0
    taint_sources: dict[str, str] = {}

    for path in _iter_text_files(root_path, tracked):
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
        if include_code:
            _scan_code(rel, text, collector)
            if include_taint and _taint_candidate(rel):
                taint_sources[rel] = text

    _audit_mcp_configs(root_path, collector)
    _audit_claude_settings(root_path, collector)
    _audit_hook_files(root_path, collector)
    _audit_instruction_files(root_path, collector)

    if taint_sources:
        _scan_taint(root_path, taint_sources, collector)

    findings = collector.secrets + collector.taint + collector.code + collector.agent
    limitations = [
        "Secrets are matched by pattern and never verified against a provider.",
        "Git history is not scanned; a secret removed from HEAD may still be in history.",
    ]
    if include_code:
        limitations.append(
            "Code checks are pattern-based (no data-flow): a CODE finding marks a sink "
            "to review, not a proven exploit."
        )
    if include_code and include_taint:
        limitations.append(
            "Data-flow (TAINT) analysis is intra-project and name-resolved: flows through "
            "reflection, dependency-injection containers, framework callbacks and dynamic "
            "dispatch are not followed, and custom validators are not recognised."
        )
    return {
        "root": str(root_path),
        "filesScanned": scanned,
        "gitAware": tracked is not None,
        "secretFindings": len(collector.secrets),
        "codeFindings": len(collector.code),
        "taintFindings": len(collector.taint),
        "agentFindings": len(collector.agent),
        "findings": findings,
        "limitations": limitations,
    }


_TEST_PATH = re.compile(
    r"(?i)(?:^|/)(?:tests?|__tests__|spec|specs|testdata|test-data|fixtures?|e2e|mocks?|__mocks__)/"
    r"|(?:^|/)test_[^/]+\.py$|_test\.(?:py|go)$|\.(?:spec|test)\.[cm]?[jt]sx?$"
    r"|(?:Tests?|Spec)\.(?:cs|java|kt|php)$|(?:^|/)[^/]+\.Tests?/"
)
_EXAMPLE_PATH = re.compile(
    r"(?i)\.(?:example|sample|template|dist|tmpl)(?:\.[^/]*)?$"
    r"|(?:^|/)(?:examples?|samples?|docs?)/|(?:^|/)README[^/]*$|\.md$"
)
_CI_PATH = re.compile(r"(?i)(?:^|/)\.github/workflows/|(?:^|/)\.gitlab-ci\.yml$|(?:^|/)\.circleci/")


def secret_context(rel: str) -> tuple[str, int, float] | None:
    """Where a secret sits changes what it means.

    Returns ``(label, severity steps to drop, confidence factor)`` for files whose
    credentials are usually fixtures or templates, ``None`` for ordinary code.
    Findings are kept (a real key in a test is still a real key) but ranked
    below secrets in shipped code.
    """
    if _TEST_PATH.search(rel):
        return "test fixture", 2, 0.5
    if _EXAMPLE_PATH.search(rel):
        return "example/template/docs", 2, 0.5
    if _CI_PATH.search(rel):
        return "CI configuration", 1, 0.7
    return None


def _step_down(severity: str, steps: int) -> str:
    index = SEVERITY_LEVELS.index(severity) if severity in SEVERITY_LEVELS else 2
    return SEVERITY_LEVELS[max(0, index - steps)]


def _scan_secrets(rel: str, text: str, tracked: set[str] | None, out: _Collector) -> None:
    committed = tracked is None or rel in tracked
    context = secret_context(rel)
    for match in scan_text(text, max_matches=20):
        severity = match["severity"] if committed else _lower_severity(match["severity"])
        confidence = match["confidence"]
        evidence_context: list[str] = []
        # A private key is never "just a fixture" when it is committed.
        if context and match["rule"] != "private-key":
            label, steps, factor = context
            severity = _step_down(severity, steps)
            confidence = round(confidence * factor, 2)
            evidence_context = [f"Context: {label} (severity and confidence reduced)"]
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
            confidence=confidence,
            message=f"{match['name']} in {rel}:{match['line']}",
            evidence=[f"File: {rel}:{match['line']}", f"Value (redacted): {match['redacted']}",
                      f"Rule: {match['rule']}", *evidence_context, f"Status: {status}"],
            file=rel,
        )


def _scan_code(rel: str, text: str, out: _Collector) -> None:
    from archmap.core.audit.code_rules import scan_code

    context = "vendored third-party code" if is_vendored_path(rel) else None
    test_context = secret_context(rel)
    if context is None and test_context and test_context[0] == "test fixture":
        context = "test code"
    for match in scan_code(rel, text):
        severity = match["severity"]
        confidence = match["confidence"]
        evidence = [
            f"File: {rel}:{match['lines'][0]}",
            f"Code: {match['snippet']}",
            f"Rule: {match['rule']} ({match['cwe']})",
        ]
        if len(match["lines"]) > 1:
            shown = ", ".join(str(n) for n in match["lines"][:10])
            more = f" (+{len(match['lines']) - 10} more)" if len(match["lines"]) > 10 else ""
            evidence.append(f"Occurrences: {len(match['lines'])} at lines {shown}{more}")
        if context:
            severity = _step_down(severity, 2)
            confidence = round(confidence * 0.5, 2)
            evidence.append(f"Context: {context} (severity and confidence reduced)")
        evidence.append(f"Fix: {match['remediation']}")
        out.add_code(
            category=match["rule"],
            severity=severity,
            confidence=confidence,
            message=f"{match['title']} in {rel}:{match['lines'][0]}",
            evidence=evidence,
            file=rel,
            line=match["lines"][0],
            cwe=match["cwe"],
            remediation=match["remediation"],
        )


def _taint_candidate(rel: str) -> bool:
    from archmap.core.audit.taint import SUPPORTED_EXTENSIONS

    suffix = rel[rel.rfind("."):].lower() if "." in rel else ""
    if suffix not in SUPPORTED_EXTENSIONS or suffix in (".d.ts",) or rel.endswith(".min.js"):
        return False
    context = secret_context(rel)
    # Test code feeds fixtures to sinks on purpose; vendored code is not ours.
    return not is_vendored_path(rel) and not (context and context[0] == "test fixture")


def _graph_neighbours(root: Path) -> dict[str, set[str]]:
    """file -> files it imports, from ArchMAP's own resolved dependency graph."""
    try:
        from archmap.core.parser import parse_project

        parsed = parse_project(root, parallel=True)
    except Exception:
        return {}
    return {
        item["id"]: {dep["id"] for dep in item["dependencies"] if dep.get("type") == "file"}
        for item in parsed["parsedFiles"]
    }


def _scan_taint(root: Path, sources: dict[str, str], out: _Collector) -> None:
    from archmap.core.audit.taint import SINKS, analyze_sources

    graph = _graph_neighbours(root)
    try:
        hits = analyze_sources(sources, lambda file: graph.get(file, set()))
    except RecursionError:
        return
    from archmap.core.audit.code_rules import is_suppressed

    covered: dict[str, set[int]] = {}
    for hit in hits:
        lines = sources.get(hit.file, "").splitlines()
        if is_suppressed(lines, hit.line):
            continue
        kind = SINKS[hit.sink]
        confidence = 0.85 if hit.file.endswith(".py") else 0.75
        if hit.via:
            confidence -= 0.05
        evidence = [f"Sink: {hit.file}:{hit.line}  {hit.text}"]
        evidence += [f"Flow: {step}" for step in hit.trace]
        evidence += [f"Call: {call}" for call in hit.via]
        evidence += [f"Rule: taint-{hit.sink} ({kind.cwe})", f"Fix: {kind.remediation}"]
        source = _source_text(hit.source) or "untrusted input"
        out.add_taint(
            category=f"taint-{hit.sink}",
            severity=kind.severity,
            confidence=round(confidence, 2),
            message=f"{kind.title}: {source} reaches {hit.file}:{hit.line}",
            evidence=evidence,
            file=hit.file,
            line=hit.line,
            cwe=kind.cwe,
            remediation=kind.remediation,
        )
        covered.setdefault(hit.file, set()).add(hit.line)
    # A pattern finding fully explained by a data-flow finding adds nothing.
    out.code = [
        f for f in out.code
        if not (f.get("file") in covered and _code_lines(f) <= covered[str(f.get("file"))])
    ]


def _source_text(label: str) -> str:
    from archmap.core.audit.taint.model import BROWSER_PREFIX, LOCAL_PREFIX

    return label.removeprefix(LOCAL_PREFIX).removeprefix(BROWSER_PREFIX)


def _code_lines(finding: Finding) -> set[int]:
    for item in finding.get("evidence", []):
        if item.startswith("Occurrences: "):
            numbers = item.split(" at lines ", 1)[1].split(" (", 1)[0]
            return {int(n) for n in numbers.split(", ") if n.isdigit()}
    return {int(finding.get("line", 0))}


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
