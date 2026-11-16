<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
|------|----------|
| `detect_changes` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context` | Need source snippets for review — token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.

## Pull request rule: AI authorship and human supervision (mandatory)

Every pull request opened or updated by an AI agent (Claude Code or any other)
must fill the **AI assistance & supervision** section of
`.github/PULL_REQUEST_TEMPLATE.md`, in detail. This is a project rule, not a
suggestion:

- **Agent**: tool and model as reported by the session, plus the session /
  replay link (e.g. `https://claude.ai/code/session_...`) so the work can be
  audited step by step.
- **Supervisor**: the human who directed and reviewed the work, by GitHub
  handle (e.g. `@Kaua-KGzin`). Never publish personal e-mail addresses.
- **Timeline (UTC)**: session start, each commit (hash + time), PR creation and
  every later update, taken from `git log --date=iso` / the GitHub API — never
  estimated.
- **What the human decided** vs. **what the agent did on its own**: the
  instructions given, decisions taken, and anything the agent chose that the
  supervisor should double-check.
- **Validation actually run** (commands and results) and **known limitations /
  open risks**.

When a PR receives more commits, update the section (new commits, times,
validation) instead of leaving the original description stale.
