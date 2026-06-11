"""Tree-sitter orchestration: per-language availability + automatic fallback.

The orchestration tests monkeypatch the engine internals so they run
deterministically whether or not the optional tree-sitter grammars are
installed. A second group of tests exercises the real grammars and is skipped
when they are absent.
"""
from __future__ import annotations

import pytest

from archmap.core.parser import ts_engine
from archmap.core.parser.csharp_parser import CSharpParser
from archmap.core.parser.js_parser import JSParser


class _FakeTree:
    def __init__(self, has_error: bool) -> None:
        self.root_node = type("Node", (), {"has_error": has_error})()


# ---------------------------------------------------------------------------
# Orchestration / fallback decision (deterministic, always run)
# ---------------------------------------------------------------------------


def test_try_extract_unknown_language_returns_none() -> None:
    assert ts_engine.try_extract("cobol", "stuff") is None


def test_try_extract_unavailable_grammar_returns_none(monkeypatch) -> None:
    monkeypatch.setitem(ts_engine._EXTRACTORS, "fake", ("fakegrammar", lambda t, n: []))
    monkeypatch.setattr(ts_engine, "_load_language", lambda name: None)
    assert ts_engine.try_extract("fake", "x") is None


def _wire_fake(monkeypatch, extractor, *, has_error: bool) -> None:
    monkeypatch.setitem(ts_engine._EXTRACTORS, "fake", ("fakegrammar", extractor))
    monkeypatch.setattr(ts_engine, "_load_language", lambda name: object())
    monkeypatch.setattr(ts_engine, "_parse", lambda lang, src: _FakeTree(has_error))


def test_try_extract_returns_none_when_extractor_raises(monkeypatch) -> None:
    def boom(_tree, _name):
        raise RuntimeError("grammar panic")

    _wire_fake(monkeypatch, boom, has_error=False)
    assert ts_extract_fake() is None


def test_try_extract_falls_back_when_errored_and_empty(monkeypatch) -> None:
    _wire_fake(monkeypatch, lambda t, n: [], has_error=True)
    assert ts_extract_fake() is None


def test_try_extract_trusts_clean_empty_parse(monkeypatch) -> None:
    _wire_fake(monkeypatch, lambda t, n: [], has_error=False)
    assert ts_extract_fake() == []


def test_try_extract_keeps_results_despite_minor_errors(monkeypatch) -> None:
    _wire_fake(monkeypatch, lambda t, n: ["mod"], has_error=True)
    assert ts_extract_fake() == ["mod"]


def ts_extract_fake():
    return ts_engine.try_extract("fake", "source")


# ---------------------------------------------------------------------------
# Parser-level automatic fallback to regex
# ---------------------------------------------------------------------------


def test_jsparser_uses_regex_when_tree_sitter_declines(monkeypatch) -> None:
    # Simulate tree-sitter being unavailable/unreliable for this file.
    monkeypatch.setattr(ts_engine, "try_extract", lambda lang, src: None)
    imports = JSParser().parse('// import ghost from "g";\nimport real from "real-pkg";\n')
    assert imports == ["real-pkg"]


def test_csharp_uses_regex_when_tree_sitter_declines(monkeypatch) -> None:
    monkeypatch.setattr(ts_engine, "try_extract", lambda lang, src: None)
    imports = CSharpParser().parse("using Json = Newtonsoft.Json;\nusing System;\n")
    assert "Newtonsoft.Json" in imports
    assert "System" in imports
    assert "Json" not in imports


# ---------------------------------------------------------------------------
# Real grammars (skipped when not installed)
# ---------------------------------------------------------------------------

requires_ts = pytest.mark.skipif(
    not ts_engine.HAS_TREE_SITTER, reason="tree-sitter grammars not installed"
)


@requires_ts
def test_language_available_reports_per_language() -> None:
    # At least one grammar must be available if HAS_TREE_SITTER is True.
    assert any(ts_engine.language_available(name) for name in ts_engine._GRAMMAR_LOADERS)


@requires_ts
def test_csharp_structured_alias_via_tree_sitter() -> None:
    src = (
        "using System;\n"
        "global using System.Linq;\n"
        "using Json = Newtonsoft.Json;\n"
        "using static System.Math;\n"
    )
    imports = ts_engine.extract_csharp_imports(src)
    assert imports == ["Newtonsoft.Json", "System", "System.Linq", "System.Math"]


@requires_ts
def test_try_extract_real_fallback_on_garbage() -> None:
    # Heavily broken C# that tree-sitter cannot parse into using-directives:
    # try_extract should decline (None) so the caller uses regex.
    result = ts_engine.try_extract("csharp", "@@@ not valid using at all %%%")
    assert result is None or result == []
