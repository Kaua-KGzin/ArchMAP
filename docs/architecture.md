# ArchMAP — Architecture Overview

## Pipeline summary

Every `archmap` command runs the same core pipeline:

```
Source files on disk
     │
     ▼
┌─────────────────────────────────────┐
│  Parser   (archmap.core.parser)     │  Reads source, extracts imports
└────────────────┬────────────────────┘
                 │  ParsedProject
                 ▼
┌─────────────────────────────────────┐
│  Graph Builder (archmap.core.graph) │  Builds directed node/edge graph
└────────────────┬────────────────────┘
                 │  Graph dict
                 ▼
┌─────────────────────────────────────┐
│  Analyzer  (archmap.core.analyzer)  │  Cycles, complexity, risks
└────────────────┬────────────────────┘
                 │  Report dict
                 ▼
┌─────────────────────────────────────┐
│  Exporters (archmap.exporters)      │  JSON / Mermaid / Cytoscape
└─────────────────────────────────────┘
```

---

## Module reference

### `archmap.core.parser`

**Entry point:** `parse_project(project_path, virtual_files=None) → ParsedProject`

Discovers all source files under `project_path` and calls the language-specific sub-parser for each:

| Sub-parser | Language | Strategy |
|---|---|---|
| `python_parser.py` | Python | AST walk — captures `import X`, `from X import Y` |
| `js_parser.py` | JavaScript | Regex — `import`, `require`, `export ... from`, dynamic `import()` |
| `ts_parser.py` | TypeScript | Same as JS |
| `rust_parser.py` | Rust | Regex — `use`, `mod`, `extern crate` |

Dependency resolution (`_resolve_python_dependency`, `_resolve_js_ts_dependency`, etc.) maps each import string to:
- An **internal file ID** (`type: "file"`) when the path exists in the project
- An **external package** (`type: "package"`, id prefixed with `pkg:`) otherwise

For Python absolute `from pkg import name` imports, each imported name is checked as a potential submodule (`pkg/name.py`, `pkg/name/__init__.py`) before falling back to the package root.

---

### `archmap.core.graph`

**Entry point:** `build_graph(parsed_project) → Graph`

Converts a `ParsedProject` into a directed graph:

- **Nodes** — one per file (plus synthetic package nodes for external deps)
  - Fields: `id`, `label`, `type`, `language`, `folder`, `outgoing`, `incoming`, `isCircular`
- **Edges** — one per resolved dependency
  - Fields: `id` (`"source->target"`), `source`, `target`, `isCircular`

Edge deduplication is handled at this stage.

---

### `archmap.core.analyzer`

**Entry point:** `analyze_graph(graph) → Report`

Three sub-analyzers run in sequence:

#### 1. `cycle_detector.py`
Finds strongly connected components using a DFS variant.
Returns `cycles: list[list[str]]` — each inner list is a set of file IDs forming a cycle.

#### 2. `complexity_analyzer.py`
Annotates each node with a `complexity` score `[0, 1]` (normalized outgoing edge count).
Produces `metrics.complexity` (top files by score) and `metrics.criticalFiles` (top files by incoming count).

#### 3. `risk_analyzer.py`
Detects three architecture smell categories:

| Risk | Detection | Threshold |
|---|---|---|
| **God module** | `outgoing ≥` p90 or 8 | Dynamic, per-project |
| **Dependency explosion** | `incoming + outgoing ≥` p90 or 12 | Dynamic, per-project |
| **Layer violation** | Lower-rank layer imports higher-rank layer | Hardcoded `LAYER_ORDER` map |

Built-in layer ranks (higher = closer to user):

```
cli / web-ui / api / interface  →  5 (entry)
app / application               →  4
core / domain                   →  3
exporters / adapters            →  2
utils / shared                  →  1 (foundation)
```

A violation fires when a layer with rank `< N` imports from a layer with rank `> N`.

Every file receives a composite `riskScore`:

```
score = incoming×2 + outgoing
      + 10 (if in a cycle)
      + 8  (if god module)
      + 6  (if dependency explosion)
      + 4× (layer violations count)
```

---

### `archmap.exporters`

| Exporter | Output |
|---|---|
| `json_exporter.py` | Structured JSON (see `docs/api.md`) |
| `mermaid_exporter.py` | Mermaid `graph TD` diagram |
| `cytoscape_exporter.py` | Cytoscape.js `elements` format |

---

### `archmap.cli`

`main.py` is the CLI entry point (registered as `archmap` and `code-arch` scripts).

Commands:
- `analyze` — parse + export, print summary
- `serve` — analyze + start an HTTP server serving the Web UI and `/api/graph`
- `diff` — analyze two git refs, print delta metrics
- `version` — print version

Static file resolution order for `serve`:
1. PyInstaller `_MEIPASS` bundle
2. `importlib.resources.files("archmap") / "web-ui" / "static"` (installed wheel)
3. `src/archmap/../../../web-ui/static` (source checkout)

---

### `archmap.utils`

- `file_utils.py` — filesystem helpers: `discover_source_files`, `normalize_file_id`, `to_file_id`, extension sets, `first_segment`, `percentile`

---

## Data flow types (simplified)

```python
ParsedProject = {
    "projectRoot": str,
    "parsedFiles": list[ParsedFile],
}

ParsedFile = {
    "id": str,           # relative posix path e.g. "src/archmap/cli/main.py"
    "label": str,
    "type": "file",
    "language": str,
    "dependencies": list[Dependency],
}

Dependency = {
    "id": str,           # e.g. "src/archmap/core/__init__.py" or "pkg:requests"
    "label": str,
    "type": "file" | "package",
}
```
