# Market trends research — October 2026

Snapshot of GitHub's trending repositories (monthly: all languages, Python,
TypeScript, Rust, Go; plus the weekly overall list), collected on
2026-10-17, and what each signal means for ArchMAP. Star counts are as
GitHub displayed them that day.

## 1. What is trending

Almost every top repository this month is tooling **for AI coding agents**,
not for humans directly. Five clusters account for most of the growth:

| Cluster | Representative repos (stars gained this month) | What they ship |
|---|---|---|
| **Agent skills & plugins** | `affaan-m/ECC` (+23.0k), `addyosmani/agent-skills` (+12.8k), `mattpocock/skills` (+11.9k/week), `anthropics/claude-plugins-official` (+4.8k), `cursor/plugins` (+4.0k), `vercel-labs/skills` (+3.6k), `xingkongliang/skills-manager` (+1.7k) | `SKILL.md` folders and plugin manifests installable into 50+ agents with one command |
| **Agent memory** | `vectorize-io/hindsight` (+26.9k), `thedotmack/claude-mem` (+7.7k), `topoteretes/cognee` (+1.8k), `Gentleman-Programming/engram` (+0.7k) | Persistent per-project memory that consolidates observations over time instead of replaying history |
| **Context-window economy** | `mksglu/context-mode` (+7.0k), `ranxianglei/billion-context` (weekly), `VectifyAI/PageIndex` (+3.6k) | Keep raw data out of the prompt; index it (SQLite FTS5/BM25) and return only what matches the task |
| **Verified, agent-driven security** | `cloudflare/security-audit-skill` (+24.8k), `vxcontrol/pentagi` (+6.3k), `trufflesecurity/trufflehog` (+0.7k), ECC's AgentShield | Recon → hunt → independent verification → schema-validated `findings.json` |
| **Agent runtimes & sandboxes** | `NVIDIA/OpenShell` (+7.9k), `microsoft/mxc` (+1.5k), `coder/coder` (+2.7k), `github/gh-aw` | Policy-driven isolation; the agent's own config (MCP servers, hooks, permissions) treated as attack surface |

Supporting signals: `HKUDS/CLI-Anything` (+4.0k) codifies "agent-native CLI"
conventions (`--json` everywhere, a `SKILL.md` per CLI, deterministic
output); `cathrynlavery/diagram-design` (+9.0k/week) shows demand for
self-contained HTML/SVG diagrams agents can emit.

## 2. Where ArchMAP already stands

ArchMAP is unusually well positioned: it already has a deterministic
dependency graph, an 8-tool MCP server, `archmap memory` (session-start
digest), a unified findings model with stable IDs and confidence scores
(v1.3.0), SARIF export, and a code↔network correlation layer. Most trending
agent tools are prompt-driven; ArchMAP is a **deterministic engine** those
agents can call. The gap is distribution and agent ergonomics, not core
capability.

## 3. Opportunities

Ranked by impact × effort. "Zero-dep" means implementable with the Python
standard library, preserving ArchMAP's `dependencies = []`.

### P0 — Ship ArchMAP as an agent plugin + skill  ✅ done in this change

*Signal:* skills/plugins cluster. *Gap:* users had to hand-edit MCP config
and hooks from `docs/cli/memory.md`.

- `plugins/archmap/` — Claude Code plugin: MCP server, `SessionStart` hook
  that injects `archmap memory --print`, and an `archmap` skill that tells
  the agent *when* to call which tool (impact before edit, checks before
  done).
- `.claude-plugin/marketplace.json` — `/plugin marketplace add Kaua-KGzin/ArchMAP`.
- Same `SKILL.md` installs into Cursor, Codex, OpenCode, etc. via
  `npx skills add Kaua-KGzin/ArchMAP --skill archmap`.
- `tests/test_agent_plugin.py` fails CI if the plugin version drifts from
  the package or the skill names an MCP tool that doesn't exist.

**Next:** submit to Anthropic's plugin directory and `cursor/plugins`.

### P1 — Task-scoped context retrieval (`get_relevant_context`)

