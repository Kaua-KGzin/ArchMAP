# ArchMAP

[![CI](https://github.com/Kaua-KGzin/ArchMAP/actions/workflows/ci.yml/badge.svg)](https://github.com/Kaua-KGzin/ArchMAP/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Version](https://img.shields.io/badge/version-0.5.0--beta.0-orange)](./CHANGELOG.md)

Static architecture analysis for software repositories.

ArchMAP scans source code, builds dependency graphs, detects cycles, reports architectural risks, and serves an interactive web UI.

Supported languages:
- Python
- JavaScript
- TypeScript
- Rust
- Go
- PHP
- Java
- C#
- C/C++

## Status

- Current release: `v0.5.0-beta.0`
- Primary runtime: Python `>=3.11`
- Interactive UI: built-in static UI + Node dev server option
- Distribution: PyPI package + Windows executable

## Installation

### From PyPI

```bash
pip install archmap
```

### For local development

```bash
git clone https://github.com/Kaua-KGzin/ArchMAP
cd ArchMAP
python -m pip install -e ".[dev]"
```

## Quick demo

Run the bundled sample project:

```bash
archmap analyze examples/sample-project --format both --include-cytoscape
archmap serve examples/sample-project
```

Optional project configuration:

```toml
[analysis]
ignore_dirs = ["generated", "vendor"]
max_file_size_bytes = 1048576

[architecture.rules]
forbid = ["controller -> repository", "ui -> database"]
allow = ["controller -> service", "service -> repository"]

[risks.layer_order]
platform = 6
core = 3
```

Useful API endpoints while `serve` is running:

- `GET /api/graph`
- `GET /api/history?limit=12`
- `GET /api/health`
- `GET /api/project`
- `POST /api/reanalyze`

## CLI overview

### Analyze

```bash
archmap analyze <path> --format json|mermaid|both
```

Quality gates for CI:

```bash
archmap analyze . --fail-on-risks --top 10
archmap analyze . --fail-on-custom-rules --min-health 75
```

### Serve

```bash
archmap serve <path> --host 0.0.0.0 --port 3000
```

### Diff

```bash
archmap diff HEAD~5 HEAD
```

### History

```bash
archmap history --repo . --limit 12
```

## Git workflow (professional flow)

Branch promotion model:

`feat/* -> dev -> release/* -> main`

Also supported:
- `feature/*` (legacy alias)
- `fix/*`
- `docs/*`

Rules:

1. No direct feature merge into `main`.
2. `release/*` accepts only stabilization changes.
3. CI must pass before merge.
4. Update docs/changelog when behavior changes.

See:
- [CONTRIBUTING.md](./CONTRIBUTING.md)
- [docs/BRANCHING.md](./docs/BRANCHING.md)

## Repository layout

```text
ArchMAP/
+-- .github/                  # CI/release workflows and PR template
+-- docs/                     # MkDocs documentation
+-- examples/                 # sample project for demos
+-- logs/                     # runtime/archive log organization
+-- scripts/                  # automation helpers (smoke, benchmark, exe build)
+-- src/archmap/              # Python source code
+-- tests/                    # automated test suite
+-- web-ui/                   # Node dev server + static assets
+-- archmap.spec              # PyInstaller spec
+-- NOTICE.md                 # original distribution notice
`-- README.md
```

## Logs and artifacts

- Runtime logs: `logs/runtime/` (git-ignored)
- Historical logs: `logs/archive/`
- Analysis outputs: `.codeatlas/` (generated locally and git-ignored)
- Build artifacts: generated locally (`build/`, `dist/`) and should not be committed as source changes

## Windows executable

Build locally:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-exe.ps1 -Clean
```

This script:
- Builds `dist/archmap.exe`
- Creates a versioned binary copy
- Removes older `dist/archmap-*.exe` binaries after a successful build
- Writes `dist/archmap-build-info.json` with SHA256
- Runs executable smoke test (`archmap.exe version`)

## Node development server utilities

For frontend/API exploration with dynamic Python analysis:

```bash
npm run serve:web -- --path .
```

## Original distributor rights

Original distributor and primary author: **Kaua Gabriel** (Kaua-KGzin).

Redistributions must preserve:
- [LICENSE](./LICENSE)
- [NOTICE.md](./NOTICE.md)

## License

MIT. See [LICENSE](./LICENSE).
