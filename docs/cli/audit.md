# archmap audit

Finds committed secrets and risky AI-agent configuration. Offline,
deterministic, and safe to share: secret values are always redacted.

```bash
archmap audit [path] [--json] [--out PATH] [--fail-on SEVERITY]
```

## Secrets (`SEC-*`)

Text files under `path` are matched against provider-specific rules
(private key blocks, AWS, GitHub, GitLab, Slack, Stripe, Google, Anthropic,
OpenAI keys, JWTs, credentials embedded in URLs) and `password = "..."`-style
assignments whose value looks real (placeholders such as `changeme` or
`${VAR}` and low-entropy values are ignored).

The audit is **git-aware**: a secret in a file git tracks is reported at
the rule's severity, while the same secret in an untracked file (a local,
gitignored `.env`) is downgraded two levels, because it was never
committed. Each finding's evidence states which case applies.

Skipped: VCS and dependency directories, lockfiles, minified bundles,
source maps, binary files (use [`archmap inspect`](inspect.md) for those),
and files over 1 MiB. Git history is not scanned.

## AI-agent configuration (`AGENT-*`)

AI coding agents execute the MCP servers, hooks, and permissions a
repository declares, and read instruction files as prompts, so that
configuration is part of the attack surface.

| Source | Check | Severity |
|---|---|---|
| `.mcp.json`, `.cursor/mcp.json`, `.vscode/mcp.json`, `.gemini/settings.json` | MCP server over `http://`/`ws://` to a non-loopback host | medium |
| | `npx`/`uvx` package without a pinned version (or `@latest`) | low |
| | Literal credential in `env` or `headers` (instead of `${VAR}`) | high |
| `.claude/settings.json`, `.claude/settings.local.json` | `defaultMode: bypassPermissions` | high |
| | `Bash`, `Bash(*)`, `*` pre-approved | high |
| | Interpreter wildcard pre-approved (`Bash(python *)`, `Bash(node:*)`, ...) — arbitrary code without a prompt | medium |
| | `enableAllProjectMcpServers: true` | medium |
| | Hook that pipes a download into a shell (`curl … \| sh`, `base64 -d \| sh`) | high |
| | Hook that makes network calls | medium |
| `**/hooks/hooks.json` (plugins) | Same hook checks | high/medium |
| `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.cursorrules`, `.windsurfrules`, `.github/copilot-instructions.md` | Invisible Unicode (bidi overrides, zero-width, tag characters): read by the model, invisible to reviewers ("Rules File Backdoor") | high |

## CI usage

```bash
archmap audit . --fail-on high      # exit 2 on any high/critical finding
archmap audit . --json --out audit.json
```

## Example

```text
$ archmap audit .
[ok] Audited 207 text files in /home/me/project (git-aware)
  Secrets: 0 | Agent config: 1
  Findings (1):
    [medium  ] AGENT-001  .claude/settings.local.json pre-approves 'Bash(python *)' (arbitrary command execution without a prompt)
```
