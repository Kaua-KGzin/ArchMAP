# ArchMAP

ArchMAP is a static architecture analysis toolkit for source repositories.

It parses code, builds dependency graphs, detects circular dependencies,
computes risk signals, suggests cleaner folder structure, and serves the results
through exports and a lightweight web UI.

## Highlights

- Multi-language parsing:
  - Python
  - JS/TS
  - Rust
  - Go
  - PHP
  - Java
  - C#
  - C/C++
- Circular dependency detection
- Architecture risk scoring:
  - god modules
  - layer violations
  - dependency explosions
- Simple project explanation with `archmap explain`
- File blast-radius inspection with `archmap risk`
- Automatic reorganization suggestions with `archmap improve`
- Exporters:
  - JSON
  - Mermaid
  - Cytoscape
- Interactive service map with `archmap serve`

## Recommended path

1. [Installation](getting-started/installation.md)
2. [Quick Start](getting-started/quickstart.md)
3. [CLI analyze](cli/analyze.md)
4. [CLI explain](cli/explain.md)
5. [CLI risk](cli/risk.md)
6. [CLI improve](cli/improve.md)
7. [CLI serve](cli/serve.md)
8. [CLI diff](cli/diff.md)

## Governance and release

- [Branching Strategy](BRANCHING.md)
- [Contributing Guide](contributing.md)
- [Code of Conduct](code-of-conduct.md)
- [Changelog](changelog.md)
- [Roadmap](roadmap.md)

## Attribution

Original distributor: **Kaua Gabriel** (Kaua-KGzin).
See [Original Distribution Notice](notice.md) and the
[MIT License](https://github.com/Kaua-KGzin/ArchMAP/blob/main/LICENSE).
