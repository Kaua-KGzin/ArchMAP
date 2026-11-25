# archmap diff

Compares architecture between two git refs **or two saved JSON snapshots** and prints a delta report.

## Usage

```bash
# Git refs
archmap diff <base_ref> <head_ref> [options]

# JSON snapshots (no git required)
archmap diff --snapshot-a <file> --snapshot-b <file> [options]
```

## Arguments

| Argument | Description |
|---|---|
| `base_ref` | The baseline git ref (branch, tag, or commit SHA) |
| `head_ref` | The comparison git ref |

## Options

| Option | Default | Description |
|---|---|---|
| `--repo` | `.` | Path to the git repository (git-ref mode only) |
| `--snapshot-a` | — | Path to the baseline JSON snapshot file |
| `--snapshot-b` | — | Path to the comparison JSON snapshot file |
| `--json` | off | Output full diff as JSON instead of a summary (same as `--format json`) |
| `--format` | `text` | `text`, `json`, or `markdown` (the pull-request comment, see [GitHub Action](../github-action.md)) |
| `--out` | stdout | Write the `json`/`markdown` output to this file |

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

# Compare two saved snapshots (cross-machine or cross-deploy)
archmap diff --snapshot-a before.json --snapshot-b after.json
archmap diff --snapshot-a before.json --snapshot-b after.json --json

# Render the pull-request comment (what the GitHub Action posts)
archmap analyze . --out head.json
archmap diff --snapshot-a base.json --snapshot-b head.json --format markdown --out report.md
```

Snapshots are the files `archmap analyze --out` writes. Since 1.6.0 they include
`findings`, each with a stable `key`, so the comparison can list **new** and
**resolved** findings instead of only count deltas. A snapshot written by 1.5.0
or older has no findings: the diff still works and marks
`findingsComparable: false`.

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

### Finding comparison (snapshots from 1.6.0+)

```json
{
  "findingsComparable": true,
  "findings": { "new": [ { "key": "structural_bottleneck|src/core/router.ts", "...": "..." } ],
                "resolved": [], "unchanged": 41 },
  "bottlenecks": { "new": [ "..." ] },
  "tests": { "baseTestedRatio": 0.729, "headTestedRatio": 0.701,
             "lostCoverage": [ { "file": "src/core/router.ts", "testedBy": ["tests/router.test.ts"] } ] },
  "grades": { "base": "C", "head": "D" }
}
```

A finding's `key` is its category plus the file, the source/target edge, or the
sorted members of a cycle, so it stays the same across runs even when IDs
(`ARCH-001`...) and the numbers in messages change.

## Use in CI

```yaml
- name: Architecture diff
  run: |
    archmap diff ${{ github.event.pull_request.base.sha }} ${{ github.sha }} --json \
      | tee archmap-diff.json
```
