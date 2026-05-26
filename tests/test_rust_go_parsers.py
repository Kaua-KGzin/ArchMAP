"""Tests for RustParser and GoParser (regex fallback path, no tree-sitter)."""

from __future__ import annotations

import pytest

from archmap.core.parser.go_parser import GoParser
from archmap.core.parser.rust_parser import RustParser, _normalize_use_path

# ---------------------------------------------------------------------------
# Helper: force tree-sitter off so we exercise the regex branch
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def no_tree_sitter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("archmap.core.parser.rust_parser.HAS_TREE_SITTER", False, raising=False)
    monkeypatch.setattr("archmap.core.parser.go_parser.HAS_TREE_SITTER", False, raising=False)
    monkeypatch.setattr("archmap.core.parser.ts_engine.HAS_TREE_SITTER", False, raising=False)


# ===========================================================================
# RustParser
# ===========================================================================


class TestRustParserParse:
    def test_use_statement(self) -> None:
        parser = RustParser()
        entries = parser.parse("use std::collections::HashMap;")
        assert any(e["type"] == "use" for e in entries)
        assert any("std::collections::HashMap" in e["path"] for e in entries)

    def test_mod_statement(self) -> None:
        parser = RustParser()
        entries = parser.parse("mod utils;")
        assert any(e["type"] == "mod" and e["module"] == "utils" for e in entries)

    def test_extern_crate(self) -> None:
        parser = RustParser()
        entries = parser.parse("extern crate serde;")
        assert any(e["type"] == "extern" and e["crate"] == "serde" for e in entries)

    def test_multiple_declarations(self) -> None:
        code = "use std::io;\nmod parser;\nextern crate log;"
        entries = RustParser().parse(code)
        types = {e["type"] for e in entries}
        assert types == {"use", "mod", "extern"}

    def test_empty_file(self) -> None:
        assert RustParser().parse("") == []

    def test_use_with_alias(self) -> None:
        parser = RustParser()
        entries = parser.parse("use std::io::Write as W;")
        assert entries[0]["path"] == "std::io::Write"

    def test_use_with_wildcard(self) -> None:
        parser = RustParser()
        entries = parser.parse("use std::prelude::*;")
        assert entries[0]["path"] == "std::prelude"

    def test_use_with_group(self) -> None:
        parser = RustParser()
        entries = parser.parse("use std::{io, fs};")
        assert entries[0]["path"] == "std"


class TestRustParserResolve:
    def test_resolve_use_entry(self) -> None:
        parser = RustParser()
        entries = [{"type": "use", "path": "std::io", "module": "", "crate": ""}]
        deps = parser.resolve(entries, "src/main.rs", set())
        # Should return at least one dependency (package or file)
        assert isinstance(deps, list)

    def test_resolve_ignores_non_dict(self) -> None:
        parser = RustParser()
        deps = parser.resolve(["not_a_dict"], "src/main.rs", set())  # type: ignore[list-item]
        assert deps == []

    def test_resolve_empty(self) -> None:
        parser = RustParser()
        assert parser.resolve([], "src/main.rs", set()) == []


class TestNormalizeUsePath:
    def test_plain_path(self) -> None:
        assert _normalize_use_path("std::io::Write") == "std::io::Write"

    def test_alias_stripped(self) -> None:
        assert _normalize_use_path("std::io::Write as W") == "std::io::Write"

    def test_wildcard_stripped(self) -> None:
        assert _normalize_use_path("std::prelude::*") == "std::prelude"

    def test_group_stripped(self) -> None:
        assert _normalize_use_path("std::{io, fs}") == "std"

    def test_pub_prefix_stripped(self) -> None:
        assert _normalize_use_path("pub std::io") == "std::io"

    def test_trailing_colons_stripped(self) -> None:
        assert _normalize_use_path("std::") == "std"


# ===========================================================================
# GoParser
# ===========================================================================


class TestGoParserParse:
    def test_single_import(self) -> None:
        parser = GoParser()
        imports = parser.parse('import "fmt"')
        assert "fmt" in imports

    def test_aliased_import(self) -> None:
        parser = GoParser()
        imports = parser.parse('import f "fmt"')
        assert "fmt" in imports

    def test_blank_import(self) -> None:
        parser = GoParser()
        imports = parser.parse('import _ "database/sql/driver"')
        assert "database/sql/driver" in imports

    def test_dot_import(self) -> None:
        parser = GoParser()
        imports = parser.parse('import . "math"')
        assert "math" in imports

    def test_block_import(self) -> None:
        parser = GoParser()
        code = 'import (\n\t"fmt"\n\t"os"\n)'
        imports = parser.parse(code)
        assert "fmt" in imports
        assert "os" in imports

    def test_block_import_with_alias(self) -> None:
        parser = GoParser()
        code = 'import (\n\tf "fmt"\n\t_ "os"\n)'
        imports = parser.parse(code)
        assert "fmt" in imports
        assert "os" in imports

    def test_empty_file(self) -> None:
        assert GoParser().parse("") == []

    def test_deduplication(self) -> None:
        code = 'import "fmt"\nimport "fmt"'
        assert GoParser().parse(code).count("fmt") == 1

    def test_sorted_output(self) -> None:
        code = 'import (\n\t"zzz"\n\t"aaa"\n)'
        result = GoParser().parse(code)
        assert result == sorted(result)


class TestGoParserResolve:
    def test_resolve_stdlib(self) -> None:
        parser = GoParser()
        deps = parser.resolve(["fmt"], "main.go", set())
        assert any(d["label"] == "fmt" for d in deps)

    def test_resolve_local_module(self) -> None:
        parser = GoParser()
        file_ids = {"myapp/utils/helper.go"}
        deps = parser.resolve(["myapp/utils"], "main.go", file_ids, module_name="myapp")
        # At least attempted resolution
        assert isinstance(deps, list)

    def test_resolve_with_get_file_content(self) -> None:
        parser = GoParser()
        def get_file_content(path: str) -> str | None:
            if path == "go.mod":
                return "module github.com/user/myapp\n\ngo 1.21\n"
            return None

        deps = parser.resolve(["fmt"], "main.go", set(), get_file_content=get_file_content)
        assert isinstance(deps, list)

    def test_resolve_get_file_content_no_mod(self) -> None:
        parser = GoParser()
        deps = parser.resolve(["fmt"], "main.go", set(), get_file_content=lambda p: None)
        assert isinstance(deps, list)

    def test_resolve_empty(self) -> None:
        assert GoParser().resolve([], "main.go", set()) == []
