# Contributing to ArchMAP

Thanks for contributing.

## Prerequisites

- Python >= 3.11
- pip >= 23

## Setup

```bash
python -m pip install -e ".[dev]"
```

## Branching model

- `main`: stable branch only
- `dev`: integration branch
- `feature/*`: one feature per branch
- `fix/*`: bugfix branches
- `docs/*`: documentation branches
- `release/*`: stabilization and release prep

Recommended flow:

`feature/* -> dev -> release/* -> main`

## Development checklist

1. Create a branch from `dev` (or `main` for urgent fixes).
2. Implement the change with tests.
3. Run quality gates:

```bash
ruff check .
pytest
archmap analyze . --format both --out .codeatlas/local-graph.json --out-mermaid .codeatlas/local-graph.mmd --include-cytoscape
```

4. Update docs (`README.md`, `ROADMAP.md`, `CHANGELOG.md`) if behavior changes.
5. Open a pull request using the repository template.

## Coding guidelines

- Keep modules focused and composable.
- Prefer explicit data contracts for analyzer outputs.
- Add tests for parser/analyzer/exporter behavior changes.
- Preserve CLI compatibility unless a major release justifies breaking changes.
