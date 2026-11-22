"""C/C++ `#include "..."` resolution: -I style suffix matching, and its cost."""

from __future__ import annotations

import time

from archmap.core.parser.resolvers import _resolve_cpp_dependency


def _ids(deps):
    return [(d["type"], d["id"]) for d in deps]


def _local(value):
    return {"type": "local", "value": value}


def test_include_resolves_by_unique_path_suffix():
    files = {"src/main.cpp", "include/foo/bar.h", "src/util.h"}
    deps = _resolve_cpp_dependency(_local("foo/bar.h"), "src/main.cpp", files)
    assert _ids(deps) == [("file", "include/foo/bar.h")]


def test_ambiguous_suffix_stays_unresolved():
    files = {"src/main.cpp", "a/foo/bar.h", "b/foo/bar.h"}
    deps = _resolve_cpp_dependency(_local("foo/bar.h"), "src/main.cpp", files)
    assert _ids(deps) == [("package", "pkg:foo/bar.h")]


def test_suffix_match_respects_path_boundaries():
    # "bar.h" must not match "foobar.h".
    files = {"src/main.cpp", "lib/foobar.h"}
    deps = _resolve_cpp_dependency(_local("bar.h"), "src/main.cpp", files)
    assert _ids(deps) == [("package", "pkg:bar.h")]


def test_index_follows_a_different_file_set():
    first = {"src/main.cpp", "x/foo.h"}
    second = {"src/main.cpp", "y/foo.h"}
    assert _ids(_resolve_cpp_dependency(_local("foo.h"), "src/main.cpp", first)) == [
        ("file", "x/foo.h")
    ]
    assert _ids(_resolve_cpp_dependency(_local("foo.h"), "src/main.cpp", second)) == [
        ("file", "y/foo.h")
    ]


def test_suffix_lookup_does_not_scan_every_file_per_include():
    # A 4k-file C/C++ tree took ~100 s to analyse because every unresolved
    # include scanned the whole file set. 20k files x 3k includes was about
    # 60M endswith calls with the scan; an index makes it milliseconds.
    files = {f"lib{i // 100}/mod{i}.h" for i in range(20_000)} | {"src/main.cpp"}
    started = time.perf_counter()
    for i in range(3_000):
        _resolve_cpp_dependency(_local(f"missing/h{i}.h"), "src/main.cpp", files)
    assert time.perf_counter() - started < 2.0
