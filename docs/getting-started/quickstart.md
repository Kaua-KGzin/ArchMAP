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
[ok] Architecture health 78/100 (B)
Top risk files:
  - src/core/__init__.py: score 42 (god_module, circular_dependency)
```

## 2. Ask ArchMAP to explain the project

```bash
archmap explain /path/to/project
```

Typical simple map:

```text
auth -> users, payments
payments -> gateway
```

## 3. Inspect one file before changing it

```bash
archmap risk src/auth/login.ts /path/to/project
```

Use this before refactors to understand blast radius and dependency pressure.

## 4. Get a reorganization suggestion

```bash
archmap improve /path/to/project --out-script .codeatlas/refactor.ps1
```

This suggests folders such as `/auth`, `/payments`, `/users`, and can write a
helper script with move commands.

## 5. Start the interactive UI

```bash
archmap serve /path/to/project --port 3000
```

Optional:

```bash
archmap serve . --host 127.0.0.1 --port 8080 --no-open
archmap serve . --watch
```

## 6. Use quality gates in CI

```bash
archmap analyze . --fail-on-risks --top 10
```

Exit code `2` means the quality gate failed.

## 7. Compare two git refs

```bash
archmap diff HEAD~5 HEAD
```
