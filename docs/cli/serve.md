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
| `--host` | `0.0.0.0` | Host/interface to bind the server |
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

# Bind to localhost only
archmap serve . --host 127.0.0.1 --port 4000
```

## Live API endpoints

While running, the server exposes:

| Endpoint | Description |
|---|---|
| `GET /` | Interactive graph UI |
| `GET /api/graph` | Full JSON report (same as `archmap analyze` output) |
| `GET /api/project` | Current analyzed project path |
| `GET /api/health` | `{"status":"ok"}` |
| `POST /api/reanalyze` | Recompute report for current project path |
| `POST /api/open` | Open folder picker and switch project |

## Notes

- Press `Ctrl+C` to stop the server.
- The UI `Refresh` button triggers `POST /api/reanalyze`, so restart is no longer required.
