# archmap trace

Traces all files reachable from an entrypoint through the dependency graph using BFS (breadth-first search).

## Usage

```bash
archmap trace <entrypoint> [path] [options]
```

## Arguments

| Argument | Description |
|---|---|
| `entrypoint` | Entry file to trace from (relative path or filename) |
| `path` | Project root to analyze (default: `.`) |

## Options

| Option | Default | Description |
|---|---|---|
| `--unreachable` | off | Also list files that are **not** reachable from the entrypoint |
| `--max-depth N` | unlimited | Only include files reachable within N dependency hops |
| `--json` | off | Output results as JSON |
| `--out PATH` | — | Write JSON output to a file |
| `--parallel` | on | Enable parallel file parsing |

## Examples

```bash
# Trace from a specific file
archmap trace src/main.py .

# Show unreachable files too
archmap trace src/main.py . --unreachable

# Limit to direct and indirect deps within 3 hops
archmap trace src/main.py . --max-depth 3

# JSON output
archmap trace src/main.py . --json

# Save JSON to file
archmap trace src/main.py . --out trace-report.json
```

## Output

### Default (human-readable)

```text
[trace] From: src/main.py
Reachable: 46/64 files (71.9% coverage)
Dependency tree:
src/main.py
  - src/config.py
  - src/cli/args.py
    - src/cli/commands.py
    - src/core/analyzer.py
```

### JSON (`--json`)

```json
{
  "entrypoint": "src/main.py",
  "reachableCount": 46,
  "unreachableCount": 18,
  "totalFiles": 64,
  "coveragePercent": 71.9,
  "reachable": [
    { "file": "src/main.py", "depth": 0 },
    { "file": "src/config.py", "depth": 1 }
  ],
  "unreachable": ["src/legacy/old_module.py"]
}
```

## Use cases

- **Dead code hunting**: files that appear in `--unreachable` are not transitively imported from your entrypoint and may be unused.
- **Blast radius**: understand which files could be affected by a change to the entrypoint.
- **Deployment scope**: verify which modules are actually loaded by a specific binary or service entry.

## Web UI

The Trace view is also available in the interactive web UI (`archmap serve`).
Select any node and click **Trace from here**, or use the Trace panel in the nav rail.
