# ArchMAP Roadmap

## v0.2.0 (current beta)

- Python migration completed (`src/archmap` as canonical source)
- New command: `archmap diff <base> <head>`
- Architecture risk detection:
  - god modules
  - layer violations
  - dependency explosion
- CI pipeline with lint + tests + coverage + smoke

## v0.3.0

- Layer configuration file support (`archmap.toml`)
- More precise language resolvers (workspace aliases, monorepos)
- Risk trend report over commit history
- SARIF export for CI integration

## v0.4.0

- Drift detection between architecture snapshots
- Architecture policy checks (allowed/blocked dependencies)
- Incremental analysis cache for large repositories

## v1.0.0

- Stable plugin system for custom parsers/analyzers
- Official VS Code extension integration
- Full release hardening and compatibility guarantees
