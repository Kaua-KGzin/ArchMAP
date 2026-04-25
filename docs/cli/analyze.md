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
| `--top` | `5` | Number of top complexity/risk items printed to terminal |
| `--fail-on-cycles` | off | Exit code `2` when cycles are found |
| `--fail-on-layer-violations` | off | Exit code `2` when layer violations are found |
| `--fail-on-god-modules` | off | Exit code `2` when god modules are found |
| `--fail-on-dependency-explosions` | off | Exit code `2` when dependency explosions are found |
| `--fail-on-risks` | off | Exit code `2` when any cycle/risk category is found |

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

# CI quality gate
archmap analyze . --fail-on-risks --top 10
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
