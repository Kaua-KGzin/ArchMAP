# ArchMAP

[![CI](https://github.com/Kaua-KGzin/ArchMAP/actions/workflows/ci.yml/badge.svg)](https://github.com/Kaua-KGzin/ArchMAP/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Version](https://img.shields.io/badge/version-0.7.0-orange)](./CHANGELOG.md)

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

- Current release: `v0.7.0`
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

Useful API endpoints while `serve` is running:

- `GET /api/graph`
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
```

Use `analyze` for the full report, quality gates, Mermaid, JSON, and Cytoscape exports.

### Explain

```bash
archmap explain <path>
```

Prints a simple architecture summary for tired humans:

```text
auth -> users, payments
payments -> gateway
```

### Risk

```bash
archmap risk <file> [path]
```

Shows blast radius, incoming/outgoing dependencies, and the file risk score.

### Improve

```bash
archmap improve [path] --out-script .codeatlas/refactor.ps1
```

Suggests a cleaner project structure, such as `/auth`, `/payments`, `/users`,
and can generate a helper refactor script.

### Serve

```bash
archmap serve <path> --host 0.0.0.0 --port 3000
```

### Diff

```bash
archmap diff HEAD~5 HEAD
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
- Build artifacts: generated locally (`build/`, `dist/`) and should not be committed as source changes

## Windows executable

Build locally:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-exe.ps1 -Clean
```

This script:
- Builds `dist/archmap.exe`
- Creates a versioned binary copy
- Writes `dist/archmap-build-info.json` with SHA256
- Runs executable smoke test (`archmap.exe version`)

## Node development server utilities

For frontend/API exploration with dynamic Python analysis:

```bash
npm run serve:web -- --path .
```

## Original distributor rights

Original distributor and primary author: **Kaua Gabriel / Kauã Gabriel** (Kaua-KGzin).

Redistributions must preserve:
- [LICENSE](./LICENSE)
- [NOTICE.md](./NOTICE.md)

## License

MIT. See [LICENSE](./LICENSE).
