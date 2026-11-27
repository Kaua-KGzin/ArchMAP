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
| `--estimate` | off | Predict time and memory (and the reductions a budget would force) without analyzing; add `--format json` for JSON on stdout |
| `--time-budget SECONDS` | none | Soft time budget for the whole run; `0` = no limit. Overrides `[analysis.limits] time_budget_seconds` |

### Time budget and `[analysis.limits]`

```toml
# .archmap.toml
[analysis.limits]
time_budget_seconds = 60   # 0 = no limit; negative values are rejected
```

This is separate from `[analysis.budgets]`, which sets coupling budgets for the
`--fail-on-budget-violations` gate. The time budget is **soft**: parsing is never
cut short, and a run can overshoot. When time runs out, impacted-file lists are
dropped (`impactCount` and `risk` stay exact, nodes are marked
`impactedFilesTruncated`) and centrality is sampled to 64 files or skipped. Each
reduction is a `QUAL-*` finding (category `budget_reduction`) and, for
`archmap analyze` and every other command that runs an analysis, a
`[budget] ...` line on stderr (never with `--quiet`). Reduced runs are never
cached, so the cache is shared by every budget, the MCP server's included. Stored impact lists are always capped at 200 files; `--impact PATH`
prints the full list. Details, numbers and the MCP default in
[Performance](../performance.md).

### Which files are analysed

ArchMAP walks the project and keeps files with a supported extension. These
directories are skipped without being entered:

- the built-in set: `.git`, `node_modules`, `dist`, `build`, `target`,
  `coverage`, `.venv`, `venv`, `__pycache__`, the tool caches, `site`,
  `tests`, `examples`;
- every name in `[analysis] ignore_dirs` in `.archmap.toml`. For a path entry
  such as `src/gen`, the last segment is what matches;
- whatever git ignores (`.gitignore` at any level, `.git/info/exclude`, the
  global excludes file), asked from git itself, so negations behave as in
  `git status`. Tracked files are always kept, even when they match a
  pattern. Outside a git work tree, or without git installed, this step is a
  no-op.

To analyse git-ignored files too (generated code you want in the graph, for
example), turn the git step off:

```toml
[analysis]
respect_gitignore = false
```

`archmap expose` still scans git-ignored `.env` files for endpoints, since
that is where connection strings usually live.

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
| `timingsMs` | Time per stage in milliseconds: `discover`, `parse`, `cycles`, `impact`, `risk`, `testMapping`, `centrality`, `findings` |
| `budget` / `reductions` | Present only when a time budget is active: `{seconds, source}` and what was reduced |

Gaps also become `QUAL-*` entries in the unified `findings` list
(`parse_failure`, `decode_failure`, `oversized_skipped`, and
`low_resolution` for a language with at least 5 imports and under 50%
resolved), and `archmap memory` adds the confidence line and warnings to the
agent digest so an agent knows when "no dependents" is a lower bound.

### Test mapping (`metrics.testMapping`)

ArchMAP records which project files have a test referring to them. A test
counts for a file when it imports the file, or when it is named after it by
the language convention: `test_foo.py` / `foo_test.py`, `foo_test.go`,
`foo.spec.ts` / `foo.test.tsx`, `FooTest.java` / `FooTests.cs`. The naming
rule covers Go and Java tests, which share the package under test and often
import nothing from it.

A file is treated as a test when it sits under a `tests/`, `test/`,
`__tests__/`, `spec/` or `specs/` directory, or matches one of those names.
`tests/` stays out of the graph: its files are read only for this mapping,
and they never become nodes or change any risk score. Imports inside them
resolve against the project's top-level Python packages, so a `src/` layout
works from `tests/` without an `__init__.py`.

| Field | Meaning |
|---|---|
| `testFiles` | Test files found (in the graph or in test directories) |
| `sourceFiles` / `testedFiles` / `untestedFiles` | Non-test files, and how many have at least one test |
| `testedRatio` | `testedFiles / sourceFiles` |

Each file node also carries `testedBy`, the list of test files that refer to
it. The highest-risk files with an empty `testedBy` become `TEST-*` findings
(`untested_critical_file`, severity `medium`, at most 10). Their confidence is
`0.7` because the mapping is static and cannot see a file tested only
indirectly, through another module. A project with no test files gets no
`TEST-*` findings.

This is a structural signal, not line coverage: use it to spot important
code that no test even names, and a coverage tool for how much of it runs.

.NET test projects (`Acme.Api.Tests/`, `Acme.UnitTests/`,
`Acme.IntegrationTests/`) count as test directories too.

### Structural bottlenecks (`metrics.centrality`)

Fan-in and fan-out say how many files touch a file. They do not say how many
dependency chains pass *through* it. ArchMAP computes betweenness centrality
on the file graph and stores it as `betweenness` on every file node. The
value is the share of connected import chains (ordered file pairs joined by
a chain of imports) whose shortest route goes through the file, so `0.3`
means "on 30% of the chains".

The value is normalised by connected pairs rather than by every pair of files:
dependency graphs are sparse, and the textbook normalisation would make every
score look negligible.

| Field | Meaning |
|---|---|
| `method` | `exact`, or `sampled` above 1000 files (256 source files, fixed seed, so reruns agree) |
| `nodes` / `connectedPairs` | Files in the graph, and import chains between them (estimated when sampled) |
| `top` | Up to 10 files with the highest `betweenness` |

Files on at least 10% of the chains become `GRAPH-*` findings
(`structural_bottleneck`, domain `code`, at most 5). Severity is `medium` from
25% and `low` below. Confidence is `0.9`, or `0.8` when sampled. They require
a graph with at least 50 chains, and test files are never reported.
Betweenness does not change `riskScore` or the health score.

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
