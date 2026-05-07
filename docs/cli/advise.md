# archmap advise

Analyzes a project and sends a compact summary to an LLM to get concrete architectural advice.

Supports Claude, OpenAI, Ollama (local), and any OpenAI-compatible endpoint.
Uses only Python's standard library (`urllib`) — no new runtime dependencies.

## Usage

```bash
archmap advise [path] [options]
```

## Arguments

| Argument | Description |
|---|---|
| `path` | Project root to analyze (default: `.`) |

## Options

| Option | Default | Description |
|---|---|---|
| `--provider` | `claude` | LLM provider: `claude`, `openai`, `ollama`, `custom` |
| `--model` | provider default | Model name (e.g. `claude-opus-4-7`, `gpt-4o`, `llama3`) |
| `--api-key KEY` | env var | API key — overrides `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` |
| `--base-url URL` | provider default | Custom base URL for OpenAI-compatible endpoints |
| `--timeout SECS` | `90` | HTTP timeout in seconds |
| `--json` | off | Output result as JSON |
| `--parallel` | on | Enable parallel file parsing |

## Provider defaults

| Provider | Default model | API key env var | Default base URL |
|---|---|---|---|
| `claude` | `claude-opus-4-7` | `ANTHROPIC_API_KEY` | `https://api.anthropic.com` |
| `openai` | `gpt-4o` | `OPENAI_API_KEY` | `https://api.openai.com` |
| `ollama` | `llama3` | _(none)_ | `http://localhost:11434` |
| `custom` | `gpt-4o` | `ARCHMAP_LLM_API_KEY` | _(required via `--base-url`)_ |

## Examples

```bash
# Claude (set ANTHROPIC_API_KEY in env)
archmap advise .

# OpenAI
archmap advise . --provider openai

# Local Ollama
archmap advise . --provider ollama

# Local Ollama with a specific model
archmap advise . --provider ollama --model mistral

# LM Studio or any OpenAI-compatible local server
archmap advise . --provider custom --base-url http://localhost:1234

# Specific Claude model
archmap advise . --model claude-sonnet-4-6

# JSON output
archmap advise . --json
```

## What the advisor sends

A compact JSON summary of the analysis including: health score, cycle count, god modules, layer violations, custom rule violations, and top risk files. The LLM is prompted to return:

1. The single most critical issue and why it matters.
2. Step-by-step refactoring instructions.
3. Two or three additional quick wins.

## Web UI

The AI Advisor panel is also available in the interactive web UI (`archmap serve`).
Open it from the nav rail — it shows top issue cards and ready-to-copy CLI commands per provider.
