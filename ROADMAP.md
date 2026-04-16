# ArchMAP Roadmap

## v0.6.0 (current)

- Zero-config CLI flow strengthened around:
  - `archmap analyze`
  - `archmap explain`
  - `archmap risk`
  - `archmap improve`
- Automatic architecture suggestion engine with simple folder proposals.
- Live watch mode for terminal and web UI.
- Windows-safe CLI output and broader parser stability.
- Security hardening: subprocess timeouts, request body limits, path
  traversal guards, CSP headers, thread-safe SSE listeners.
- Professional open-source governance: SECURITY.md, CODEOWNERS, py.typed.
- CLI banner suppressed when output is piped for clean JSON workflows.

## Next up

- Stronger domain clustering for the automatic architect mode.
- Optional CSV and SARIF exports for CI and reporting workflows.
- Incremental analysis cache for larger repositories.
- Richer API documentation for insights, explanation, impact, and improve payloads.
- `--quiet` flag for fully silent operation in CI pipelines.
- Dynamic health badge endpoint (`/api/badge`) for README embedding.

## Longer-term

- Stable plugin API for custom parsers and analyzers via entry points.
- Editor integration and code-action helpers for refactor suggestions.
- More precise monorepo and workspace alias resolution across ecosystems.
- GraphML and Graphviz DOT export formats.
- GitHub Action for automatic PR architecture diff comments.
