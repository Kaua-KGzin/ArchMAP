---
name: archmap
description: Architecture-aware workflow for changing code safely. Use before editing, moving, or deleting a file (to check its blast radius), when planning a refactor, when asked about project structure, dependencies, cycles, layer rules, or coupling, and before finishing a change (to run architecture quality gates). Backed by the ArchMAP MCP server or the `archmap` CLI.
---

# ArchMAP — architecture-aware changes

ArchMAP builds a dependency graph of the project (Python, JS/TS, Rust, Go,
PHP, Java, C#, C/C++) and answers structural questions deterministically.
Prefer it over reading many files to infer structure: one call returns what
would otherwise take dozens of file reads.

## Tools

Use the `archmap` MCP tools when they are available. Otherwise run the CLI
equivalent (install with `pip install KG-ARCHMAP`). Every tool takes an
optional `project_path`; it defaults to the project root.

| Need | MCP tool | CLI fallback |
|---|---|---|
| Orientation at task start | `get_project_memory` | `archmap memory . --print` |
| Full health / risk report | `get_architecture_summary` | `archmap analyze . --format json` |
| Imports, dependents, complexity of one file | `get_file_context` (`file`) | `archmap risk <file> . --json` |
| Who breaks if this file changes | `impact_analysis` (`file`, or `pkg:<name>`) | `archmap risk <file> . --json` |
| What an entrypoint pulls in, dead code | `trace_reachability` (`entrypoint`, `max_depth`) | `archmap trace <entry> . --unreachable` |
| Architecture delta of a change | `diff_architecture` (`base_ref`, `head_ref`) | `archmap diff HEAD~1 HEAD` |
| Quality gates (cycles, layers, god modules) | `run_checks` | `archmap analyze . --fail-on-risks` |
| Open ports mapped to the code that uses them | `get_network_exposure` (`target`) | `archmap expose <target> .` |

## Workflow

1. **Orient.** At the start of a task, call `get_project_memory` once. Treat
   it as a precomputed snapshot; do not re-explore the codebase to rebuild
   what it already says.
2. **Before editing a file**, call `impact_analysis` on it. If the risk tier
   is high or the impacted set is large, tell the user which dependents are
   affected and keep the public interface stable, or update every dependent
   in the same change.
3. **Before moving, renaming, or deleting a file**, call `get_file_context`
   to list every dependent that must be updated.
4. **When adding an import**, respect the layer rules in `.archmap.toml`
   (`[architecture.rules]`). Do not introduce an import that creates a cycle
   or points from a lower layer to a higher one.
5. **Before reporting the task done**, call `run_checks` and, inside a git
   repository, `diff_architecture`. Report any new cycle, layer violation,
   or health-score drop to the user instead of hiding it.

## Rules

- Findings carry stable IDs (`ARCH-*` for code, `NET-*` for network) and a
  `confidence`. Quote the ID when reporting a finding.
- `get_network_exposure` performs a live network scan. Run it only when the
  user asks for it, and only against hosts they are authorized to scan.
- If a file reports unresolved imports, the graph around it is incomplete;
  say so rather than claiming a file has no dependents.
