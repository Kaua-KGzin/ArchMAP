# archmap temporal

Detects temporal coupling — file pairs that change together frequently in git history, revealing hidden dependencies that the static import graph cannot see.

## Usage

```bash
archmap temporal [path] [options]
```

## Arguments

| Argument | Description |
|---|---|
| `path` | Project root to analyze (default: `.`) |

## Options

| Option | Default | Description |
|---|---|---|
| `--min-commits N` | `2` | Minimum number of co-changes to include a pair |
| `--top N` | `20` | Maximum number of pairs to show |
| `--json` | off | Output results as JSON |

## Examples

```bash
# Detect temporal coupling in the current directory
archmap temporal .

# Raise the signal threshold (only pairs that changed together 5+ times)
archmap temporal . --min-commits 5

# Show the top 30 pairs in JSON format
archmap temporal . --top 30 --json
```

## Output

### Default (human-readable)

```text
Temporal coupling — top co-changed file pairs
(files that change together frequently may have hidden coupling)

  src/core/analyzer.py  <-->  src/core/graph_builder.py
    co-changes: 12  |  coupling strength: 0.923

  src/cli/commands.py  <-->  src/cli/args.py
    co-changes: 9  |  coupling strength: 0.818
```

### JSON (`--json`)

```json
[
  {
    "fileA": "src/core/analyzer.py",
    "fileB": "src/core/graph_builder.py",
    "coChanges": 12,
    "commitsA": 13,
    "commitsB": 13,
    "couplingStrength": 0.923
  }
]
```

**Fields:**

| Field | Description |
|---|---|
| `fileA` / `fileB` | The two files in the co-change pair |
| `coChanges` | Number of commits where both files changed |
| `commitsA` / `commitsB` | Total commits that touched each file |
| `couplingStrength` | `coChanges / min(commitsA, commitsB)` — a value from 0 to 1 |

## How it works

ArchMAP runs `git log --name-only --diff-filter=ACDMR` and counts how often each pair of files appears in the same commit. Files with high co-change frequency are likely coupled in ways not captured by import statements (shared configuration, coordinated API contracts, generated code, etc.).

## Use cases

- **Hidden coupling**: find modules that are always modified together despite no direct import.
- **Refactoring targets**: high coupling strength between unrelated layers suggests a leaky abstraction.
- **Onboarding**: understand which files form natural change clusters.
- **Test coverage gaps**: if a source file and a test file never co-change, the test may be lagging.

## Requirements

Requires a git repository with at least one commit. The command reads git history only — no network access needed.
