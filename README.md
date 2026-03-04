# CodeAtlas

Visualize the architecture of your codebase with a dependency graph and actionable metrics.

## Features

- Dependency graph for `JavaScript`, `TypeScript`, `Python`, and `Rust`
- Circular dependency detection
- Complexity metrics (imports per file)
- Critical files ranking (most depended-on files)
- Interactive visualization powered by Cytoscape.js
- CLI analysis report export (`JSON`)

## Project Structure

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

## Install

```bash
npm install
```

For local `code-arch` command availability in this folder:

```bash
npm link
```

## Usage

Analyze a project and export JSON:

```bash
code-arch analyze ./project
```

Run analysis and open web UI (`http://localhost:3000`):

```bash
code-arch ./project
```

Explicit serve mode:

```bash
code-arch serve ./project --port 3000
```

## CLI Output Example

```text
✔ 321 arquivos analisados
✔ 1240 dependências detectadas
⚠ 3 circular dependencies encontradas
```

## Graph JSON Shape

```json
{
  "nodes": ["server.js", "auth.js", "database.js"],
  "edges": [["server.js", "auth.js"], ["auth.js", "database.js"]]
}
```

## Current Language Support (v1)

- JavaScript
- TypeScript
- Python
- Rust

## Planned (v2)

- Java
- Go
- C#
- Complexity heatmap
- Architecture timeline from commit history
- Risk analysis by dependency density + change frequency
