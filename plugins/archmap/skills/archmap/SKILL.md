---
name: archmap
description: Architecture-aware and reverse-engineering workflow backed by ArchMAP. Use before exploring code for a task (to get the right files to read), before editing, moving, or deleting a file (blast radius), when asked about structure, dependencies, cycles, layer rules, or coupling, when inspecting binaries, firmware, APKs, archives, databases, or unknown files (formats, imports, mitigations, strings, hexdump), when auditing secrets or AI-agent configuration, and before finishing a change (quality gates).
---

# ArchMAP — architecture-aware changes and static reverse engineering

ArchMAP builds a dependency graph of the project (Python, JS/TS, Rust, Go,
PHP, Java, C#, C/C++) and statically inspects any file (ELF, PE, Mach-O,
WebAssembly, APK/JAR, SQLite, archives, JSON/CSV). Answers are deterministic
and come with evidence; one call replaces dozens of file reads.

## Tools

Use the `archmap` MCP tools when available; otherwise run the CLI equivalent
(`pip install KG-ARCHMAP`). Every tool takes an optional `project_path`.

### Code and architecture

| Need | MCP tool | CLI fallback |
|---|---|---|
| Orientation at task start | `get_project_memory` | `archmap memory . --print` |
| Which files to read for a task | `get_relevant_context` (`task`, `budget_tokens`) | `archmap context "<task>" . --json` |
| How complete the graph is | `get_analysis_quality` | `archmap analyze . --format json` (`metrics.analysisQuality`) |
| Full health / risk report | `get_architecture_summary` | `archmap analyze . --format json` |
| All findings with stable IDs | `list_findings` (`domain`, `min_severity`) | `archmap analyze . --format json` (`findings`) |
| Imports, dependents, complexity of one file | `get_file_context` (`file`) | `archmap risk <file> . --json` |
| Who breaks if this file changes | `impact_analysis` (`file`, or `pkg:<name>`) | `archmap risk <file> . --json` |
| What an entrypoint pulls in, dead code | `trace_reachability` (`entrypoint`, `max_depth`) | `archmap trace <entry> . --unreachable` |
| Architecture delta of a change | `diff_architecture` (`base_ref`, `head_ref`) | `archmap diff HEAD~1 HEAD` |
| Quality gates (cycles, layers, god modules) | `run_checks` | `archmap analyze . --fail-on-risks` |
| Open ports mapped to the code that uses them | `get_network_exposure` (`target`) | `archmap expose <target> .` |

### Reverse engineering and security

| Need | MCP tool | CLI fallback |
|---|---|---|
| Identify and analyze a file or folder | `inspect_path` (`path`) | `archmap inspect <path> --json` |
| Raw bytes at an offset | `hexdump` (`path`, `offset`, `length`) | `archmap hexdump <file> -s 0x40 -n 128` |
| Strings worth reading (URLs, IPs, paths, keys) | `extract_strings` (`path`) | `archmap strings <file> --interesting` |
| Secrets and risky agent config | `audit_project` | `archmap audit . --json` |

## Workflow

1. **Orient.** Call `get_project_memory` once at task start. Then call
   `get_relevant_context` with the task in your own words (include any
   identifiers you know) and read files in the order returned; its snippets
   often answer the question without opening the file.
2. **Check the graph is trustworthy.** If `get_analysis_quality` reports
   confidence below `high`, or the memory lists parse failures, treat "no
   dependents" and small blast radii as lower bounds and say so.
3. **Before editing a file**, call `impact_analysis`. If the impacted set is
   large, keep its public interface stable or update every dependent in the
   same change. Before moving or deleting a file, list its dependents with
   `get_file_context`.
4. **When adding an import**, respect `.archmap.toml` layer rules; never
   introduce a cycle.
5. **Before reporting done**, call `run_checks` and, in a git repository,
   `diff_architecture`. Report new cycles, violations, or a health drop.

## Reverse-engineering workflow

1. `inspect_path` on the file (or the unpacked folder) first: format,
   hashes, linked libraries, imports/exports, mitigations, entropy, and the
   interesting strings. For a folder, its `graph` shows which binary links
   which library.
2. High entropy in an executable section, or a packer name, means the
   static view is incomplete; say so instead of guessing behavior.
3. Use `extract_strings` for more strings and `hexdump` to confirm a
   header, trailer, or embedded payload at a specific offset.
4. Quote `BIN-*` finding IDs with their evidence; never claim a binary is
   malicious from static data alone.

## Rules

- Findings carry stable IDs: `ARCH-*` (code), `QUAL-*` (analysis quality),
  `NET-*` (network), `BIN-*` (binaries/files), `SEC-*` (secrets), `AGENT-*`
  (agent configuration). Quote the ID and its evidence when reporting.
- File tools only read inside the project root; nothing is executed.
- Secret values are always redacted. Never try to recover or print them.
- `get_network_exposure` performs a live network scan: run it only when the
  user asks, against hosts they are authorized to scan.
