# archmap audit

Finds committed secrets, insecure code patterns, and risky AI-agent
configuration. Offline, deterministic, and safe to share: secret values are
always redacted.

```bash
archmap audit [path] [--json] [--out PATH] [--sarif PATH] [--no-code] [--fail-on SEVERITY]
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

**Context-aware.** Where a secret sits changes what it means, so findings
are kept but ranked accordingly (the evidence says which case applied):

| Location | Effect |
|---|---|
| Test code (`tests/`, `*.spec.ts`, `*Tests.cs`, `test_*.py`, ...) | severity −2, confidence ×0.5 |
| Templates and docs (`.env.example`, `*.sample`, `docs/`, `*.md`) | severity −2, confidence ×0.5 |
| CI configuration (`.github/workflows/`, `.gitlab-ci.yml`) | severity −1, confidence ×0.7 |

A committed private key is never downgraded. URLs whose password is a
well-known placeholder (`postgresql://user:password@localhost/db`,
`${DB_PASSWORD}`) are not reported at all.

Skipped: VCS and dependency directories (`node_modules`), caches, lockfiles,
minified bundles, source maps, binary files (use
[`archmap inspect`](inspect.md) for those), and files over 1 MiB. Unlike
`archmap analyze`, the audit **does** scan `tests/` and `examples/`, and
scans build output (`dist/`, `build/`, `target/`, ...) when git tracks it —
a committed bundle leaks a key just as well. Git history is not scanned.

## Insecure code patterns (`CODE-*`)

A lightweight, offline SAST pass over comment-stripped source. Each rule
targets a sink that is dangerous by itself or with dynamic input, carries a
CWE id and a fix, and occurrences are grouped into one finding per rule and
file. It is pattern-based, not data-flow analysis: a `CODE` finding marks a
line a reviewer should look at, and its confidence says how sure the rule is.

| Area | Examples | CWE |
|---|---|---|
| Command/code injection | `subprocess(..., shell=True)`, `os.system`, `` exec(`git ${x}`) ``, `Runtime.exec`, `sh -c` in Go, `system(var)` in C, `eval`/`new Function` | 78, 95 |
| SQL injection | f-string / concatenated SQL in `execute`, `query`, `$queryRawUnsafe`, `FromSqlRaw($"...")`, `executeQuery("..." + x)`, `fmt.Sprintf` in `db.Query` | 89 |
| Unsafe deserialization | `pickle.loads`, `yaml.load` without `SafeLoader`, `BinaryFormatter`, `TypeNameHandling`, `ObjectInputStream`, `unserialize` | 502 |
| TLS verification off | `verify=False`, `rejectUnauthorized: false`, validation callback `=> true`, `InsecureSkipVerify`, `danger_accept_invalid_certs` | 295 |
| Weak crypto | MD5/SHA-1, DES/RC4/ECB | 327, 328 |
| Web | `innerHTML`/`dangerouslySetInnerHTML`/`document.write`, `jwt.decode` for trust, CORS any-origin with credentials, Flask `debug=True` | 79, 347, 942, 489 |
| Memory safety (C/C++) | `gets`, `strcpy`/`strcat`/`sprintf`, `scanf("%s")`, non-literal `printf` format, `alloca` | 242, 120, 134 |

Precision rules learned from real repositories:

- `system("pause")` and other constant commands are not reported.
- `sprintf` with a numeric-only literal format is reported as **low**, not medium.
- ``innerHTML = `...` `` templates whose every `${...}` goes through a
  sanitizer (`esc*`, `escape*`, `sanitize*`, `DOMPurify.sanitize`, `Number(...)`)
  are not reported.
- Docstrings and comments never match.
- Test code and vendored third-party code (`vendor/`, `third_party/`, `ext/`,
  `imgui/`, ...) are reported two severity levels lower.

Suppress a reviewed line with a comment on the same or previous line:
`archmap-ignore`, or another tool's marker (`nosemgrep`, `nosec`,
`NOSONAR`, `codeql[...]`). Skip the pass entirely with `--no-code`.

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
archmap audit . --sarif audit.sarif  # GitHub code scanning (CWE tags + security-severity)
```

Upload the SARIF file with `github/codeql-action/upload-sarif` to see
findings as code-scanning alerts on pull requests.

## Example

```text
$ archmap audit .
[ok] Audited 207 text files in /home/me/project (git-aware)
  Secrets: 0 | Code: 0 | Agent config: 1
  Findings (1):
    [medium  ] AGENT-001  .claude/settings.local.json pre-approves 'Bash(python *)' (arbitrary command execution without a prompt)
```
