"""Parsing hot spots: memoised file ids and one resolve call per import."""
from __future__ import annotations

from collections import Counter
from typing import Any

import pytest

from archmap.core.analyzer.quality import empty_diagnostics
from archmap.core.parser import (
    _THREADED_READ_MIN_FILES,
    _load_source_map,
    parse_project,
    registry,
)
from archmap.core.parser.python_parser import PythonParser
from archmap.core.perf.synthetic import generate_project, generate_sources
from archmap.utils.file_utils import normalize_file_id, to_file_id


def test_normalize_file_id_is_memoised(tmp_path):
    generate_project(tmp_path, 200, shape="layered")
    normalize_file_id.cache_clear()
    parse_project(tmp_path, parallel=False)
    assert normalize_file_id.cache_info().hits > 0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("./a/b.py", "a/b.py"),
        ("a\\b\\c.py", "a/b/c.py"),
        ("a//b/./c.py", "a/b/c.py"),
        ("", "."),
        (".", "."),
        ("/abs/x.py", "/abs/x.py"),
    ],
)
def test_normalize_file_id_behaviour_unchanged(raw, expected):
    assert normalize_file_id(raw) == expected


def test_python_resolve_called_once_per_import_entry(tmp_path, monkeypatch):
    generate_project(tmp_path, 200, shape="layered")
    calls: list[tuple[str, int]] = []
    original = PythonParser.resolve

    def spy(self: Any, import_entries: list[Any], file_id: str, *args: Any, **kwargs: Any):
        calls.append((file_id, len(import_entries)))
        return original(self, import_entries, file_id, *args, **kwargs)

    monkeypatch.setattr(PythonParser, "resolve", spy)
    project = parse_project(tmp_path, parallel=False)

    source_ids = {f["id"] for f in project["parsedFiles"]}
    per_file = Counter(fid for fid, _ in calls if fid in source_ids)
    assert all(n == 1 for fid, n in calls if fid in source_ids)
    for parsed in project["parsedFiles"]:
        assert per_file[parsed["id"]] == parsed["importsTotal"]


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_dependencies_match_whole_list_resolution(tmp_path, language):
    generate_project(tmp_path, 120, language=language, shape="hub", seed=2)
    sources = generate_sources(120, language=language, shape="hub", seed=2)
    project = parse_project(tmp_path, parallel=False)
    file_ids = set(sources)
    parser = registry.get_parser(language)
    assert parser is not None
    for parsed in project["parsedFiles"]:
        expected = parser.resolve(parser.parse(sources[parsed["id"]]), parsed["id"], file_ids)
        assert parsed["dependencies"] == expected


def test_go_dependencies_stay_deduplicated_in_first_seen_order(tmp_path):
    (tmp_path / "go.mod").write_text("module example.com/app\n", encoding="utf-8")
    (tmp_path / "util").mkdir()
    (tmp_path / "util" / "a.go").write_text("package util\n", encoding="utf-8")
    (tmp_path / "util" / "b.go").write_text("package util\n", encoding="utf-8")
    (tmp_path / "main.go").write_text(
        'package main\n\nimport (\n\t"fmt"\n\t"example.com/app/util"\n\t"os"\n)\n',
        encoding="utf-8",
    )
    project = parse_project(tmp_path, parallel=False)
    main = next(f for f in project["parsedFiles"] if f["id"] == "main.go")
    parser = registry.get_parser("go")
    assert parser is not None
    file_ids = {f["id"] for f in project["parsedFiles"]}
    whole = parser.resolve(
        parser.parse((tmp_path / "main.go").read_text(encoding="utf-8")),
        "main.go",
        file_ids,
        get_file_content=lambda p: (tmp_path / p).read_text(encoding="utf-8")
        if (tmp_path / p).is_file()
        else None,
    )
    assert main["dependencies"] == whole
    ids = [d["id"] for d in main["dependencies"]]
    assert len(ids) == len(set(ids))


def test_to_file_id_for_a_single_file_root(tmp_path):
    target = tmp_path / "solo.py"
    target.write_text("x = 1\n", encoding="utf-8")
    assert to_file_id(target, target) == "solo.py"
    assert to_file_id(tmp_path, target) == "solo.py"


def test_to_file_id_matches_relative_to(tmp_path):
    nested = tmp_path / "pkg" / "sub" / "mod.py"
    assert to_file_id(tmp_path, nested) == nested.relative_to(tmp_path).as_posix()
    # A root spelled differently from the path still goes through pathlib.
    assert to_file_id(tmp_path / "pkg" / "..", tmp_path / "pkg" / ".." / "x.py") == "x.py"


def test_load_source_map_threaded_keeps_order_and_diagnostics(tmp_path):
    count = _THREADED_READ_MIN_FILES + 6
    for i in range(count):
        (tmp_path / f"m{i:03d}.py").write_bytes(f"x = {i}\r\n".encode())
    (tmp_path / "big.py").write_text("y = 1\n" * 100, encoding="utf-8")
    (tmp_path / "bad.py").write_bytes(b"\xff\xfe\x00bad")
    diag = empty_diagnostics()
    config = {"analysis": {"max_file_size_bytes": 200, "respect_gitignore": False}}
    source_map = _load_source_map(tmp_path, None, config=config, diagnostics=diag)

    assert list(source_map) == sorted(f"m{i:03d}.py" for i in range(count))
    assert source_map["m000.py"] == "x = 0\n"  # newlines translated as before
    assert diag["oversized"] == ["big.py"]
    assert diag["decodeErrors"] == ["bad.py"]
    assert diag["discovered"] == count + 2
