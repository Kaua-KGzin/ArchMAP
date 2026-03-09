# ArchMAP — JSON API Reference

This document describes the output schema produced by `archmap analyze` and consumed by the Web UI (`/api/graph`).

---

## `archmap analyze` — JSON output

Default path: `.codeatlas/graph.json`

```json
{
  "projectRoot": "/absolute/path/to/project",
  "generatedAt": "2026-03-07T12:00:00+00:00",

  "nodes": ["src/main.py", "src/utils.py"],
  "edges": [["src/main.py", "src/utils.py"]],

  "metrics": { ... },
  "cycles":  [ ... ],
  "risks":   { ... },

  "detailed": {
    "nodes": [ ... ],
    "edges": [ ... ]
  }
}
```

---

## Top-level fields

### `nodes` — `string[]`

Flat list of all node IDs (file paths and `pkg:*` names). Convenient for quick enumeration.

### `edges` — `[source: string, target: string][]`

Flat list of dependency pairs.

---

## `metrics`

```json
{
  "filesAnalyzed": 42,
  "totalDependencies": 130,
  "externalDependencies": 18,
  "circularDependencyCount": 3,
  "complexity": [
    {
      "file": "src/archmap/cli/main.py",
      "imports": 14,
      "score": 0.87
    }
  ],
  "criticalFiles": [
    {
      "file": "src/archmap/core/__init__.py",
      "dependents": 9
    }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `filesAnalyzed` | `int` | Count of source files parsed |
| `totalDependencies` | `int` | Total edge count (internal + external) |
| `externalDependencies` | `int` | Count of external package nodes |
| `circularDependencyCount` | `int` | Number of detected cycles |
| `complexity` | `ComplexityEntry[]` | Top files by normalized outgoing-import score (descending) |
| `criticalFiles` | `CriticalFileEntry[]` | Top files by incoming dependency count (descending) |

#### `ComplexityEntry`

| Field | Type | Description |
|---|---|---|
| `file` | `string` | Relative file ID |
| `imports` | `int` | Outgoing dependency count |
| `score` | `float` | Normalized score `[0, 1]` |

#### `CriticalFileEntry`

| Field | Type | Description |
|---|---|---|
| `file` | `string` | Relative file ID |
| `dependents` | `int` | Count of files that depend on this file |

---

## `cycles` — `string[][]`

Each element is a list of file IDs forming a circular dependency group.

```json
[
  ["src/a.py", "src/b.py"],
  ["src/x.py", "src/y.py", "src/z.py"]
]
```

---

## `risks`

```json
{
  "god_modules": [ ... ],
  "layer_violations": [ ... ],
  "dependency_explosions": [ ... ],
  "top_risk_files": [ ... ],
  "thresholds": {
    "god_module_min_outgoing": 8,
    "dependency_explosion_min_connections": 12
  }
}
```

### `god_modules`

Files with an outgoing dependency count ≥ max(8, p90).

```json
[{ "file": "src/archmap/cli/main.py", "outgoing": 12 }]
```

### `layer_violations`

Detected lower-level → higher-level dependency violations.

```json
[
  {
    "source": "utils/helpers.py",
    "target": "cli/main.py",
    "sourceLayer": "utils",
    "targetLayer": "cli",
    "rule": "lower-level module should not depend on higher-level module"
  }
]
```

### `dependency_explosions`

Files with `incoming + outgoing` ≥ max(12, p90).

```json
[
  {
    "file": "src/core/__init__.py",
    "incoming": 9,
    "outgoing": 6,
    "totalConnections": 15
  }
]
```

### `top_risk_files`

Up to 15 files ranked by composite risk score.

```json
[
  {
    "file": "src/core/__init__.py",
    "riskScore": 42,
    "dependents": 9,
    "outgoing": 6,
    "signals": ["god_module", "circular_dependency"]
  }
]
```

| Signal | Meaning |
|---|---|
| `circular_dependency` | Part of at least one cycle |
| `god_module` | Too many outgoing dependencies |
| `dependency_explosion` | High total connection count |
| `layer_violations:N` | Committed N layer-order violations |

### `thresholds`

Dynamic per-project thresholds used for risk detection.

```json
{
  "god_module_min_outgoing": 8,
  "dependency_explosion_min_connections": 12
}
```

---

## `detailed`

Full node and edge objects for the Web UI and Cytoscape integration.

### `detailed.nodes`

```json
[
  {
    "id": "src/archmap/cli/main.py",
    "label": "src/archmap/cli/main.py",
    "type": "file",
    "language": "python",
    "folder": "src",
    "outgoing": 12,
    "incoming": 0,
    "isCircular": false,
    "complexity": 0.87
  },
  {
    "id": "pkg:requests",
    "label": "requests",
    "type": "package",
    "language": "package",
    "folder": "(external)",
    "outgoing": 0,
    "incoming": 3,
    "isCircular": false
  }
]
```

### `detailed.edges`

```json
[
  {
    "id": "src/main.py->src/utils.py",
    "source": "src/main.py",
    "target": "src/utils.py",
    "isCircular": false
  }
]
```

---

## Web UI live endpoint

When `archmap serve` is running, the same report is available at:

```
GET http://localhost:3000/api/graph   → application/json (full report)
GET http://localhost:3000/api/health  → {"status":"ok"}
```
