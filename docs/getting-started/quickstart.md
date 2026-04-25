# Quick Start

## 1. Analyze a repository

```bash
archmap analyze /path/to/project --format both --include-cytoscape
```

Typical output:

```text
[ok] 42 files analyzed
[ok] 130 dependencies detected
[ok] 3 circular dependencies detected
Top complexity (imports):
  - src/archmap/cli/main.py: 14 imports (87% score)
Top risk files:
  - src/core/__init__.py: score 42 (god_module, circular_dependency)
```

## 2. Start the interactive UI

```bash
archmap serve /path/to/project --port 3000
```

Optional:

```bash
archmap serve . --host 127.0.0.1 --port 8080 --no-open
```

## 3. Use quality gates in CI

```bash
archmap analyze . --fail-on-risks --top 10
```

Exit code `2` means quality gate failed.

## 4. Compare two git refs

```bash
archmap diff HEAD~5 HEAD
```

## 5. Run sample project

```bash
archmap serve examples/sample-project
```
