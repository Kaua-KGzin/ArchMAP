# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0-beta.0] - 2026-03-04

### Added
- ArchMAP branding across CLI, UI, and docs.
- Complexity heatmap mode in the web UI.
- Mermaid exporter (`graph TD`) with sanitized identifiers.
- CLI format selection via `--format json|mermaid|both`.
- New CLI option `--out-mermaid`.
- CI workflow with tests and smoke analysis.
- Project governance files: roadmap, contributing, PR template.

### Changed
- Package name changed to `archmap`.
- CLI now exposes `archmap` as primary command.
- `code-arch` remains available as compatibility alias.
- Analyzer now includes `complexityImports` and `complexityScore` per file node.

### Notes
- Next planned release: `v0.2.0` on `2026-03-10`.