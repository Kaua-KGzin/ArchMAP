"""Robustness tests: comment false positives + per-language semantic resolution.

These exercise the regex fallbacks (tree-sitter not required) and the
configuration-aware resolvers added to raise every language parser's accuracy.
"""
from __future__ import annotations

from archmap.core.parser import parse_project
from archmap.core.parser._text import strip_comments
from archmap.core.parser.csharp_parser import CSharpParser
from archmap.core.parser.go_parser import _parse_go_replacements
from archmap.core.parser.java_parser import JavaParser
from archmap.core.parser.js_parser import JSParser
from archmap.core.parser.php_parser import PHPParser


def _deps(result: dict, file_id: str) -> set[str]:
    entry = next(f for f in result["parsedFiles"] if f["id"] == file_id)
    return {d["id"] for d in entry["dependencies"]}


# ---------------------------------------------------------------------------
# strip_comments utility
# ---------------------------------------------------------------------------


def test_strip_comments_preserves_strings_and_newlines() -> None:
    src = 'const url = "http://x"; // import fake from "evil"\nimport real from "ok";'
    cleaned = strip_comments(src, string_delims=('"', "'", "`"))
    assert '"http://x"' in cleaned  # string preserved, // inside not a comment
    assert "fake" not in cleaned  # comment content removed
    assert cleaned.count("\n") == src.count("\n")  # line structure preserved


def test_strip_comments_block() -> None:
    src = "a /* import x from 'y' */ b"
    assert "import" not in strip_comments(src)


# ---------------------------------------------------------------------------
# JS/JS false positives in comments
# ---------------------------------------------------------------------------


def test_js_ignores_imports_in_comments() -> None:
    src = (
        '// import ghost from "ghost-pkg";\n'
        '/* require("block-ghost") */\n'
        'import real from "real-pkg";\n'
    )
    imports = JSParser().parse(src)
    assert imports == ["real-pkg"]


# ---------------------------------------------------------------------------
# C# aliases, global using, comment handling
# ---------------------------------------------------------------------------


def test_csharp_alias_captures_rhs_and_skips_comments() -> None:
    src = (
        "using System;\n"
        "global using System.Linq;\n"
        "using Json = Newtonsoft.Json;\n"
        "// using Commented.Out;\n"
    )
    imports = CSharpParser().parse(src)
    assert "System" in imports
    assert "System.Linq" in imports
    assert "Newtonsoft.Json" in imports  # alias RHS, not the alias name
    assert "Json" not in imports
    assert not any("Commented" in i for i in imports)


# ---------------------------------------------------------------------------
# Java inner classes + comment handling
# ---------------------------------------------------------------------------


def test_java_inner_class_resolves_to_outer_file() -> None:
    files = {
        "src/main/java/app/Main.java": (
            "// import com.example.Ghost;\n"
            "import com.example.Outer.Inner;\n"
        ),
        "com/example/Outer.java": "package com.example; class Outer {}\n",
    }
    result = parse_project(".", virtual_files=files)
    deps = _deps(result, "src/main/java/app/Main.java")
    assert "com/example/Outer.java" in deps
    assert not any("Ghost" in d for d in deps)


def test_java_comment_import_is_ignored() -> None:
    imports = JavaParser().parse("// import com.x.Y;\nimport com.real.Z;\n")
    assert imports == ["com.real.Z"]


# ---------------------------------------------------------------------------
# Go replace directives
# ---------------------------------------------------------------------------


def test_parse_go_replacements_local_only() -> None:
    mod = (
        "module example.com/app\n"
        "replace example.com/old => ./internal/old\n"
        "replace example.com/remote v1.2.3 => github.com/fork/remote v1.2.4\n"
        "replace (\n"
        "  example.com/grouped v1 => ../grouped\n"
        ")\n"
    )
    rep = _parse_go_replacements(mod)
    assert rep == {
        "example.com/old": "./internal/old",
        "example.com/grouped": "../grouped",
    }


def test_go_replace_resolves_to_local_file() -> None:
    files = {
        "go.mod": "module example.com/app\nreplace example.com/lib => ./lib\n",
        "main.go": 'import "example.com/lib/util"\n',
        "lib/util/util.go": "package util\n",
    }
    result = parse_project(".", virtual_files=files)
    assert "lib/util/util.go" in _deps(result, "main.go")


# ---------------------------------------------------------------------------
# PHP composer PSR-4
# ---------------------------------------------------------------------------


def test_php_psr4_resolves_namespace_to_src() -> None:
    files = {
        "composer.json": '{"autoload": {"psr-4": {"App\\\\": "src/"}}}',
        "index.php": "<?php\nuse App\\Models\\User;\n",
        "src/Models/User.php": "<?php\nnamespace App\\Models;\nclass User {}\n",
    }
    result = parse_project(".", virtual_files=files)
    assert "src/Models/User.php" in _deps(result, "index.php")


def test_php_psr4_longest_prefix_wins() -> None:
    files = {
        "composer.json": (
            '{"autoload": {"psr-4": '
            '{"App\\\\": "src/", "App\\\\Admin\\\\": "admin/"}}}'
        ),
        "index.php": "<?php\nuse App\\Admin\\Dashboard;\n",
        "admin/Dashboard.php": "<?php\nnamespace App\\Admin;\nclass Dashboard {}\n",
    }
    result = parse_project(".", virtual_files=files)
    assert "admin/Dashboard.php" in _deps(result, "index.php")


def test_php_comment_use_is_ignored() -> None:
    imports = PHPParser().parse("<?php\n// use Ghost\\Thing;\nuse Real\\Thing;\n")
    values = {e["value"] for e in imports}
    assert "Real\\Thing" in values
    assert not any("Ghost" in v for v in values)


# ---------------------------------------------------------------------------
# C/C++ include-dir suffix resolution + comment handling
# ---------------------------------------------------------------------------


def test_cpp_include_dir_suffix_resolution() -> None:
    files = {
        "src/app.cpp": '#include "mylib/widget.h"\n',
        "include/mylib/widget.h": "// header\n",
    }
    result = parse_project(".", virtual_files=files)
    assert "include/mylib/widget.h" in _deps(result, "src/app.cpp")


def test_cpp_comment_include_is_ignored() -> None:
    files = {
        "a.c": '// #include "ghost.h"\n/* #include "block.h" */\n#include "real.h"\n',
        "real.h": "int x;\n",
    }
    result = parse_project(".", virtual_files=files)
    deps = _deps(result, "a.c")
    assert "real.h" in deps
    assert not any("ghost" in d or "block" in d for d in deps)
