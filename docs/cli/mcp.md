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

The server exposes seven tools:

| Tool | Description |
|---|---|
| `get_architecture_summary` | Full architecture report: health score, cycles, god modules, layer violations, top risk files |
| `get_file_context` | Per-file detail: imports, dependents, complexity, impact radius |
| `impact_analysis` | Transitive blast radius of a file or package (`pkg:<name>`) — returns the precomputed impacted-files set and risk tier |
| `run_checks` | Quality gate results: cycle count, god modules, layer violations, resolution rate |
| `trace_reachability` | BFS from an entrypoint file through outgoing dependency edges — everything it transitively pulls in, plus coverage stats and dead-code detection |
| `diff_architecture` | Architecture diff between two git refs (default `HEAD~1` vs `HEAD`): health/complexity/cycle deltas and per-file changes |
| `get_network_exposure` | Live network scan of a target, correlated against the project's dependency graph — surfaces which open ports/services map to code the project actually imports, that code's blast radius, a confidence score per finding, and any `[network.rules]` drift violations (see [`archmap expose`](expose.md)) |

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

After restarting Claude Code, the seven tools become available in every conversation about that project.

## Registering with Cursor or Windsurf

Add the same JSON block to your editor's MCP settings file (see editor docs for the exact path). The `command` and `args` format is identical across MCP-compatible clients.

## Protocol

The server reads JSON-RPC 2.0 requests from stdin and writes responses to stdout. Each request must be a single newline-terminated JSON object.

```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"run_checks","arguments":{}}}
```

## Notes

- Analysis results are cached in memory per `project_path`, keyed by the same
  content fingerprint (config + every source file's mtime/size) the on-disk
  cache uses. A tool call only re-analyzes when a source file actually
  changed since the last call in this session — edits made by the AI
  assistant mid-conversation are picked up automatically, without a stale
  read and without re-analyzing on every single call.
- `project_path` is a per-call argument, not a server-wide setting: passing a
  different path than the one the server started with just adds a second
  cache entry, so one running instance can already answer about more than
  one project. Starting the server pointed at a specific project (`archmap
  mcp /path/to/project`) is a convention for the common case, not a
  hard limit.
- `get_network_exposure` runs a real network scan against whatever `target`
  it's given. Only use it against hosts you own or are explicitly authorized
  to test — the same rule as [`archmap netscan`](netscan.md) and
  [`archmap expose`](expose.md).
- The server does not open any network ports of its own — communication with
  the MCP client is exclusively over stdio; only `get_network_exposure`
  makes outbound connections, and only when explicitly invoked.
