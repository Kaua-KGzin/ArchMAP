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

The server exposes fifteen tools.

### Architecture and code

| Tool | Description |
|---|---|
| `get_project_memory` | Compact markdown digest of the whole project — health, top risks, cycles, violations — the same content [`archmap memory`](memory.md) writes to `.archmap/memory.md`. Call this first. |
| `get_architecture_summary` | Full architecture report: health score, cycles, god modules, layer violations, top risk files |
| `get_file_context` | Per-file detail: imports, dependents, complexity, impact radius |
| `impact_analysis` | Transitive blast radius of a file or package (`pkg:<name>`) — returns the precomputed impacted-files set and risk tier |
| `run_checks` | Quality gate results: cycle count, god modules, layer violations, resolution rate |
| `trace_reachability` | BFS from an entrypoint file through outgoing dependency edges — everything it transitively pulls in, plus coverage stats and dead-code detection |
| `diff_architecture` | Architecture diff between two git refs (default `HEAD~1` vs `HEAD`): health/complexity/cycle deltas and per-file changes |
| `get_network_exposure` | Live network scan of a target, correlated against the project's dependency graph — surfaces which open ports/services map to code the project actually imports, that code's blast radius, a confidence score per finding, and any `[network.rules]` drift violations (see [`archmap expose`](expose.md)) |
| `get_relevant_context` | Files to read for a task, in order, packed into a token budget, with reasons and best-matching lines (see [`archmap context`](context.md)) |
| `get_analysis_quality` | Parse coverage, failures, per-language resolution, and overall confidence of the graph |
| `list_findings` | Unified findings (`ARCH-*`, `QUAL-*`, `TEST-*`) filtered by domain and minimum severity |

### Reverse engineering and security

| Tool | Description |
|---|---|
| `inspect_path` | Static inspection of a file or directory inside the project (see [`archmap inspect`](inspect.md)) |
| `hexdump` | Hex + ASCII dump of up to 4096 bytes at an offset (negative offsets from the end) |
| `extract_strings` | ASCII/UTF-16LE strings, by default only the classified, interesting ones (secrets redacted) |
| `audit_project` | Secrets (`SEC-*`), cross-file data flows (`TAINT-*`), insecure code patterns (`CODE-*`) and AI-agent configuration risks (`AGENT-*`) (see [`archmap audit`](audit.md)) |

File tools resolve paths against the project root (following symlinks) and
refuse anything outside it, so a prompt-injected model can't use them to
read `~/.ssh` or other files beyond the project. Start the server in the
directory you want inspected.

### Time budget and `notice`

Eleven tools run a full analysis (`get_project_memory`, `get_architecture_summary`,
`get_file_context`, `impact_analysis`, `run_checks`, `trace_reachability`,
`get_network_exposure`, `get_relevant_context`, `get_analysis_quality`,
`list_findings`, `diff_architecture`) and accept an optional `time_budget`
argument in seconds. The budget is, in order: the `time_budget` argument,
`[analysis.limits] time_budget_seconds` in `.archmap.toml`, then a **120 s
default**. `0` means no limit; negative values are rejected.
`diff_architecture` analyzes two refs and gives each half of the budget.

The budget is soft (parsing is never cut short). The response carries a
`notice` field:

- when the budget forced a reduction (impacted-file lists left out, centrality
  sampled or skipped): which stages were reduced and how to get a full run
  (`time_budget=0`);
- when the 120 s default is the active budget, even if nothing was reduced:

```text
Analysis ran under the default 120 s MCP time budget (mcp-default); nothing was
reduced. Change it with the time_budget argument or [analysis.limits]
time_budget_seconds in .archmap.toml; 0 means no limit.
```

A budget you set yourself (argument or `.archmap.toml`) adds a `notice` only
when something was reduced. `impact_analysis` always returns the full impacted
list for the file you ask about. See [Performance](../performance.md).

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

After restarting Claude Code, the tools become available in every conversation about that project.

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
  cache uses. The budget is not part of the key: a full result is reused for
  any budget, while a reduced one is reused only by a call with the same
  budget. The on-disk cache is shared with the CLI, so `archmap memory` in a
  session hook and the MCP server do not invalidate each other. A tool call only re-analyzes when a source file actually
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
