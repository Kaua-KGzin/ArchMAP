## Summary

- What does this PR change?
- Why is this change needed?

## Scope checklist

- [ ] Parser behavior
- [ ] Graph/analyzer behavior
- [ ] CLI behavior
- [ ] Web UI behavior
- [ ] Docs updated (if needed)

## Validation

- [ ] `ruff check .`
- [ ] `pytest`
- [ ] `archmap analyze . --format both --out .codeatlas/pr-graph.json --out-mermaid .codeatlas/pr-graph.mmd --include-cytoscape`
- [ ] Manual UI smoke check (`archmap serve .`)

## Release impact

- [ ] Backward compatible
- [ ] Breaking change
- [ ] No release impact
