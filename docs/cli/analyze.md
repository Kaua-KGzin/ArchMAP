# archmap analyze

Analyzes a project and exports the dependency graph.

## Usage

```bash
archmap analyze [path] [options]
```

`path` defaults to `.` (current directory).

## Options

### Export

| Option | Default | Description |
|---|---|---|
| `--format` | `json` | Output format: `json`, `mermaid`, or `both` |
| `--out` | `.codeatlas/graph.json` | JSON output path |
| `--out-mermaid` | `.codeatlas/graph.mmd` | Mermaid output path |
| `--out-cytoscape` | `.codeatlas/graph-cytoscape.json` | Cytoscape output path |
| `--include-cytoscape` | off | Also write Cytoscape JSON |
| `--no-subgraphs` | off | Disable subgraph grouping by layer in Mermaid output |
| `--sarif` | off | Export a SARIF 2.1.0 report alongside other outputs |
| `--out-sarif` | auto | Path for the SARIF output file |

### Output control

| Option | Default | Description |
|---|---|---|
| `--top N` | `5` | Number of top complexity/risk items printed to terminal |
| `--summary-format` | `text` | Terminal summary style: `text`, `table`, or `markdown` |
| `--quiet`, `-q` | off | Suppress banner, insights, and hints — print only violations (useful in CI) |
| `--include-insights` | on | Print human-oriented architectural insights |
| `--no-include-insights` | — | Disable insights output |
| `--include-explanation` | on | Print an automatic project explanation |
| `--no-include-explanation` | — | Disable explanation output |
| `--show-unresolved[=N]` | off | Print unresolved import details; `N` controls how many are shown (default 20) |

### Graph filtering

| Option | Default | Description |
|---|---|---|
| `--ignore-external` | off | Exclude external package nodes and their edges; focuses graph on internal structure |
| `--impact PATH` | — | Simulate the architectural impact of changing a specific file |

### Performance

| Option | Default | Description |
|---|---|---|
| `--parallel` / `--no-parallel` | on | Enable/disable parallel file parsing |
| `--no-cache` | off | Skip loading and saving cached analysis results |

### CI quality gates

| Option | Default | Description |
|---|---|---|
| `--fail-on-cycles` | off | Exit code `2` when circular dependencies are detected |
| `--fail-on-layer-violations` | off | Exit code `2` when layer violations are detected |
| `--fail-on-god-modules` | off | Exit code `2` when god modules are detected |
| `--fail-on-dependency-explosions` | off | Exit code `2` when dependency explosions are detected |
| `--fail-on-custom-rules` | off | Exit code `2` when custom architecture rule violations are detected |
| `--fail-on-risks` | off | Exit code `2` when any cycle or risk category is detected |
| `--fail-on-budget-violations` | off | Exit code `2` when any file exceeds coupling budgets |
| `--min-health N` | — | Exit code `2` when architecture health score falls below N (0–100) |
| `--min-resolution-rate PCT` | — | Exit code `2` when import resolution rate is below PCT percent (0–100) |
| `--min-coverage PCT` | — | Exit code `2` when fewer than PCT percent of discovered source files were parsed into the graph |
| `--max-parse-failures N` | — | Exit code `2` when more than N source files fail to parse |
| `--max-outgoing-per-file N` | — | CLI override: max outgoing dependencies per file (overrides `.archmap.toml`) |
| `--max-incoming-per-file N` | — | CLI override: max incoming dependencies per file (overrides `.archmap.toml`) |

## Examples

```bash
# Analyze current directory
archmap analyze .

# Analyze specific path, all formats
archmap analyze ./src --format both

# Table-format summary
archmap analyze . --summary-format table

# Markdown summary (paste into a PR description)
archmap analyze . --summary-format markdown

# Show which imports failed to resolve
archmap analyze . --show-unresolved

# Focus on internal structure only (hide external packages)
archmap analyze . --ignore-external

# Full CI quality gate
archmap analyze . \
  --fail-on-cycles \
  --fail-on-layer-violations \
  --fail-on-budget-violations \
  --max-outgoing-per-file 20 \
  --min-health 70 \
  --min-resolution-rate 80 \
  --quiet

# Coupling budgets from config file (set in .archmap.toml)
archmap analyze . --fail-on-budget-violations

# SARIF output for GitHub Code Scanning
archmap analyze . --sarif --out-sarif results/archmap.sarif

# Impact analysis for a specific file
archmap analyze . --impact src/core/__init__.py
```

## Output

Prints a summary to stdout:

```text
[ok] 42 files analyzed
[ok] 130 dependencies detected
[ok] 0 circular dependencies detected
[ok] Average instability 38%
[ok] Import resolution rate 97% (4 unresolved)
[ok] Analysis confidence 99% (42/42 files parsed)
[ok] Architecture health 84/100 (B)
Top complexity (imports/dependents):
  - src/main.py: 14 imports, 3 dependents, 17 total, 82% instability (87% score)
Top risk files:
  - src/core/__init__.py: score 42 (god_module)
[info] JSON report exported to .codeatlas/graph.json
```

### Analysis quality (`metrics.analysisQuality`)

Every metric above is only as trustworthy as the parse behind it. Files that
fail to parse, aren't valid UTF-8, or exceed `max_file_size_bytes` used to
vanish from the graph silently; they are now counted and reported:

| Field | Meaning |
|---|---|
| `filesDiscovered` / `filesParsed` | Source files found vs. files that made it into the graph |
| `coverage` | `filesParsed / filesDiscovered` |
| `resolutionRate` | Share of imports resolved to a file or package |
| `confidence` / `confidenceLevel` | `coverage × (0.6 + 0.4 × resolutionRate)`; `high` ≥ 0.9, `medium` ≥ 0.7, else `low` |
| `parseFailures` | `{file, language, error}` for each file whose parser raised |
| `decodeFailures` / `oversizedSkipped` | Files skipped before parsing |
| `languages` | Per language: files, imports, resolved, failures, resolutionRate |
| `warnings` | Human-readable summary of every gap |
| `timingsMs` | Discovery and parse time |

Gaps also become `QUAL-*` entries in the unified `findings` list
(`parse_failure`, `decode_failure`, `oversized_skipped`, and
`low_resolution` for a language with at least 5 imports and under 50%
resolved), and `archmap memory` adds the confidence line and warnings to the
agent digest so an agent knows when "no dependents" is a lower bound.

### Table format (`--summary-format table`)

```text
──────────────────────────────────────────────────────
Metric                  Value
──────────────────────────────────────────────────────
Files analyzed          42
Dependencies            130
Circular dependencies   0
Average instability     38%
Import resolution       97% (4 unresolved)
Architecture health     84/100 (B)
Detected style          layered (82%)
──────────────────────────────────────────────────────
```

See the [API Reference](../api.md) for the full JSON schema.
