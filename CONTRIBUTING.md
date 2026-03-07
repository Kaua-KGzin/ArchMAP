# Contributing to ArchMAP

Thanks for contributing! Please read our [Code of Conduct](./CODE_OF_CONDUCT.md) first.

## Prerequisites

- Python >= 3.11
- pip >= 23
- Git

## Setup

```bash
git clone https://github.com/Kaua-KGzin/code-arch-visualizer
cd code-arch-visualizer
python -m pip install -e ".[dev]"
```

## Running the tool locally

```bash
# Analyze a project
archmap analyze <path>

# Start the interactive Web UI
archmap serve <path>

# Compare two git refs
archmap diff HEAD~5 HEAD
```

## Running tests

```bash
pytest                       # all tests with coverage
pytest tests/test_cli.py     # single module
pytest -k "parser"           # filter by name
```

## Running lint

```bash
ruff check .
```

## Building the Windows executable (PyInstaller)

```bash
pip install pyinstaller
pyinstaller archmap.spec
# Output: dist/archmap.exe
```

## Branching model

- `main`: stable branch only
- `dev`: integration branch for upcoming release
- `feature/*`: one feature per branch
- `fix/*`: bugfix branches
- `docs/*`: documentation-only changes
- `release/*`: stabilization and release prep

Flow: `feature/* → dev → release/* → main`

## Development checklist before opening a PR

1. Branch from `dev` (or `main` for urgent fixes).
2. Implement changes with tests.
3. Run quality gates:

```bash
ruff check .
pytest
archmap analyze . --format both --out .codeatlas/local-graph.json --out-mermaid .codeatlas/local-graph.mmd --include-cytoscape
```

4. Update `CHANGELOG.md`, `README.md`, or `ROADMAP.md` if behavior changes.
5. Open a PR using the repository template.

## Coding guidelines

- Keep modules focused and composable.
- Prefer explicit data contracts for analyzer outputs (typed dicts).
- Add tests for any parser/analyzer/exporter behavior changes.
- Preserve CLI compatibility unless a major release justifies breaking changes.

