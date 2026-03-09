# ArchMAP

[![CI](https://github.com/Kaua-KGzin/code-arch-visualizer/actions/workflows/ci.yml/badge.svg)](https://github.com/Kaua-KGzin/code-arch-visualizer/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Version](https://img.shields.io/badge/version-0.4.0--beta-orange)](./CHANGELOG.md)

**Static architecture analysis for any codebase.** ArchMAP scans your source code, builds a dependency graph, detects circular dependencies, flags risky files, and lets you explore everything through a premium interactive web UI — in one command.

Supports **Python · JavaScript · TypeScript · Go · PHP · Java · C# · C · C++**.

## Status

- Current release: `v0.4.0-beta` (The "Respect" Update)
- Primary stack: Python (`>=3.11`)
- Current supported languages: Python, JS, TS, Rust, Go, PHP, Java, C#, C, C++

## Why ArchMAP migrated to Python

ArchMAP was migrated from Node.js to Python to make the analysis engine easier to evolve and
package for automation workflows. The migration was done to unlock:

- A cleaner modular architecture under `src/archmap`
- Better compatibility with data/analysis tooling ecosystems
- Easier CLI packaging and CI quality gates (lint + coverage)
- Faster iteration for architecture analysis features like `diff` and risk scoring

The old JavaScript implementation can remain in history, but Python is now the canonical runtime.

## How ArchMAP Works

Pipeline:

Source Code
-> Parser
-> Dependency Graph
-> Analyzer (cycles, complexity, risk)
-> Exporters (JSON, Mermaid, Cytoscape)
-> Visualization

- Static dependency analysis for 9+ languages
- Circular dependency detection with visual cycle mapping
- Complexity scoring by imports & incoming dependency ranking
- **Architecture Risk Engine**:
  - God modules (Hubs) detection
  - Layer violations & Dependency explosions
- **Commit/Ref Comparison**:
  - `archmap diff <base> <head>`
  - Dependency/cycle/complexity deltas
- **Interactive "UI of Respect"**:
  - **Dark Mode** & Premium glassmorphism styling
  - **Dynamic Project Import**: Switch projects inside the UI
  - **Architectural Risk Dashboard**
- **Distribution**:
  - Standalone Windows Executable with embedded assets
  - Export formats: JSON, Mermaid, Cytoscape JSON

## Installation

```bash
pip install archmap
```

For local development (editable + dev tools):

```bash
git clone https://github.com/Kaua-KGzin/code-arch-visualizer
cd code-arch-visualizer
pip install -e ".[dev]"
```

## CLI Usage

Main command:

```bash
archmap
```

Backward-compatible alias:

```bash
code-arch
```

### Analyze

```bash
archmap analyze <path> [--format json|mermaid|both] [--out <file>] [--out-mermaid <file>] [--include-cytoscape]
```

### Serve

```bash
archmap serve <path> [--port 3000] [--no-open] [--format json|mermaid|both]
```

### Diff between refs

```bash
archmap diff HEAD~5 HEAD
```

Example output:

```text
+12 dependencies
+1 circular dependencies
complexity +18.00%
```

## Recommended Repository Structure

```text
ArchMAP
├── src/
│   └── archmap/
│       ├── cli/
│       │   └── main.py
│       ├── core/
│       │   ├── parser/
│       │   ├── analyzer/
│       │   └── graph/
│       ├── exporters/
│       └── utils/
├── tests/
├── docs/
├── examples/
├── scripts/
├── README.md
├── ROADMAP.md
├── CONTRIBUTING.md
├── CHANGELOG.md
└── pyproject.toml
```

## Branch Strategy

- `main`: stable production code only
- `dev`: integration branch for upcoming release
- `feature/*`: isolated features
- `release/*`: stabilization, docs, tests, and release prep

Flow:

`feature/* -> dev -> release/* -> main`

## Development

Run lint:

```bash
ruff check .
```

Run tests with coverage:

```bash
pytest
```

Smoke analysis:

```bash
archmap analyze . --format both --out .codeatlas/ci-graph.json --out-mermaid .codeatlas/ci-graph.mmd --include-cytoscape
```

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md). Please read our [Code of Conduct](./CODE_OF_CONDUCT.md) before opening issues or pull requests.

## License

MIT. See [LICENSE](./LICENSE).
