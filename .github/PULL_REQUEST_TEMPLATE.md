## Summary

Describe the purpose of this PR in 2-5 lines.

## Branch Flow

- Source branch: `feat/*` or `fix/*` or `docs/*`
- Target branch: `dev` (default) or `release/*` (stabilization only)

## Checklist

- [ ] I ran `python -m ruff check .`
- [ ] I ran `python -m pytest -q`
- [ ] I ran smoke analysis:
  - `python -m archmap.cli.main analyze . --format both --out .codeatlas/local-graph.json --out-mermaid .codeatlas/local-graph.mmd --include-cytoscape`
- [ ] I updated docs/changelog when behavior changed
- [ ] I did not commit local runtime logs or build artifacts
- [ ] I preserved attribution files (`LICENSE`, `NOTICE.md`)

## Impact

- Breaking change: `yes` / `no`
- New CLI flags/endpoints:
- Risk to release:

## Validation Notes

Paste key command outputs or explain test coverage for this PR.
