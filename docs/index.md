<div class="archmap-hero" markdown>

<p align="center">
  <img src="assets/logo.png" alt="ArchMAP" width="420"/>
</p>

<p class="tagline"><em>Map Your Architecture. Control Your Future.</em></p>

<p align="center">
  <a href="https://github.com/Kaua-KGzin/ArchMAP/actions/workflows/ci.yml">
    <img src="https://github.com/Kaua-KGzin/ArchMAP/actions/workflows/ci.yml/badge.svg" alt="CI"/>
  </a>
  <img src="https://img.shields.io/pypi/v/KG-ARCHMAP?label=PyPI" alt="PyPI"/>
  <img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue" alt="Python"/>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT"/>
</p>

[Get started](getting-started/installation.md){ .md-button .md-button--primary }
[CLI reference](cli/analyze.md){ .md-button }

</div>

---

**ArchMAP** is a static architecture analysis toolkit for source repositories. It
parses code, builds dependency graphs, detects circular dependencies, computes
complexity and risk signals, and exposes the results through a rich CLI, an
interactive web UI, and an MCP server for AI assistants.

```bash
pip install KG-ARCHMAP
archmap analyze . --format both
archmap serve .
```

## Why ArchMAP

<div class="grid cards" markdown>

-   :material-graph-outline:{ .lg .middle } __Dependency graphs, 9 languages__

    ---

    Python, JavaScript, TypeScript, Rust, Go, PHP, Java, C#, and C/C++. Tree-sitter
    is used as a resilient primary parser with an automatic per-file regex fallback.

    [:octicons-arrow-right-24: Architecture](architecture.md)

-   :material-sync-circle:{ .lg .middle } __Cycle & risk detection__

    ---

    Strongly-connected-component cycle detection, god-module / layer-violation /
    dependency-explosion smells, and a composite risk score per file.

    [:octicons-arrow-right-24: Risk command](cli/risk.md)

-   :material-shield-check:{ .lg .middle } __CI quality gates__

    ---

    Fail the build on cycles, architectural risks, coupling budgets, or a low
    import-resolution rate. SARIF export integrates with GitHub Code Scanning.

    [:octicons-arrow-right-24: Analyze command](cli/analyze.md)

-   :material-robot-outline:{ .lg .middle } __AI-native__

    ---

    An MCP server exposes the analysis engine to Claude Code, Cursor, and Windsurf,
    plus an optional LLM architectural advisor.

    [:octicons-arrow-right-24: MCP server](cli/mcp.md)

</div>

## Getting started

<p align="center">
  <img src="assets/banner-cli.png" alt="archmap CLI" width="520"/>
</p>

1. [Installation](getting-started/installation.md) — PyPI, Docker, and the optional tree-sitter extra
2. [Quick Start](getting-started/quickstart.md) — analyze and serve your first project
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
| [`init`](cli/init.md) | Generate `.archmap.toml` from a real dependency graph |
| [`advise`](cli/advise.md) | LLM-powered architectural advisor |
| [`temporal`](cli/temporal.md) | Temporal coupling via git history |
| [`mcp`](cli/mcp.md) | MCP server for AI assistant integration |
| [`watch`](cli/watch.md) | Continuous analysis on file change |
| [`netscan`](cli/netscan.md) | Network host discovery + port scanning, nmap-style |

## What's new

- **1.1.0** — `archmap netscan`: nmap-style network discovery, port scanning,
  and per-port risk classification, stdlib-only (works on Termux without root).
  Web UI mobile/Termux fixes, and fail-fast on a nonexistent project path.
- **1.0.3** — tree-sitter becomes a resilient *primary* parser with automatic
  per-file fallback to the regex path; structured C# extraction.
- **1.0.2** — comment-aware parsing and configuration-aware resolution
  (Go `replace`, PHP composer PSR-4, Java inner classes, C# aliases, C/C++ include dirs).
- **1.0.1** — security hardening (`serve` binds to loopback by default),
  O(V+E) impact analysis, and tsconfig/jsconfig path-alias resolution.

See the full [Changelog](changelog.md) and [Roadmap](roadmap.md).

## Governance and release

- [Branching Strategy](BRANCHING.md)
- [Contributing Guide](contributing.md)
- [Code of Conduct](code-of-conduct.md)

## Attribution

Original distributor: **Kaua Gabriel / Kauã Gabriel** (Kaua-KGzin).
See [Original Distribution Notice](notice.md) and the [MIT License](https://github.com/Kaua-KGzin/ArchMAP/blob/main/LICENSE).
