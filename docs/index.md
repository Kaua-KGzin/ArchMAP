<p align="center">
  <img src="assets/logo.png" alt="ArchMAP" width="460"/>
</p>

<p align="center">
  <em>Map Your Architecture. Control Your Future.</em>
</p>

<p align="center">
  <a href="https://github.com/Kaua-KGzin/ArchMAP/actions/workflows/ci.yml">
    <img src="https://github.com/Kaua-KGzin/ArchMAP/actions/workflows/ci.yml/badge.svg" alt="CI"/>
  </a>
  <img src="https://img.shields.io/badge/version-0.8.0-orange" alt="v0.8.0"/>
  <img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue" alt="Python"/>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT"/>
</p>

---

**ArchMAP** is a static architecture analysis toolkit for source repositories.

It parses code, builds dependency graphs, detects circular dependencies, computes complexity and risk signals, and exposes results through a rich CLI and an interactive web UI.

## What's in v0.8.0

| Feature | Command |
|---|---|
| Multi-language parsing (Python, JS/TS, Rust, Go, PHP, Java, C#, C/C++) | `archmap analyze` |
| Circular dependency detection (Tarjan SCC) | `archmap analyze` |
| Architecture risk scoring (god modules, layer violations, dep explosions) | `archmap risk` |
| Git ref diff and JSON snapshot diff | `archmap diff` |
| BFS reachability from any entrypoint | `archmap trace` |
| LLM architectural advisor — Claude, OpenAI, Ollama, or any local model | `archmap advise` |
| Exporters: JSON, Mermaid, Cytoscape, SARIF | `archmap analyze` |
| Interactive service map with Trace and Advisor views | `archmap serve` |
| VS Code extension with inline diagnostics and health score | IDE |

## Getting started

<p align="center">
  <img src="assets/banner-cli.png" alt="archmap CLI" width="520"/>
</p>

```bash
pip install KG-ARCHMAP
archmap analyze . --format both
archmap serve .
```

1. [Installation](getting-started/installation.md)
2. [Quick Start](getting-started/quickstart.md)
3. [Live Demo](getting-started/demo.md)

## CLI reference

| Command | Purpose |
|---|---|
| [`analyze`](cli/analyze.md) | Full report, quality gates, Mermaid/JSON/Cytoscape/SARIF |
| [`explain`](cli/explain.md) | Human-readable architecture summary |
| [`risk`](cli/risk.md) | Blast radius and risk score for a file |
| [`improve`](cli/improve.md) | Structural suggestions + refactor script |
| [`serve`](cli/serve.md) | Interactive web UI with graph, insights, trace, advisor |
| [`diff`](cli/diff.md) | Compare git refs or JSON snapshots |
| [`trace`](cli/trace.md) | BFS reachability from any entrypoint |
| [`init`](cli/init.md) | Generate `.archmap.toml` from real dependency graph |
| [`advise`](cli/advise.md) | LLM-powered architectural advisor |
| [`watch`](cli/watch.md) | Continuous analysis on file change |

## Governance and release

- [Branching Strategy](BRANCHING.md)
- [Contributing Guide](contributing.md)
- [Code of Conduct](code-of-conduct.md)
- [Changelog](changelog.md)
- [Roadmap](roadmap.md)

## Attribution

Original distributor: **Kaua Gabriel / Kauã Gabriel** (Kaua-KGzin).  
See [Original Distribution Notice](notice.md) and the [MIT License](https://github.com/Kaua-KGzin/ArchMAP/blob/main/LICENSE).
