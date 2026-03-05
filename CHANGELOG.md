# Changelog

All notable changes to this project are documented in this file.

## [0.1.3] - 2026-03-05

### Added
- **Single File Analysis:** Added support to natively read and resolve dependencies starting from a single file instead of a full directory scan, reducing overhead and providing concise maps for entry files.
- **Standalone Windows Executable (`.exe`):** Bundled the CLI and the Web UI into a completely portable, zero-dependency Windows executable via PyInstaller. The interactive graph server (`archmap.exe serve .`) operates directly without a Python runtime requirement.

### Changed
- Rebuilt architecture file crawler (`file_utils.discover_source_files`) to intercept root files before deep recursive searches.

## [0.2.0-beta.0] - 2026-03-04

### Added
- Full Python implementation under `src/archmap`.
- New Python CLI with commands:
  - `analyze`
  - `serve`
  - `diff`
- Architecture risk engine with:
  - god module detection
  - layer violation detection
  - dependency explosion detection
- Cytoscape exporter (`cytoscape_exporter.py`).
- `pyproject.toml` with package metadata and scripts.
- Pytest suite for parser, analyzer, exporters, CLI, and diff.
- CI pipeline with Ruff lint + pytest coverage + smoke analysis.

### Changed
- Canonical runtime migrated from Node.js to Python.
- Repository structure aligned to `src/archmap` layout.
- Branch strategy documented as:
  - `feature/* -> dev -> release/* -> main`

### Notes
- JavaScript implementation is no longer the primary runtime.
- Next target: `v0.3.0` architecture policy and trend analysis.
