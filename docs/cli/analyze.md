# archmap analyze

Analyzes a project and exports the dependency graph.

## Usage

```bash
archmap analyze [path] [options]
```

`path` defaults to `.`.

ArchMAP automatically skips common generated folders such as `build/`, `dist/`,
`node_modules/`, `.venv/`, `tests/`, and `examples/`. Optional project rules
can be loaded from `.archmap.toml` or `archmap.toml`.

## Options

| Option | Default | Description |
|---|---|---|
| `--format` | `json` | Output format: `json`, `mermaid`, or `both` |
| `--out` | `.codeatlas/graph.json` | JSON output path |
| `--out-mermaid` | `.codeatlas/graph.mmd` | Mermaid output path |
| `--out-cytoscape` | `.codeatlas/graph-cytoscape.json` | Cytoscape output path |
| `--include-cytoscape` | off | Also write Cytoscape JSON |
| `--no-subgraphs` | off | Disable Mermaid layer subgraphs |
| `--impact <path>` | unset | Simulate the impact of changing one file |
| `--include-insights` | on | Print human-oriented architecture insights |
| `--include-explanation` | on | Print an automatic project explanation |
| `--top` | `5` | Number of top complexity/risk items printed to terminal |
| `--parallel` | on | Enable parallel file parsing |
| `--fail-on-cycles` | off | Exit code `2` when cycles are found |
| `--fail-on-layer-violations` | off | Exit code `2` when layer violations are found |
| `--fail-on-god-modules` | off | Exit code `2` when god modules are found |
| `--fail-on-dependency-explosions` | off | Exit code `2` when dependency explosions are found |
| `--fail-on-custom-rules` | off | Exit code `2` when custom architecture rules are violated |
| `--fail-on-risks` | off | Exit code `2` when any cycle/risk category is found |
| `--min-health` | unset | Exit code `2` when architecture health drops below the given score |

## Examples

```bash
archmap analyze .
archmap analyze ./src --format both
archmap analyze . --impact src/auth/login.ts
archmap analyze . --fail-on-risks --top 10
archmap analyze . --fail-on-custom-rules --min-health 75
```

## Output

Terminal summary:

```text
[ok] 42 files analyzed
[ok] 130 dependencies detected
[ok] 3 circular dependencies detected
[ok] Architecture health 78/100 (B)
[insight] Architectural reading
[explain] Project summary
Top risk files:
  - src/core/__init__.py: score 42 (god_module)
```

See the [API Reference](../api.md) for the JSON report shape.
