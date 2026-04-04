# ArchMAP JSON API Reference

This document describes the main report shape produced by `archmap analyze`
and served by the web UI at `/api/graph`.

## Main report fields

```json
{
  "projectRoot": "/absolute/path/to/project",
  "generatedAt": "2026-03-30T12:00:00+00:00",
  "nodes": [ ... ],
  "edges": [ ... ],
  "metrics": { ... },
  "cycles": [ ... ],
  "risks": { ... },
  "architecture": { ... },
  "insights": { ... },
  "explanation": { ... }
}
```

## Important sections

### `nodes`

List of graph nodes. File nodes include values such as:

- `id`
- `label`
- `type`
- `language`
- `incoming`
- `outgoing`
- `isCircular`
- `impact`

### `edges`

List of dependencies with:

- `source`
- `target`
- `isCircular` when applicable

### `metrics`

Project-wide summary values such as:

- `filesAnalyzed`
- `totalDependencies`
- `externalDependencies`
- `circularDependencyCount`
- `complexity`
- `criticalFiles`
- `coupling`

### `risks`

Architecture risk output such as:

- `god_modules`
- `layer_violations`
- `dependency_explosions`
- `top_risk_files`
- `thresholds`

### `architecture`

Higher-level architecture analysis such as:

- detected style
- health score and grade
- active rules
- rule violations

### `insights`

Human-readable architecture interpretation:

- `status`
- `message`
- `problems`
- `actions`

### `explanation`

Simple project explanation for CLI and UI:

- `architecture`
- `simple`
- `technical`

## Related commands

- `archmap analyze`
- `archmap explain`
- `archmap risk`
- `archmap improve`
- `archmap serve`

## Live endpoints

When `archmap serve` is running:

```text
GET  /api/graph
GET  /api/history
GET  /api/project
GET  /api/health
POST /api/reanalyze
```
