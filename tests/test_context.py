"""Tests for task-scoped context retrieval (archmap.core.context.relevance)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from archmap import analyze_project
from archmap.cli.main import main
from archmap.core.context.relevance import rank_relevant_files, tokenize


def test_tokenize_splits_identifiers_and_stems() -> None:
    tokens = tokenize("parseHTTPResponse retries user_accounts the")
    assert "parsehttpresponse" in tokens
    assert {"parse", "http", "response", "retry", "user", "account"} <= set(tokens)
    assert "the" not in tokens


@pytest.fixture()
def report(tmp_path: Path) -> dict:
    (tmp_path / "auth").mkdir()
    (tmp_path / "auth" / "__init__.py").write_text("")
    (tmp_path / "auth" / "tokens.py").write_text(
        "from auth import crypto\n\ndef refresh_token(session):\n    return crypto.sign(session)\n"
    )
    (tmp_path / "auth" / "crypto.py").write_text("def sign(value):\n    return value\n")
    (tmp_path / "billing.py").write_text("def invoice_total(items):\n    return sum(items)\n")
    return dict(analyze_project(tmp_path, use_cache=False))


def test_rank_prefers_matches_and_adds_neighbors(report: dict) -> None:
    result = rank_relevant_files(report, "refresh token expiry")
    files = {item["file"]: item for item in result["files"]}
    assert result["files"][0]["file"] == "auth/tokens.py"
    assert files["auth/tokens.py"]["role"] == "match"
    assert files["auth/crypto.py"]["role"] == "neighbor"
    assert "imported by auth/tokens.py" in files["auth/crypto.py"]["reasons"]
    assert "billing.py" not in files
    assert files["auth/tokens.py"]["snippets"][0] == {
        "line": 3,
        "text": "def refresh_token(session):",
    }


def test_budget_is_respected(report: dict) -> None:
    result = rank_relevant_files(report, "refresh token sign crypto", budget_tokens=1)
    # The best file is always returned even when it alone exceeds the budget.
    assert len(result["files"]) == 1


def test_empty_query(report: dict) -> None:
    result = rank_relevant_files(report, "the and of")
    assert result["files"] == []
    assert "no searchable terms" in result["note"]


def test_context_cli(report: dict, capsys: pytest.CaptureFixture[str]) -> None:
    root = report["projectRoot"]
    assert main(["context", "invoice total", root, "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["files"][0]["file"] == "billing.py"
    assert main(["context", "invoice total", root]) == 0
    assert "billing.py" in capsys.readouterr().out
