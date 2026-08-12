<p align="center">
  <img src="resources/logo.png" alt="ArchMAP — Map Your Architecture. Control Your Future." width="480"/>
</p>

<p align="center">
  <a href="https://github.com/Kaua-KGzin/ArchMAP/actions/workflows/ci.yml">
    <img src="https://github.com/Kaua-KGzin/ArchMAP/actions/workflows/ci.yml/badge.svg" alt="CI"/>
  </a>
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue" alt="Python"/>
  </a>
  <a href="./LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT"/>
  </a>
  <a href="./CHANGELOG.md">
    <img src="https://img.shields.io/badge/version-1.1.0-brightgreen" alt="Version"/>
  </a>
  <a href="https://pypi.org/project/KG-ARCHMAP/">
    <img src="https://img.shields.io/badge/PyPI-KG--ARCHMAP-orange?logo=pypi&logoColor=white" alt="PyPI"/>
  </a>
</p>

<p align="center">
  Static architecture analysis for software repositories.
</p>

---

ArchMAP scans source code, builds dependency graphs, detects cycles, reports architectural risks, and serves an interactive web UI.

**Supported languages:** Python · JavaScript · TypeScript · Rust · Go · PHP · Java · C# · C/C++

## Status

| | |
|---|---|
| Release | `v1.1.0` |
| Runtime | Python `>=3.11` |
| UI | built-in static UI + Node dev server |
| Distribution | PyPI (`KG-ARCHMAP`) + Windows `.exe` |

## Installation

### From PyPI

```bash
pip install KG-ARCHMAP
```

### For local development

```bash
git clone https://github.com/Kaua-KGzin/ArchMAP
cd ArchMAP
python -m pip install -e ".[dev]"
```

### Termux (Android)

```bash
pkg install python
pip install KG-ARCHMAP
```

