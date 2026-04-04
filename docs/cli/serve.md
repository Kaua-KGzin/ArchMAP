# archmap serve

Analyzes a project and starts the interactive web UI server.

## Usage

```bash
archmap serve [path] [options]
```

`path` defaults to `.`.

## Options

| Option | Default | Description |
|---|---|---|
| `--host` | `0.0.0.0` | Host/interface to bind the server |
| `--port` | `3000` | Port to listen on |
| `--no-open` | off | Skip opening the browser automatically |
| `--watch` | off | Re-analyze automatically and push live reload updates |
| `--format` | `both` | Output format for exports: `json`, `mermaid`, or `both` |
| `--out` | `.codeatlas/graph.json` | JSON export path |
| `--out-mermaid` | `.codeatlas/graph.mmd` | Mermaid export path |
| `--include-cytoscape` | off | Also write Cytoscape JSON |
| `--parallel` | on | Enable parallel file parsing |

## Examples

```bash
archmap serve .
archmap serve . --port 8080
archmap serve . --no-open
archmap serve /path/to/project --port 4000
archmap serve . --host 127.0.0.1 --port 4000
archmap serve . --watch
```

## Live API endpoints

While running, the server exposes:

| Endpoint | Description |
|---|---|
| `GET /` | Interactive graph UI |
| `GET /api/graph` | Full JSON report |
| `GET /api/history` | Git-backed architecture timeline |
| `GET /api/project` | Current analyzed project path |
| `GET /api/health` | `{"status":"ok"}` |
| `POST /api/reanalyze` | Recompute report for current project path |
| `POST /api/open` | Open folder picker and switch project |

## Notes

- Press `Ctrl+C` to stop the server.
- `--watch` is useful during refactoring because the browser updates without a
  full restart.
