# archmap serve

Analyzes a project and starts an interactive Web UI server.

## Usage

```bash
archmap serve [path] [options]
```

`path` defaults to `.` (current directory).

## Options

| Option | Default | Description |
|---|---|---|
| `--host` | `127.0.0.1` | Host/interface to bind the server. Use `0.0.0.0` to expose on the network (prints a security warning) |
| `--port` | `3000` | Port to listen on |
| `--no-open` | off | Skip opening the browser automatically |
| `--format` | `both` | Output format for exports: `json`, `mermaid`, or `both` |
| `--out` | `.codeatlas/graph.json` | JSON export path |
| `--out-mermaid` | `.codeatlas/graph.mmd` | Mermaid export path |
| `--include-cytoscape` | off | Also write Cytoscape JSON |

## Examples

```bash
# Serve current directory
archmap serve .

# Custom port
archmap serve . --port 8080

# Don't open browser (e.g. in CI or remote server)
archmap serve . --no-open

# Serve a specific project
archmap serve /path/to/project --port 4000

# Expose on the network (explicit opt-in; prints a security warning)
archmap serve . --host 0.0.0.0 --port 4000
```

## Live API endpoints

While running, the server exposes:

| Endpoint | Method | Scope | Description |
|---|---|---|---|
| `/` | GET | any | Interactive graph UI |
| `/api/graph` | GET | any | Full JSON report (same as `archmap analyze` output) |
| `/api/project` | GET | any | Current analyzed project path |
| `/api/health` | GET | any | `{"status":"ok"}` |
| `/api/badge` | GET | any | Architecture health badge (SVG, for README embedding) |
| `/api/history` | GET | any | Temporal coupling history snapshots |
| `/api/events` | GET | any | Server-sent events stream for live UI refresh |
| `/api/reanalyze` | POST | loopback | Recompute the report for the current project |
| `/api/project` | POST | loopback | Switch the analyzed directory |
| `/api/advise` | POST | loopback | LLM architectural advice (validates `base_url`) |
| `/api/open` | POST | loopback | Open the native folder picker and switch project |
| `/api/open-file` | POST | loopback | Open a graph node's file in the OS/IDE |

## Security

`archmap serve` is a developer tool, not a hardened multi-tenant service.

- **Loopback by default.** Since v1.0.1 the server binds to `127.0.0.1`. Pass
  `--host 0.0.0.0` to expose it on the network; a warning is printed when you do.
- **State-changing and local endpoints are restricted to loopback** regardless
  of `--host`. Endpoints that switch the analyzed directory, open local files, or
  trigger outbound LLM requests (`/api/project`, `/api/reanalyze`, `/api/advise`,
  `/api/open`, `/api/open-file`) reject non-loopback clients with `403`. Only the
  read-only graph/health/badge endpoints are reachable when bound to `0.0.0.0`.
- **`/api/advise` validates `base_url`** — only well-formed `http`/`https` URLs
  are forwarded server-side, preventing SSRF via other URL schemes.

For untrusted networks, keep the default loopback binding and put a reverse proxy
with authentication in front if remote access is required.

## Notes

- Press `Ctrl+C` to stop the server.
- The UI `Refresh` button triggers `POST /api/reanalyze`, so a restart is not required.
