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
    <img src="https://img.shields.io/badge/version-1.0.0-brightgreen" alt="Version"/>
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
| Release | `v1.0.0` |
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
archmap serve <path> --host 0.0.0.0 --port 3000
```

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

When installed, all language parsers upgrade automatically. The regex fallback is preserved — no behaviour change without the extra.

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
