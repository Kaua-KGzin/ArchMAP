# archmap analyze

Analyzes a project and exports the dependency graph.

## Usage

```bash
archmap analyze [path] [options]
```

`path` defaults to `.` (current directory).

## Options

| Option | Default | Description |
|---|---|---|
| `--format` | `json` | Output format: `json`, `mermaid`, or `both` |
| `--out` | `.codeatlas/graph.json` | JSON output path |
| `--out-mermaid` | `.codeatlas/graph.mmd` | Mermaid output path |
| `--out-cytoscape` | `.codeatlas/graph-cytoscape.json` | Cytoscape output path |
| `--include-cytoscape` | off | Also write Cytoscape JSON |

## Examples

```bash
# Analyze current directory, JSON only
archmap analyze .

# Analyze specific path, all formats
archmap analyze ./src --format both

# Include Cytoscape export
archmap analyze . --format both --include-cytoscape

# Custom output paths
archmap analyze . --out reports/graph.json --out-mermaid reports/graph.mmd
```

## Output

Prints a summary to stdout:

```text
[ok] 42 files analyzed
[ok] 130 dependencies detected
[ok] 3 circular dependencies detected
Top complexity (imports):
  - src/main.py: 14 imports (87% score)
Top risk files:
  - src/core/__init__.py: score 42 (god_module)
[info] JSON report exported to .codeatlas/graph.json
```

See the [API Reference](../api.md) for the full JSON schema.
