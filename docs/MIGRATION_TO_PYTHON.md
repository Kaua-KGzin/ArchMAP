# Migration to Python

## What changed

ArchMAP moved its canonical implementation from Node.js to Python.

- New package root: `src/archmap`
- New CLI entrypoint: `archmap.cli.main`
- New build metadata: `pyproject.toml`
- New test stack: `pytest` + `pytest-cov`
- New lint stack: `ruff`

## Why this migration was made

1. Improve maintainability of the analysis engine.
2. Make packaging and distribution simpler for CLI users.
3. Standardize quality checks with lint + coverage in CI.
4. Speed up architecture-focused feature development (`diff`, risk scoring, policy checks).

## Backward compatibility

- CLI alias `code-arch` is still available.
- Existing exported formats (JSON, Mermaid) are preserved.
- Cytoscape export was added explicitly as a first-class exporter.

## New capabilities introduced during migration

- `archmap diff <base> <head>` for architecture delta analysis between git refs.
- Risk ranking engine (`top_risk_files`) with signals:
  - circular dependency
  - god module
  - layer violation
  - dependency explosion

## What is still pending

- Additional parser depth for Java, Go, and C#.
- Policy configuration file (`archmap.toml`) for custom layering rules.
