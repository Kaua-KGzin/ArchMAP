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

## Views

The UI is available in English, Português, Español, Français, Deutsch, and
中文 (Settings → Language), in light and dark themes, and reflows for phones
and tablets.

| View | What it shows |
|---|---|
| **Graph** | The dependency graph (Cytoscape). Filter by folder, show only cycles, color by complexity (heatmap). Click a node for its imports, dependents, and blast radius; *Trace from here* jumps to the Trace view. |
| **Insights** | Health metrics plus the **Analysis confidence** card: files discovered vs. parsed, parse failures with their errors, files skipped for encoding/size, and import resolution per language. The Summary panel shows the same confidence as a KPI, highlighted when it isn't high. |
| **Rules & Layers** | Layer hierarchy from `.archmap.toml`, layer violations, and custom rule violations. |
| **Trace** | BFS reachability from an entrypoint, depth-colored on the graph, with coverage and unreachable files. |
| **AI Advisor** | LLM architectural advice (Claude, OpenAI, Ollama, or any OpenAI-compatible endpoint) and the matching CLI commands. |
| **Findings** | All unified findings (`ARCH-*`, `QUAL-*`, plus `SEC-*`/`AGENT-*` once an audit has run), with counts per severity, filters by domain and minimum severity, expandable evidence, and *Show in graph* for findings tied to a file. |
| **Task context** | Type a task ("fix retry backoff in the payment webhook"), pick a token budget, and get the files to read in order: role (match or neighbor), estimated tokens, dependents, why each was picked, and the best matching lines. *Highlight in graph* dims everything else. Ctrl+Enter runs the search. |
| **Inspect files** | Inspect any path inside the project. For a file: type, size, entropy, SHA-256, format details, mitigation chips (green = present, red = missing), data summary, and `BIN-*` findings. For a folder (`.` for the whole project): an inventory by format and the list of binaries and containers. |
| **Inspector** (canvas tab) | Opens after an inspection. For a file: a clickable entropy profile, a paged hexdump (offsets accept `0x` hex; *End* jumps to the last bytes), and a filterable strings table whose offsets jump the hexdump. For a folder: the binary→library linkage graph (click a binary to inspect it) and the most linked libraries. |
| **Security audit** | Runs `archmap audit` on the project: secret and agent-configuration counts, git awareness, and every `SEC-*`/`AGENT-*` finding with redacted evidence. |
| **Layers / Matrix** (canvas tabs) | Breadth-first layer diagram and a dependency matrix of the 25 most connected files. |

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
| `/api/context` | POST | loopback | `{"task", "budget", "maxFiles"}` → files to read for a task |
| `/api/inspect` | POST | loopback | `{"path", "strings"}` → file report or folder inventory (path inside the project) |
| `/api/hexdump` | POST | loopback | `{"path", "offset", "length"}` → hexdump of up to 4096 bytes |
| `/api/strings` | POST | loopback | `{"path", "interesting", "minLength", "limit"}` → strings |
| `/api/audit` | POST | loopback | Secrets and AI-agent configuration audit of the project |

Every `POST` must send `Content-Type: application/json` (an empty body is
`{}`), for example:

```bash
curl -X POST http://127.0.0.1:3000/api/reanalyze -H "Content-Type: application/json" -d "{}"
```

The toolkit endpoints answer `{"status": "success", "result": ...}`, or
`400` with a message for invalid input (missing file, path outside the
project).

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
- **CSRF protection (v1.4.0).** Every `POST` must carry
  `Content-Type: application/json`, otherwise the server answers `415`. A web
  page on another origin can't send that header without a CORS preflight,
  which the server never approves, so a website you visit while `archmap
  serve` is running can't trigger re-analysis, switch the project, or run
  the file-reading endpoints.
- **File access is confined to the project.** `/api/inspect`, `/api/hexdump`,
  and `/api/strings` resolve paths (and symlinks) inside the analyzed project
  and refuse anything outside it. Nothing is executed.

For untrusted networks, keep the default loopback binding and put a reverse proxy
with authentication in front if remote access is required.

## Notes

- Press `Ctrl+C` to stop the server.
- The UI `Refresh` button triggers `POST /api/reanalyze`, so a restart is not required.
