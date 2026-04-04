# ArchMAP

[![CI](https://github.com/Kaua-KGzin/ArchMAP/actions/workflows/ci.yml/badge.svg)](https://github.com/Kaua-KGzin/ArchMAP/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Version](https://img.shields.io/badge/version-0.6.0b0-orange)](./CHANGELOG.md)

Static architecture analysis for software repositories.

ArchMAP scans source code, builds dependency graphs, detects cycles, reports
architectural risks, suggests cleaner structure, and serves a lightweight web UI.

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

- Current release line: `v0.6.0b0`
- Primary runtime: Python `>=3.11`
- Workflow style: zero-config first
- Distribution: PyPI package + Windows executable
- API and CLI surface may still change before `1.0.0`

## Installation

### From PyPI

```bash
pip install KG-ARCHMAP
```

The installed CLI command remains `archmap`.

### For local development

```bash
git clone https://github.com/Kaua-KGzin/ArchMAP
cd ArchMAP
python -m pip install -e ".[dev]"
```

## Quick start

```bash
archmap analyze .
archmap explain .
archmap risk src/auth/login.ts .
archmap improve . --out-script .codeatlas/refactor.ps1
archmap serve .
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

## CLI overview

### Analyze

```bash
archmap analyze <path> --format json|mermaid|both
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

### Watch

```bash
archmap watch <path>
archmap serve <path> --watch
```

### Init

```bash
archmap init <path>
```

Generates a starter `.archmap.toml` based on the current project layout.

### Diff and history

```bash
archmap diff HEAD~5 HEAD
archmap history --repo . --limit 12
```

## API endpoints while `serve` is running

- `GET /api/graph`
- `GET /api/history?limit=12`
- `GET /api/health`
- `GET /api/project`
- `POST /api/reanalyze`

## Git workflow

Branch promotion model:

`feat/* -> dev -> release/* -> main`

Also supported:
- `feature/*` (legacy alias)
- `fix/*`
- `docs/*`

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
+-- scripts/                  # automation helpers
+-- src/archmap/              # Python source code
+-- tests/                    # automated test suite
+-- web-ui/                   # Node development server helpers
+-- archmap.spec              # PyInstaller spec
+-- NOTICE.md                 # original distribution notice
`-- README.md
```

## Windows executable

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-exe.ps1 -Clean
```

This script builds `dist/archmap.exe`, creates a versioned binary copy, writes
`dist/archmap-build-info.json`, and runs an executable smoke test.

## Original distributor rights

Original distributor and primary author: **Kaua Gabriel** (Kaua-KGzin).

Redistributions must preserve:
- [LICENSE](./LICENSE)
- [NOTICE.md](./NOTICE.md)

## License

MIT. See [LICENSE](./LICENSE).
