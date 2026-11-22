# Contributing to ArchMAP

Thanks for contributing! Please read our [Code of Conduct](./code-of-conduct.md) first.

## Prerequisites

- Python >= 3.11
- pip >= 23
- Git

## Setup

```bash
git clone https://github.com/Kaua-KGzin/ArchMAP
cd ArchMAP
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

- `main`: the only long-lived branch; every pull request targets it
- `feat/*`: one feature per branch
- `fix/*`: bugfix branches
- `perf/*`: performance work with no behaviour change
- `docs/*`: documentation-only changes
- `release/<version>`: the version-bump pull request for a release
- `feature/*`: legacy alias of `feat/*`

Flow: `feat/*` (or `fix/*`, `perf/*`, `docs/*`) -> `main`; releases are tags
on `main`. Do not stack pull requests: base each one on `main`, even when it
depends on another (see the
[Branching Strategy](https://github.com/Kaua-KGzin/ArchMAP/blob/main/docs/BRANCHING.md)).

## Development checklist before opening a PR

1. Branch from `main`.
2. Implement changes with tests.
3. Run quality gates:

```bash
ruff check .
pytest
archmap analyze . --format both --out .codeatlas/local-graph.json --out-mermaid .codeatlas/local-graph.mmd --include-cytoscape
python -m archmap.cli.main analyze . --fail-on-risks
```

4. Update `CHANGELOG.md` (under `[Unreleased]`, mirrored in `docs/changelog.md`),
   `README.md`, or `ROADMAP.md` if behavior changes.
5. Open a PR using the repository template.

## Coding guidelines

- Keep modules focused and composable.
- Prefer explicit data contracts for analyzer outputs (typed dicts).
- Add tests for any parser/analyzer/exporter behavior changes.
- Preserve CLI compatibility unless a major release justifies breaking changes.

## Original distribution attribution

ArchMAP is originally distributed by **Kaua Gabriel** (Kaua-KGzin).

When redistributing source code or binaries, preserve:
- `LICENSE`
- `NOTICE.md`

