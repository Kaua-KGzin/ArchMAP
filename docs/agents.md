# AI agent plugin & skill

ArchMAP ships as a ready-made plugin for Claude Code and as a portable agent
skill for Cursor, Codex, OpenCode, and other agents that read `SKILL.md`.
Installing it replaces the manual MCP and hook setup described in
[`archmap mcp`](cli/mcp.md) and [`archmap memory`](cli/memory.md).

## Prerequisite

The plugin calls the `archmap` CLI, so install it first:

```bash
pip install KG-ARCHMAP
```

## Claude Code

```text
/plugin marketplace add Kaua-KGzin/ArchMAP
/plugin install archmap@archmap
```

The plugin provides:

| Component | What it does |
|---|---|
| MCP server `archmap` | Runs `archmap mcp .` and exposes all fifteen ArchMAP tools (architecture, context, quality, findings, reverse engineering, audit) |
| `SessionStart` hook | Injects `archmap memory --print` into context at session start. Skips silently if `archmap` isn't installed, and is bounded to 60 s |
| `archmap` skill | Tells the agent when to call which tool: orient with `get_project_memory` and `get_relevant_context`, check `get_analysis_quality`, run `impact_analysis` before editing, `run_checks` + `diff_architecture` before finishing; plus a reverse-engineering workflow (`inspect_path`, `extract_strings`, `hexdump`) and `audit_project` |

To also refresh `.archmap/memory.md` after every edit, add the
`PostToolUse` hook from [`archmap memory`](cli/memory.md) to your project's
`.claude/settings.json`. It isn't enabled by default because it writes a
file into your project.

## Other agents (Cursor, Codex, OpenCode, …)

```bash
npx skills add Kaua-KGzin/ArchMAP --skill archmap
```

This installs the same skill. Register the MCP server in your agent's MCP
config (see [`archmap mcp`](cli/mcp.md)); without it, the skill falls back to
the equivalent CLI commands.

## Layout

```text
.claude-plugin/marketplace.json     # marketplace index (repo root)
plugins/archmap/
├── .claude-plugin/plugin.json      # manifest; version tracks the package
├── .mcp.json                       # archmap MCP server
├── hooks/hooks.json                # SessionStart memory injection
└── skills/archmap/SKILL.md         # agent workflow
```

`tests/test_agent_plugin.py` keeps the plugin version equal to the package
version and fails if the skill names an MCP tool the server doesn't expose.
