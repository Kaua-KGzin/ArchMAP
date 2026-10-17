"""Consistency checks for the Claude Code plugin / agent skill in plugins/archmap."""

from __future__ import annotations

import json
import re
from pathlib import Path

from archmap import __version__
from archmap.cli.mcp_server import _TOOLS

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "archmap"
SKILL_FILE = PLUGIN_ROOT / "skills" / "archmap" / "SKILL.md"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md must start with YAML frontmatter"
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def test_marketplace_points_at_plugin() -> None:
    marketplace = _load(REPO_ROOT / ".claude-plugin" / "marketplace.json")
    entries = {p["name"]: p for p in marketplace["plugins"]}
    assert entries["archmap"]["source"] == "./plugins/archmap"
    assert (REPO_ROOT / entries["archmap"]["source"]).is_dir()


def test_plugin_version_matches_package() -> None:
    manifest = _load(PLUGIN_ROOT / ".claude-plugin" / "plugin.json")
    assert manifest["name"] == "archmap"
    assert manifest["version"] == __version__


def test_mcp_config_launches_archmap_server() -> None:
    server = _load(PLUGIN_ROOT / ".mcp.json")["mcpServers"]["archmap"]
    assert server["command"] == "archmap"
    assert server["args"][0] == "mcp"


def test_hooks_file_has_wrapper_and_is_failsafe() -> None:
    hooks = _load(PLUGIN_ROOT / "hooks" / "hooks.json")["hooks"]
    command = hooks["SessionStart"][0]["hooks"][0]["command"]
    assert "archmap memory" in command and "--print" in command
    # A missing archmap install must never break the user's session start.
    assert "command -v archmap" in command and "|| true" in command


def test_skill_frontmatter() -> None:
    fields = _frontmatter(SKILL_FILE.read_text(encoding="utf-8"))
    assert fields["name"] == "archmap"
    assert fields["description"]


def test_skill_references_only_real_mcp_tools() -> None:
    text = SKILL_FILE.read_text(encoding="utf-8")
    known = {tool["name"] for tool in _TOOLS}
    arguments = {"project_path", "max_depth", "base_ref", "head_ref"}
    referenced = set(re.findall(r"`([a-z]+(?:_[a-z]+)+)`", text)) - arguments
    assert referenced, "skill should reference MCP tools"
    assert referenced <= known, f"unknown tools in SKILL.md: {sorted(referenced - known)}"
    # Every tool the server exposes should be documented for the agent.
    assert known <= referenced, f"undocumented tools: {sorted(known - referenced)}"
