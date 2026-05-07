# ArchMAP

ArchMAP is a static architecture analysis toolkit for source repositories.

It parses code, builds dependency graphs, detects circular dependencies, computes complexity/risk signals, and exposes results through exports and an interactive web UI.

## Highlights

- Multi-language parsing (Python, JS/TS, Rust, Go, PHP, Java, C#, C/C++)
- Circular dependency detection (Tarjan SCC)
- Architecture risk scoring: god modules, layer violations, dependency explosions
- Git ref diff and JSON snapshot diff (`archmap diff`)
- BFS reachability from any entrypoint (`archmap trace`)
- LLM-powered architectural advisor — Claude, OpenAI, Ollama, or any local model (`archmap advise`)
- Exporters: JSON, Mermaid, Cytoscape, SARIF
- Interactive service map with Trace and Advisor views (`archmap serve`)
- VS Code extension with inline diagnostics and health score

## Recommended path

1. [Installation](getting-started/installation.md)
2. [Quick Start](getting-started/quickstart.md)
3. [Live Demo](getting-started/demo.md)
4. [CLI analyze](cli/analyze.md)
5. [CLI serve](cli/serve.md)
6. [CLI diff](cli/diff.md)
7. [CLI trace](cli/trace.md)
8. [CLI advise](cli/advise.md)

## Governance and release

- [Branching Strategy](BRANCHING.md)
- [Contributing Guide](contributing.md)
- [Code of Conduct](code-of-conduct.md)
- [Changelog](changelog.md)
- [Roadmap](roadmap.md)

## Attribution

Original distributor: **Kaua Gabriel / Kauã Gabriel** (Kaua-KGzin).  
See [Original Distribution Notice](notice.md) and the [MIT License](https://github.com/Kaua-KGzin/ArchMAP/blob/main/LICENSE).
