# archmap context / commands

Commands built for AI agents.

## archmap context

Ranks the files to read for a task and packs them into a token budget.

```bash
archmap context "<task>" [path] [--budget TOKENS] [--max-files N] [--json]
```

1. Every source file is tokenized identifier-aware (`parseHTTPResponse` →
   `parse`, `http`, `response`, plus the whole identifier), with path
   segments weighted 3×, and scored against the task with BM25.
2. Part of each match's score spreads to its direct imports and dependents
   in the dependency graph — the files an agent would otherwise discover one
   read at a time. These come back with `role: "neighbor"`.
3. Files are packed in score order into `--budget` tokens (≈ bytes / 4). The
   best file is always included, even alone over budget.

Each file includes why it was picked, its dependents/imports count, its
risk score, and its best-matching lines, which often answer the question
without opening the file.

```text
$ archmap context "MCP hexdump path confinement outside project root" src
[ok] 4 file(s), ~8994 tokens (budget 9000) for: MCP hexdump path confinement outside project root
   1. archmap/cli/mcp_server.py  [match, ~8759 tokens, 1 dependents]
        - matches mcp, hexdump, path, outside, project, root
        L199: """Resolve ``user_path`` against the project root and refuse anything outside it.
```

Pure Python and deterministic (no embeddings, no network). The same engine
backs the `get_relevant_context` MCP tool.

## archmap commands

```bash
archmap commands          # one line per command
archmap commands --json   # machine-readable catalog
```

The JSON catalog lists every subcommand with its options (names, help,
defaults, choices, whether each takes a value), generated from the live
argument parser, so it never drifts from the real CLI. Agents that only have
a shell can discover ArchMAP's full surface from one call.
