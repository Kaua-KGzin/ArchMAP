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
| `python_parser.py` | Python | `ast` walk — `import X`, `from X import Y` (regex on `SyntaxError`) |
| `js_parser.py` | JavaScript | tree-sitter / regex — `import`, `require`, `export … from`, dynamic `import()` |
| `ts_parser.py` | TypeScript | tree-sitter / regex — JS rules + triple-slash references |
| `rust_parser.py` | Rust | tree-sitter / regex — `use`, `mod`, `extern crate` |
| `go_parser.py` | Go | tree-sitter / regex — single + block imports |
| `php_parser.py` | PHP | tree-sitter / regex — `use`, `require`, `include` |
| `java_parser.py` | Java | tree-sitter / regex — `import`, `import static`, wildcards |
| `csharp_parser.py` | C# | tree-sitter / regex — `using`, `global using`, aliases |
| `cpp_parser.py` | C / C++ | tree-sitter / regex — `#include <…>` vs `#include "…"` |

### Tree-sitter as a resilient primary parser

Except for Python (which uses the standard-library `ast`), every parser routes
through `ts_engine.try_extract(language, source)`:

1. **Tree-sitter first.** When the optional `[tree-sitter]` extra is installed, a
   real AST is used. Grammars load **independently** — a single missing or broken
   grammar does not disable the others (`ts_engine.language_available(name)`).
2. **Automatic per-file fallback.** `try_extract` returns `None` — asking the
   parser to use its comment-aware regex fallback — whenever tree-sitter cannot be
   trusted for that file: the grammar is unavailable, parsing/querying raised, or
   the parse contained syntax errors *and* recovered no imports. A problematic file
   is never silently dropped from the graph.
3. **Regex fallback.** Without the extra, every parser uses a string-aware regex
   pass that strips comments before matching, so import-like text in comments does
   not create phantom dependencies.

### Dependency resolution

Resolution (`_resolve_python_dependency`, `_resolve_js_ts_dependency`, etc.) maps each import to:

- An **internal file ID** (`type: "file"`) when the path exists in the project
- An **external package** (`type: "package"`, id prefixed with `pkg:`) otherwise

Resolution is configuration-aware where the ecosystem provides it:

| Language | Configuration honored |
|---|---|
| Python | absolute `from pkg import name` checked as submodule (`pkg/name.py`, `pkg/name/__init__.py`) before the package root |
| JS / TS | `tsconfig.json` / `jsconfig.json` `baseUrl` + `paths` aliases (e.g. `@app/*` → `src/*`) |
| Go | `go.mod` module path and local `replace` directives |
| PHP | `composer.json` PSR-4 autoload map (longest prefix wins) |
| Java | package → directory, wildcard packages, and inner classes (`Outer.Inner` → `Outer.java`) |
| C# | namespace → directory; alias `using X = …` resolves the right-hand namespace |
| C / C++ | local includes relative to the file, then `include/`-style suffix matching |

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
