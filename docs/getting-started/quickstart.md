# Quick Start

## 1. Install

```bash
pip install archmap
```

## 2. Analyze a project

```bash
archmap analyze /path/to/your/project
```

Sample output:

```text
[ok] 42 files analyzed
[ok] 130 dependencies detected
[ok] 3 circular dependencies detected
Top complexity (imports):
  - src/archmap/cli/main.py: 14 imports (87% score)
  - src/archmap/core/analyzer/risk_analyzer.py: 6 imports (40% score)
Top risk files:
  - src/archmap/core/__init__.py: score 42 (god_module, circular_dependency)
[info] JSON report exported to .codeatlas/graph.json
[info] Mermaid graph exported to .codeatlas/graph.mmd
```

## 3. Open the interactive Web UI

```bash
archmap serve /path/to/your/project
```

A browser window opens automatically at `http://localhost:3000`.

Use `--port` to change the port:

```bash
archmap serve . --port 8080
```

Use `--no-open` to prevent the browser from opening:

```bash
archmap serve . --no-open
```

## 4. Try the included example

```bash
archmap serve examples/sample-project
```

This runs the bundled [sample project](https://github.com/Kaua-KGzin/code-arch-visualizer/tree/main/examples/sample-project) and opens the UI so you can explore a pre-built graph right away.

## 5. Compare two git commits

```bash
archmap diff HEAD~5 HEAD
```

Output:

```text
Comparing HEAD~5 -> HEAD
+12 dependencies
+1 circular dependencies
complexity +18.00%
+0 layer violations
+1 god modules
+0 dependency explosions
```
