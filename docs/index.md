# ArchMAP

[![CI](https://github.com/Kaua-KGzin/code-arch-visualizer/actions/workflows/ci.yml/badge.svg)](https://github.com/Kaua-KGzin/code-arch-visualizer/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](https://github.com/Kaua-KGzin/code-arch-visualizer/blob/main/LICENSE)

**Static architecture analysis for any codebase.** ArchMAP scans your source code, builds a dependency graph, detects circular dependencies, flags risky files, and lets you explore everything through an interactive web UI — in one command.

Supports **Python · JavaScript · TypeScript · Rust**.

---

## Quick start

```bash
pip install archmap
archmap serve .
```

That's it. A browser window opens with the interactive graph.

---

## What you get

- **Dependency graph** — every file-to-file and file-to-package edge
- **Circular dependency detection** — exact cycles, highlighted in the UI
- **Complexity ranking** — top files by outgoing import count
- **Architecture risk detection** — god modules, layer violations, dependency explosions
- **Git diff mode** — compare architecture between any two commits
- **Export formats** — JSON, Mermaid diagram, Cytoscape.js

---

## Navigation

- [**Getting Started → Installation**](getting-started/installation.md)
- [**Getting Started → Quick Start**](getting-started/quickstart.md)
- [**CLI Reference**](cli/analyze.md)
- [**Architecture Internals**](architecture.md)
- [**JSON API Reference**](api.md)