If you're analyzing a project stored in Android's shared storage (e.g.
`Download/`) and ArchMAP reports "0 files analyzed" on a project that clearly
has files, that's almost always Termux not having real access to that
folder yet, not a bug in the scan — see [Termux setup](https://kaua-kgzin.github.io/ArchMAP/getting-started/installation/#termux-android) for the fix (`termux-setup-storage` + Android's "All files access" permission, or copying the project into Termux's own home directory).

## Quick demo

```bash
archmap analyze examples/sample-project --format both --include-cytoscape
archmap serve examples/sample-project
```

Useful API endpoints while `serve` is running:

| Endpoint | Description |
|---|---|
| `GET /api/graph` | Full dependency graph JSON |
| `GET /api/health` | Health score + grade |
| `GET /api/project` | Project metadata |
| `POST /api/reanalyze` | Trigger a fresh analysis |

## CLI overview

<p align="center">
  <img src="docs/assets/banner-cli.png" alt="archmap CLI" width="560"/>
</p>

### Analyze

```bash
archmap analyze <path> --format json|mermaid|both
```

Quality gates for CI:

```bash
# Fail on cycles or architectural risks
archmap analyze . --fail-on-risks --top 10

# Coupling budget gate
archmap analyze . --fail-on-budget-violations --max-outgoing-per-file 15 --max-incoming-per-file 10

# Resolution rate gate
archmap analyze . --min-resolution-rate 70

# Strip external packages from the graph
archmap analyze . --ignore-external

# Summary output styles: text (default), table, markdown
archmap analyze . --summary-format markdown

# Show unresolved imports
archmap analyze . --show-unresolved=20
```

### Serve

```bash
# Binds to 127.0.0.1 by default (loopback only).
archmap serve <path> --port 3000

# Expose on the network explicitly (prints a security warning).
archmap serve <path> --host 0.0.0.0 --port 3000
```

> **Security note:** endpoints that read local files, switch the analyzed
> project, or call an LLM (`/api/open`, `/api/open-file`, `/api/project`,
> `/api/reanalyze`, `/api/advise`) are restricted to loopback requests
> regardless of `--host`. Only the read-only graph/health endpoints are
> reachable from other hosts when you bind to `0.0.0.0`.

The web UI is responsive — the nav rail, side panels, and toolbar reflow into a single-column, touch-friendly layout on phones and tablets, so `archmap serve` works the same way in a Termux browser as it does on desktop.

### Diff

```bash
# Compare two git refs
archmap diff HEAD~5 HEAD

# Compare two saved JSON snapshots (no git required)
archmap diff --snapshot-a before.json --snapshot-b after.json
```

### Trace

```bash
archmap trace src/main.py .
archmap trace src/main.py . --unreachable --max-depth 3
```

Shows every file reachable from an entrypoint through the dependency graph, grouped by depth, with coverage percentage.

### Init (blueprint from real graph)

```bash
archmap init                       # scan directory names
archmap init --from-analysis       # derive layer rules from actual dependency graph
archmap init --from-analysis --dry-run
```

### Advise (LLM architectural advisor)

```bash
archmap advise .                                          # Claude (ANTHROPIC_API_KEY)
archmap advise . --provider openai                        # OpenAI (OPENAI_API_KEY)
archmap advise . --provider ollama                        # local Ollama
archmap advise . --provider custom --base-url http://localhost:1234  # any OpenAI-compat API
```

### Temporal coupling

```bash
archmap temporal .                     # files that change together (hidden coupling)
archmap temporal . --min-commits 3     # raise signal threshold
archmap temporal . --top 30 --json    # machine-readable output
```

Parses `git log` and ranks file pairs by co-change frequency + coupling strength. Zero new dependencies (stdlib only).

### Netscan (network discovery)

> **Only scan networks and hosts you own or are explicitly authorized to test.** Unauthorized scanning may be illegal in your jurisdiction.

```bash
archmap netscan 192.168.1.0/24                       # discover hosts + scan top 20 ports
archmap netscan 192.168.1.10 --ports 22,80,443        # scan specific ports on one host
archmap netscan 192.168.1.0/24 --discover-only        # just find which hosts are up
archmap netscan 10.0.0.1-50 --top-ports 100 --json    # scan a range, machine-readable output
archmap netscan 192.168.1.0/24 --nmap-args="-sV"      # pass extra flags through to nmap
archmap netscan 192.168.1.0/24 --no-nmap              # force the built-in scanner instead
```

Two scan engines, one report format. If `nmap` is installed, ArchMAP uses it automatically as the engine — it's simply a more capable scanner than a from-scratch one. Pass `--no-nmap` to force the built-in stdlib-only scanner instead (no root, no extra dependencies — works the same way on a laptop or in Termux on Android), or `--use-nmap` to require nmap and fail loudly if it's missing. Either way, the target spec accepts a single IP/hostname, a CIDR block, a dash range (`192.168.1.1-50`), or a comma-separated combination.

The built-in engine discovers hosts via ICMP ping with a TCP connect-probe fallback (ICMP is often filtered on real networks), then does a threaded TCP connect port scan. Every open port gets analyzed, not just marked open: it's checked against a table of known-risky ports/services (Telnet, exposed Redis/Mongo/Elasticsearch, unauthenticated Docker API, RDP, VNC, SMB, ...) and, with fingerprinting on (`--no-fingerprint` to disable), a deeper probe — HTTP(S) title/`Server` header (over TLS for 443/8443/...), or the raw service banner otherwise.

Both engines report through the same clean, aligned table — nmap just fills in more of it: service version/extrainfo from `-sV`, an OS guess with `--os-detection`, nmap's own NSE scripts with `--scripts` (page titles, TLS cert info, known misconfigurations...), and its own scan stats — instead of nmap's raw scrolling console output:

```text
  Network Scan — target: 192.168.1.0/24 (engine: nmap v7.94)
  hosts probed: 254 | hosts up: 2 | nmap elapsed: 11.80s | duration: 12.40s

  192.168.1.1 (router.local) ----------------------------------- UP
    OS: Linux 5.X (92%)
    PORT      STATE    SERVICE          INFO
    ----------------------------------------
    22/tcp    open     ssh              OpenSSH 9.0
    80/tcp    open     http             nginx 1.18.0
        [http-title] Welcome page
    6379/tcp  open     redis              [HIGH RISK]
        ! Redis is frequently deployed with no authentication

  Summary: 2 host(s) up, 3 open port(s) total, 1 high/critical-risk port(s) flagged.
```

`--os-detection` adds nmap's `-O` OS fingerprinting; `--scripts` adds nmap's default NSE scripts + version detection (`-sC -sV`). Both require the nmap engine (and `--os-detection` needs root).

**Termux setup:**

```bash
pkg install python
pip install KG-ARCHMAP
archmap netscan 192.168.1.0/24
# optional, to use the nmap engine instead of the built-in one:
pkg install nmap
```

### Expose (network × code correlation)

```bash
archmap expose 192.168.1.0/24 .
```

Runs a netscan and cross-references the results against your codebase's dependency graph: if an open port's service (say, Redis on `6379`) matches a package your code actually imports, ArchMAP surfaces that package's already-computed blast radius (how many files depend on it) right next to the port's network risk rating — combined into one severity. Accepts every `archmap netscan` option (`--ports`, `--use-nmap`, `--scripts`, etc.) plus the project path to analyze. See [`archmap expose`](docs/cli/expose.md) for the full option list and JSON schema.

### MCP server (AI assistant integration)

```bash
archmap mcp .
```

Starts a JSON-RPC 2.0 server over stdio exposing 4 tools: `get_architecture_summary`, `get_file_context`, `impact_analysis`, `run_checks`. Register in `~/.claude/claude_desktop_config.json` to let Claude Code, Cursor, or Windsurf query your project's structure before making changes.

### Tree-sitter parser (optional)

Install the `[tree-sitter]` extra for AST-based parsing across all 9 languages (eliminates regex false positives on multiline imports, string literals, and comments):

```bash
pip install "KG-ARCHMAP[tree-sitter]"
```

When installed, all language parsers upgrade automatically. Tree-sitter is used as a resilient *primary* parser: each grammar loads independently, and if it cannot parse a given file (or parses it unreliably), that single file transparently falls back to the regex path instead of being dropped. The regex fallback is fully preserved — no behaviour change without the extra.

## VS Code Extension

<p align="center">
  <img src="vscode-extension/icon.png" alt="ArchMAP VS Code Extension" width="80"/>
</p>

The bundled VS Code extension provides zero-config IDE integration:

- Inline diagnostics (cycles, layer violations, god modules) in the Problems panel
- Status bar health score + grade
- `ArchMAP: Analyze Project` command
- `ArchMAP: Open Web UI` command
- `ArchMAP: Trace File Reachability` webview
- `archmap.analyzeOnSave` for CI-style continuous feedback

## Git workflow

Branch promotion model: `feat/* → dev → release/* → main`

Rules:
1. No direct feature merge into `main`.
2. `release/*` accepts only stabilization changes.
3. CI must pass before merge.
4. Update docs/changelog when behavior changes.

See [CONTRIBUTING.md](./CONTRIBUTING.md) and [docs/BRANCHING.md](./docs/BRANCHING.md).

## Repository layout

```text
ArchMAP/
├── .github/          # CI/release workflows and PR template
├── docs/             # MkDocs documentation + assets
├── examples/         # sample project for demos
├── logs/             # runtime/archive log organization
├── resources/        # brand assets (logos, icons)
├── scripts/          # automation helpers (smoke, benchmark, exe build)
├── src/archmap/      # Python source code
├── tests/            # automated test suite
├── vscode-extension/ # VS Code extension (inline diagnostics, trace view)
├── web-ui/           # Node dev server + static assets
├── archmap.spec      # PyInstaller spec
└── README.md
```

## Logs and artifacts

- Runtime logs: `logs/runtime/` (git-ignored)
- Historical logs: `logs/archive/`
- Build artifacts: generated locally (`build/`, `dist/`) — not committed

## Windows executable

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-exe.ps1 -Clean
```

Builds `dist/archmap.exe`, creates a versioned binary copy, writes `dist/archmap-build-info.json` with SHA256, and runs a smoke test.

## Node development server

```bash
npm run serve:web -- --path .
```

## License

MIT — see [LICENSE](./LICENSE).

Original distributor and primary author: **Kaua Gabriel / Kauã Gabriel** (Kaua-KGzin).  
Redistributions must preserve [LICENSE](./LICENSE) and [NOTICE.md](./NOTICE.md).
