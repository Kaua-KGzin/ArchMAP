# ArchMAP

ArchMAP visualizes the architecture of your codebase through dependency graphs, cycle detection, and complexity insights.

## Status

- Current release: `v0.1.0-beta.0`
- Next planned release: `v0.2.0` on `2026-03-10`
- Node.js required: `>=20`

## Features

- Dependency graph generation from source imports
- Supported languages (v0.1): JavaScript, TypeScript, Python, Rust
- Circular dependency detection
- Complexity metrics per file
- Critical files ranking (most depended-on files)
- Interactive web UI (Cytoscape.js)
- Complexity heatmap mode in the graph
- Export formats: JSON and Mermaid

## Installation

```bash
npm install
```

Optional: expose CLI globally in your machine:

```bash
npm link
```

## CLI

Primary command:

```bash
archmap
```

Backward-compatible alias:

```bash
code-arch
```

### Analyze

```bash
archmap analyze <path> [--format json|mermaid|both] [--out <file>] [--out-mermaid <file>]
```

Defaults for `analyze`:
- `--format json`
- `--out .codeatlas/graph.json`
- `--out-mermaid .codeatlas/graph.mmd`

### Serve (UI)

```bash
archmap serve <path> [--format json|mermaid|both] [--port 3000] [--no-open] [--out <file>] [--out-mermaid <file>]
```

Defaults for `serve`:
- `--format both`
- `--port 3000`

### Quick start

```bash
archmap analyze ./project --format both
archmap serve ./project
```

## Output data

JSON graph output includes:

- `nodes[]`
- `edges[]`
- `metrics`
- `cycles`
- node-level `complexityImports` and `complexityScore`

Mermaid output:

- `graph TD`
- sanitized node identifiers
- package node prefixing to avoid collisions

## Development

Run tests:

```bash
npm test
```

Run smoke check:

```bash
npm run test:smoke
```

Run full validation:

```bash
npm run check
```

## Project structure

```text
code-arch-visualizer
├── core
│   ├── parser
│   ├── analyzer
│   └── graph
├── cli
├── web-ui
└── exporters
```

## PT-BR resumo rapido

- Rode `archmap analyze ./projeto` para gerar analise em JSON.
- Rode `archmap serve ./projeto` para abrir o grafo interativo em `http://localhost:3000`.
- Use `--format mermaid` ou `--format both` para exportar diagrama Mermaid.

## License

MIT. See [LICENSE](./LICENSE).
