# ArchMAP Roadmap

## Released

### v0.7.2 (current)
- **Web UI multi-view navigation**: nav rail switches between Graph, Insights, and Rules & Layers panels.
- **Layer Diagram tab**: hierarchical BFS layout of the dependency graph.
- **Dependency Matrix tab**: top-25 files rendered as a colour-coded matrix (dependency, circular, self).
- **Insights panel**: live architecture metrics summary.
- **Rules & Layers panel**: layer rule cards from `.archmap.toml`.

### v0.7.1
- Web UI complete visual refresh (Inter + JetBrains Mono, indigo design system, health gauge, KPI tiles).
- Cytoscape bundled locally — removes CDN dependency and fixes CSP.
- CI fixes for Windows EXE build and PyPI trusted publisher.

### v0.7.0
- TypeScript parser with triple-slash reference support.
- Reusable GitHub Action (`action.yml`) with SARIF upload.
- Pre-commit hook via `archmap-check` entrypoint.
- Incremental parse cache — unchanged files skipped on re-analysis.
- `--sarif` flag for SARIF 2.1.0 export.

### v0.6.x
- Security hardening: subprocess timeouts, path traversal guards, CSP headers.
- Windows-safe CLI output and broader parser stability.
- Professional open-source governance (SECURITY.md, CODEOWNERS, py.typed).

---

## Next up (v0.7.x / v0.8.0)

- **CLI coverage** — `tests/test_args.py`, `tests/test_commands.py`, `tests/test_reporting.py` to bring coverage ≥ 85%.
- **Server security** — `/api/project` path validation (`allowed_roots`), rate limit on `/api/reanalyze`.
- **`--quiet` flag** — fully silent mode for CI pipelines.
- **Dead-code detector** — surface unreferenced files and exports.
- **Architectural Blueprint** — target-state enforcement from `.archmap.toml` layer rules.
- **Dynamic health badge** — `/api/badge` endpoint for README embedding.

## Longer-term (v0.9.0+)

- Plugin SDK for custom parsers and analyzers via entry points.
- Change coupling detector via `git log` analysis.
- Complexity budget enforcement per module.
- Multi-repo topology support.
- WebSocket-based live UI refresh.
- GraphML and Graphviz DOT export formats.
