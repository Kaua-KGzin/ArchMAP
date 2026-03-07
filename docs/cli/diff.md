# archmap diff

Compares the architecture between two git refs and prints a delta report.

## Usage

```bash
archmap diff <base_ref> <head_ref> [options]
```

## Arguments

| Argument | Description |
|---|---|
| `base_ref` | The baseline git ref (branch, tag, or commit SHA) |
| `head_ref` | The comparison git ref |

## Options

| Option | Default | Description |
|---|---|---|
| `--repo` | `.` | Path to the git repository |
| `--json` | off | Output full diff as JSON instead of a summary |

## Examples

```bash
# Compare last 5 commits
archmap diff HEAD~5 HEAD

# Compare two branches
archmap diff main feature/new-api

# Compare two tags
archmap diff v0.1.0 v0.2.0

# Use JSON output for CI integration
archmap diff HEAD~1 HEAD --json
```

## Output

### Default (human-readable)

```text
Comparing HEAD~5 -> HEAD
+12 dependencies
+1 circular dependencies
complexity +18.00%
+0 layer violations
+1 god modules
+0 dependency explosions
```

### JSON (`--json`)

```json
{
  "edges": { "base": 118, "head": 130, "delta": 12 },
  "cycles": { "base": 2,   "head": 3,   "delta": 1  },
  "complexity": { "base": 0.72, "head": 0.85, "deltaPercent": 18.0 },
  "riskSummary": {
    "layerViolationsDelta": 0,
    "godModulesDelta": 1,
    "dependencyExplosionsDelta": 0
  }
}
```

## Use in CI

```yaml
- name: Architecture diff
  run: |
    archmap diff ${{ github.event.pull_request.base.sha }} ${{ github.sha }} --json \
      | tee archmap-diff.json
```
