# archmap analyze

Analyzes a project and exports the dependency graph.

## Usage

```bash
archmap analyze [path] [options]
```

`path` defaults to `.` (current directory).

By default, ArchMAP skips common generated or non-production folders such as
`build/`, `dist/`, `node_modules/`, `site/`, `tests/`, and `examples/`.
If you want to inspect one of those areas directly, point `archmap analyze`
to that folder itself.

ArchMAP also reads an optional `.archmap.toml` (or `archmap.toml`) from the
project root:

```toml
[analysis]
ignore_dirs = ["generated", "vendor"]
max_file_size_bytes = 1048576

[architecture.rules]
forbid = ["controller -> repository", "ui -> database"]
allow = ["controller -> service", "service -> repository"]

[risks.layer_order]
platform = 6
core = 3
```

The default outputs are written under `.codeatlas/`, which is treated as a
generated local artifact and should stay out of source-control changes.

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
| `--fail-on-custom-rules` | off | Exit code `2` when custom architecture rules are violated |
| `--fail-on-risks` | off | Exit code `2` when any cycle/risk category is found |
| `--min-health` | unset | Exit code `2` when architecture health drops below the given score |

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

# Strict architecture gate
archmap analyze . --fail-on-custom-rules --min-health 75
```

## Output

Prints a summary to stdout:

```text
[ok] 42 files analyzed
[ok] 130 dependencies detected
[ok] 3 circular dependencies detected
[ok] Average instability 58%
[ok] Architecture health 78/100 (B)
[ok] Detected style: modular_monolith (74% confidence)
[ok] 2 custom architecture rules configured
[warn] 1 custom architecture rule violations detected
Top complexity (imports/dependents):
  - src/main.py: 14 imports, 9 dependents, 23 total, 61% instability (87% score)
Top risk files:
  - src/core/__init__.py: score 42 (god_module)
[info] JSON report exported to .codeatlas/graph.json
```

See the [API Reference](../api.md) for the full JSON schema.
