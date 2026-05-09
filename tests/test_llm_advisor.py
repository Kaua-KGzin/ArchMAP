from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from archmap.core.advisor.llm_advisor import advise_architecture


def _mock_openai_response(text: str = "Great advice.") -> MagicMock:
    data = {
        "choices": [{"message": {"content": text}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    mock = MagicMock()
    mock.read.return_value = json.dumps(data).encode()
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


def _capture_url() -> list[str]:
    urls: list[str] = []

    def fake_urlopen(req, timeout=None):
        urls.append(req.full_url)
        return _mock_openai_response()

    return urls, fake_urlopen


# ── URL construction per provider ────────────────────────────────────────────

def test_ollama_uses_v1_chat_completions():
    urls, fake = _capture_url()
    with patch("urllib.request.urlopen", side_effect=fake):
        advise_architecture({}, provider="ollama", base_url="http://localhost:11434")
    assert urls[0] == "http://localhost:11434/v1/chat/completions"


def test_openai_uses_v1_chat_completions():
    urls, fake = _capture_url()
    with patch("urllib.request.urlopen", side_effect=fake):
        advise_architecture(
            {}, provider="openai", api_key="sk-test", base_url="https://api.openai.com"
        )
    assert urls[0] == "https://api.openai.com/v1/chat/completions"


def test_custom_does_not_add_v1():
    """Custom provider appends /chat/completions only — supports Gemini, LM Studio, etc."""
    urls, fake = _capture_url()
    with patch("urllib.request.urlopen", side_effect=fake):
        advise_architecture(
            {},
            provider="custom",
            api_key="key",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        )
    assert urls[0] == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"


def test_custom_lm_studio_url():
    urls, fake = _capture_url()
    with patch("urllib.request.urlopen", side_effect=fake):
        advise_architecture({}, provider="custom", base_url="http://localhost:1234/v1")
    assert urls[0] == "http://localhost:1234/v1/chat/completions"


# ── Response parsing ──────────────────────────────────────────────────────────

def test_ollama_returns_advice_text():
    with patch("urllib.request.urlopen", return_value=_mock_openai_response("Fix your cycles.")):
        result = advise_architecture({}, provider="ollama", base_url="http://localhost:11434")
    assert result["advice"] == "Fix your cycles."
    assert result["provider"] == "ollama"


def test_custom_gemini_returns_advice():
    with patch("urllib.request.urlopen", return_value=_mock_openai_response("Split the god module.")):
        result = advise_architecture(
            {},
            provider="custom",
            model="gemini-1.5-flash",
            api_key="AIza-test",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        )
    assert result["advice"] == "Split the god module."
    assert result["model"] == "gemini-1.5-flash"


def test_missing_api_key_for_claude_raises():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            advise_architecture({}, provider="claude")
