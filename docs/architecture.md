# ArchMAP - Architecture Overview

## Pipeline Summary

Every `archmap` command runs the same core pipeline:

```text
Source files on disk / git ref
        |
        v
Parser (archmap.core.parser)
        |
        v
Graph Builder (archmap.core.graph)
        |
        v
Analyzer (archmap.core.analyzer)
        |
        v
Exporters / Web UI
```

## Module Reference

### `archmap.core.parser`

Entry point: `parse_project(project_path, virtual_files=None, config=None) -> ParsedProject`

Responsibilities:
- Load project configuration from `.archmap.toml` / `archmap.toml`
- Discover supported source files
- Dispatch each file to the language-specific parser
- Resolve imports to internal files or external packages

Current parser modules:

| Sub-parser | Language | Strategy |
|---|---|---|
| `python_parser.py` | Python | AST walk with regex fallback |
| `js_parser.py` | JavaScript | Lightweight scanner for `import`, `require`, `export ... from`, and dynamic `import()` |
| `ts_parser.py` | TypeScript | Same scanner as JS with TS extensions |
| `rust_parser.py` | Rust | Regex for `use`, `mod`, `extern crate` |
| `go_parser.py` | Go | Regex for grouped and direct imports |
| `generic_parser.py` | PHP / Java / C# / C / C++ | Reusable regex-based parser |

Configuration currently supported:

```toml
[analysis]
ignore_dirs = ["generated", "vendor"]
max_file_size_bytes = 1048576

[architecture.rules]
forbid = ["controller -> repository", "ui -> database"]

[risks.layer_order]
platform = 6
core = 3
```

### `archmap.core.graph`

Entry point: `build_graph(parsed_project) -> Graph`

Responsibilities:
- Convert parsed files into graph nodes and edges
- Create synthetic package nodes for external dependencies
- Compute `incoming` and `outgoing` counters on each node
- Deduplicate graph edges

### `archmap.core.analyzer`

Entry point: `analyze_graph(graph, layer_order=None) -> Report`

Sub-analyzers:

1. `cycle_detector.py`
Finds strongly connected components iteratively, avoiding Python recursion depth limits.

2. `complexity_analyzer.py`
Computes per-file complexity using outgoing, incoming, and total file connections.
Exposes:
- `complexityImports`
- `complexityDependents`
- `complexityConnections`
- `complexityScore`

3. `risk_analyzer.py`
Detects:
- God modules
- Dependency explosions
- Layer violations
- Top risk files

Layer order is built from defaults and can be extended or overridden via `.archmap.toml`.

4. `diff_analyzer.py`
Analyzes two git refs and produces:
- edge deltas
- cycle deltas
- complexity deltas
- risk summary deltas
- architecture health/style deltas
- file-level deltas (`added`, `removed`, `changed`)

Git ref loading uses `git cat-file --batch` to avoid one subprocess per file.

5. `architecture_analyzer.py`
Infers broad topology traits and lintable architecture signals:
- detected style (`monolith`, `modular_monolith`, `microservice_like`)
- detected layer tags from path structure
- custom rule violations from `[architecture.rules]`
- architecture health score and grade

### `archmap.exporters`

Output modules:
- `json_exporter.py`
- `mermaid_exporter.py`
- `cytoscape_exporter.py`

### `archmap.cli`

Entry point: `archmap.cli.main`

Current structure:
- `main.py` - bootstrap and routing
- `args.py` - CLI parser and default command behavior
- `commands.py` - command execution
- `reporting.py` - terminal rendering and diff formatting
- `server.py` - built-in HTTP server for the UI
- `defaults.py` - shared CLI defaults

### `archmap.web-ui`

The UI assets live in a single location:
- `src/archmap/web-ui/static/` for both the packaged Python distribution and the local Node development server

The root `web-ui/` folder also contains `server.js` and `dev-server.js`, which are
development-only helpers and are intentionally not duplicated under `src/`.

## Data Flow Types

```python
ParsedProject = {
    "projectRoot": str,
    "parsedFiles": list[ParsedFile],
}

ParsedFile = {
    "id": str,
    "label": str,
    "type": "file",
    "language": str,
    "dependencies": list[Dependency],
}

Dependency = {
    "id": str,
    "label": str,
    "type": "file" | "package",
}
```
