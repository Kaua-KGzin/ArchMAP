from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

_DEFAULT_MODELS: dict[str, str] = {
    "claude": "claude-opus-4-7",
    "openai": "gpt-4o",
    "ollama": "llama3",
    "custom": "gpt-4o",
}

_DEFAULT_BASE_URLS: dict[str, str] = {
    "claude": "https://api.anthropic.com",
    "openai": "https://api.openai.com",
    "ollama": "http://localhost:11434",
}

_ENV_API_KEY_NAMES: dict[str, str | None] = {
    "claude": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "ollama": None,
    "custom": "ARCHMAP_LLM_API_KEY",
}

_HTTP_TIMEOUT = 90


def advise_architecture(
    report: dict[str, Any],
    *,
    provider: str = "claude",
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: int = _HTTP_TIMEOUT,
) -> dict:
    """Send a compact report summary to an LLM and return architectural advice.

    Supports claude, openai, ollama (OpenAI-compatible), or any custom
    OpenAI-compatible endpoint via base_url.
    """
    provider = provider.lower().strip()
    resolved_model = model or _DEFAULT_MODELS.get(provider, "gpt-4o")
    resolved_base_url = (base_url or _DEFAULT_BASE_URLS.get(provider, "")).rstrip("/")

    if provider == "claude":
        return _call_claude(
            report,
            model=resolved_model,
            api_key=api_key,
            base_url=resolved_base_url,
            timeout=timeout,
        )

    return _call_openai_compat(
        report,
        provider=provider,
        model=resolved_model,
        api_key=api_key,
        base_url=resolved_base_url,
        timeout=timeout,
    )


def _build_prompt(report: dict) -> str:
    metrics = report.get("metrics", {})
    architecture = report.get("architecture", {})
    risks = report.get("risks", {})
    cycles = report.get("cycles", [])

    health = architecture.get("health", {})
    style = architecture.get("detectedStyle", {})

    summary = {
        "files": int(metrics.get("filesAnalyzed", 0)),
        "dependencies": int(metrics.get("totalDependencies", 0)),
        "cycles": int(metrics.get("circularDependencyCount", 0)),
        "health_score": int(health.get("score", 100)),
        "health_grade": health.get("grade", "?"),
        "detected_style": style.get("name", "unknown"),
        "style_confidence_pct": round(float(style.get("confidence", 0.0)) * 100),
        "god_modules": [g.get("file") for g in risks.get("god_modules", [])[:5]],
        "dependency_explosions": [
            d.get("file") for d in risks.get("dependency_explosions", [])[:5]
        ],
        "layer_violations": [
            f"{v.get('sourceLayer')} -> {v.get('targetLayer')}: {v.get('source')}"
            for v in risks.get("layer_violations", [])[:5]
        ],
        "rule_violations": [
            f"{v.get('from')} -> {v.get('to')}"
            for v in architecture.get("ruleViolations", [])[:5]
        ],
        "circular_cycles": [
            " -> ".join(c) if isinstance(c, list) else str(c)
            for c in cycles[:5]
        ],
        "top_risk_files": [
            {
                "file": r.get("file"),
                "score": r.get("riskScore"),
                "signals": r.get("signals", []),
            }
            for r in risks.get("top_risk_files", [])[:5]
        ],
    }

    return (
        "You are an expert software architect reviewing a codebase analysis from ArchMAP.\n\n"
        f"Analysis summary:\n{json.dumps(summary, indent=2)}\n\n"
        "Provide concrete architectural advice covering:\n"
        "1. The single most critical issue to fix first and why\n"
        "2. Step-by-step refactoring instructions for that issue\n"
        "3. Two or three additional quick wins\n\n"
        "Be specific about file names and patterns when available. Keep it under 400 words."
    )


def _call_claude(
    report: dict,
    *,
    model: str,
    api_key: str | None,
    base_url: str,
    timeout: int,
) -> dict:
    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError(
            "No API key for Claude. Set ANTHROPIC_API_KEY or pass --api-key."
        )

    prompt = _build_prompt(report)
    payload = {
        "model": model,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
    }

    data = _http_post(f"{base_url}/v1/messages", headers, payload, timeout)
    content_blocks = data.get("content", [])
    text = "".join(
        block.get("text", "")
        for block in content_blocks
        if block.get("type") == "text"
    )

    return {
        "provider": "claude",
        "model": model,
        "advice": text.strip(),
        "usage": data.get("usage", {}),
    }


def _call_openai_compat(
    report: dict,
    *,
    provider: str,
    model: str,
    api_key: str | None,
    base_url: str,
    timeout: int,
) -> dict:
    env_key_name = _ENV_API_KEY_NAMES.get(provider)
    key = api_key or (os.environ.get(env_key_name, "") if env_key_name else "")

    prompt = _build_prompt(report)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
    }
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    # custom provider: base_url already contains the full path prefix (e.g.
    # Gemini uses .../v1beta/openai, LM Studio uses .../v1), so only append
    # /chat/completions. Other providers follow the standard /v1/chat/completions.
    if provider == "custom":
        chat_url = f"{base_url}/chat/completions"
    else:
        chat_url = f"{base_url}/v1/chat/completions"
    data = _http_post(chat_url, headers, payload, timeout)
    choices = data.get("choices", [])
    text = choices[0].get("message", {}).get("content", "") if choices else ""

    return {
        "provider": provider,
        "model": model,
        "advice": text.strip(),
        "usage": data.get("usage", {}),
    }


def _http_post(url: str, headers: dict, payload: dict, timeout: int) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM API error {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM API connection failed: {exc.reason}") from exc
