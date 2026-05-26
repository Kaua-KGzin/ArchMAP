# archmap mcp

Starts a JSON-RPC 2.0 server over stdio that exposes ArchMAP analysis tools to AI assistants (Claude Code, Cursor, Windsurf, and any MCP-compatible client).

## Usage

```bash
archmap mcp [path]
```

## Arguments

| Argument | Description |
|---|---|
| `path` | Project root to analyze (default: `.`) |

## Examples

```bash
# Start the MCP server for the current project
archmap mcp .

# Point at a specific repo
archmap mcp /path/to/my-project
```

## Tools exposed

The server exposes four tools:

| Tool | Description |
|---|---|
| `get_architecture_summary` | Full architecture report: health score, cycles, god modules, layer violations, top risk files |
| `get_file_context` | Per-file detail: imports, dependents, complexity, impact radius |
| `impact_analysis` | Files affected if a given file changes (BFS reachability) |
| `run_checks` | Quality gate results: cycle count, god modules, layer violations, resolution rate |

## Registering with Claude Code

Add the server to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "archmap": {
      "command": "archmap",
      "args": ["mcp", "/path/to/your/project"]
    }
  }
}
```

After restarting Claude Code, the four tools become available in every conversation about that project.

## Registering with Cursor or Windsurf

Add the same JSON block to your editor's MCP settings file (see editor docs for the exact path). The `command` and `args` format is identical across MCP-compatible clients.

## Protocol

The server reads JSON-RPC 2.0 requests from stdin and writes responses to stdout. Each request must be a single newline-terminated JSON object.

```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"run_checks","arguments":{}}}
```

## Notes

- The server re-analyzes the project on each tool call (uses the incremental cache, so repeated calls are fast).
- Only one project path is supported per server instance. Start a separate instance for each project.
- The server does not open any network ports — communication is exclusively over stdio.