*Signal:* context-mode, billion-context, PageIndex. *Idea:* a new MCP tool
`get_relevant_context(task, budget_tokens)` that ranks files by BM25 over
paths, symbols, and import specifiers (stdlib `sqlite3` FTS5, zero-dep),
re-ranks by graph proximity and risk score, and returns the minimal file set
plus each file's dependents within a token budget. This turns ArchMAP from
"describe the architecture" into "tell the agent exactly which files to read
for this task" — the measurable win context-mode reports (≈98% fewer bytes in
context) but grounded in a real dependency graph instead of text search
alone.

*Risk:* FTS5 is compiled into CPython's bundled SQLite on all mainstream
platforms, but check Termux; fall back to a pure-Python BM25.

### P1 — Snapshot history and "learning" memory

*Signal:* hindsight, claude-mem, cognee. *Idea:* persist each analysis as a
compact snapshot under `.archmap/history/` (the network-snapshot item already
on the roadmap, generalized to code), then derive **observations** across
snapshots: "`core/engine.py` risk rose 5 snapshots in a row", "this cycle
has existed for 40 days", "layer violation introduced in commit X". Feed the
top observations into `archmap memory`. This is hindsight's
observation-consolidation idea applied to deterministic data — no LLM needed,
so no hallucinated memory.

### P1 — Verified-findings pipeline for agentic security audits

*Signal:* cloudflare/security-audit-skill (+24.8k, the month's #1). Its
Phase 1 (recon) produces `architecture.md`, trust boundaries, and input
surfaces; ArchMAP can produce those deterministically. Ideas:

- `archmap recon` — emit an attack-surface map: entrypoints (`trace`),
  network-facing code (`expose`), external packages, and per-file blast
  radius, as Markdown + JSON an audit skill can consume.
- Extend `Finding` with `status: confirmed | needs_validation | rejected`
  and publish a JSON Schema (`archmap findings --schema`), matching the
  pattern agents already validate against.

### P2 — Agent-config audit (`archmap agents audit`)

*Signal:* AgentShield, NVIDIA OpenShell, microsoft/mxc. Scan `.mcp.json`,
`.claude/settings*.json`, plugin hooks, and `.cursor/` for risky patterns:
`curl | sh` in hooks, wildcard Bash permissions, MCP servers over `http://`
to non-loopback hosts, secrets in plain config. Emits `AGENT-*` findings
through the unified model. Natural extension of `expose`: an MCP server is a
network service the codebase depends on.

### P2 — Secret exposure findings

*Signal:* trufflehog. `core/exposure/endpoint_scanner.py` already reads
`.env` and config files for endpoints; adding high-entropy / known-prefix
secret detection there yields `SEC-*` findings at almost no cost. Keep it
offline (no live verification) and conservative to avoid false-positive
noise.

### P2 — Agent-native CLI polish

*Signal:* CLI-Anything. Add `archmap commands --json` (machine-readable
catalog of every subcommand, its flags, and output schema) and ensure every
subcommand supports `--json` with a stable shape.

### P3 — Self-contained HTML architecture report

*Signal:* diagram-design. `archmap analyze --format html` emitting one file
with inlined Cytoscape + data — shareable, attachable to PRs, renderable by
agents' artifact viewers.

### P3 — PR bot via GitHub Agentic Workflows

*Signal:* `github/gh-aw`, `anthropics/claude-code-action`. The roadmap's
"CI/CD PR bot" can be delivered as a gh-aw workflow / claude-code-action
recipe that calls the ArchMAP MCP server, instead of custom bot code.

## 4. Deliberately out of scope

- **Voice/video generation** (VoiceStudio, hyperframes, remotion) — no
  architectural angle.
- **LLM routers** (litellm, freellmapi) — `archmap advise` already accepts
  any OpenAI-compatible `--base-url`, which covers them.
- **Binary reverse engineering** (ghidra, morluto/rea) — different problem
  domain; ArchMAP analyzes source.
- **Rewriting the core in Rust** — no evidence that analysis speed limits
  adoption; the parse cache already makes repeat runs cheap.

## 5. Risks

- **Trend volatility.** Several repos gained most of their stars in weeks;
  build on the durable layer (MCP, `SKILL.md`, hooks) rather than on any
  single harness.
- **Hook cost.** The `SessionStart` hook runs a full analysis on first use in
  a large repo. It's fail-safe and time-bounded (60 s), but very large
  monorepos may prefer `archmap memory` in CI plus a cheap `cat`.
- **Security scope creep.** P1/P2 security items must stay deterministic and
  evidence-backed; ArchMAP's value is that its findings are reproducible.
