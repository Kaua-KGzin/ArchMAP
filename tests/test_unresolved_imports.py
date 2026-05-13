from __future__ import annotations

from archmap.cli import reporting
from archmap.core.parser import parse_project


def _report_with_unresolved(items: list[dict], total: int = 10) -> dict:
    resolved = total - len(items)
    return {
        "metrics": {
            "filesAnalyzed": 5,
            "totalDependencies": 10,
            "circularDependencyCount": 0,
            "resolutionRate": resolved / total if total else 1.0,
            "unresolvedImports": items,
            "unresolvedImportsTotal": len(items),
            "complexity": [],
        },
        "risks": {},
        "architecture": {},
    }


def test_print_unresolved_imports_shows_items(capsys) -> None:
    report = _report_with_unresolved([
        {"file": "src/a.py", "import": "missing_lib"},
        {"file": "src/b.py", "import": "another_missing"},
    ])
    reporting.print_unresolved_imports(report, limit=20)
    out = capsys.readouterr().out
    assert "2 import(s) could not be resolved" in out
    assert "src/a.py" in out
    assert "missing_lib" in out
    assert "src/b.py" in out
    assert "another_missing" in out


def test_print_unresolved_imports_empty_produces_no_output(capsys) -> None:
    report = _report_with_unresolved([])
    reporting.print_unresolved_imports(report, limit=20)
    assert capsys.readouterr().out == ""


def test_print_unresolved_imports_respects_limit(capsys) -> None:
    items = [{"file": f"src/f{i}.py", "import": f"lib{i}"} for i in range(50)]
    report = _report_with_unresolved(items, total=60)
    reporting.print_unresolved_imports(report, limit=5)
    out = capsys.readouterr().out
    assert "50 import(s)" in out
    assert "lib0" in out
    assert "lib4" in out
    assert "lib5" not in out
    assert "more" in out


def test_parse_project_external_import_counts_as_resolved(tmp_path) -> None:
    # bare "import pkg" resolves to a pkg: node — it is considered resolved
    (tmp_path / "a.py").write_text("import totally_nonexistent_package\n", encoding="utf-8")
    parsed = parse_project(tmp_path, parallel=False)
    file_entry = parsed["parsedFiles"][0]
    assert file_entry["importsTotal"] == 1
    assert file_entry["importsResolved"] == 1
    assert file_entry["unresolvedImports"] == []


def test_parse_project_relative_import_to_missing_file_is_unresolved(tmp_path) -> None:
    # relative import to a non-existent sibling — parser returns no deps → unresolved
    (tmp_path / "a.py").write_text("from . import ghost_module\n", encoding="utf-8")
    parsed = parse_project(tmp_path, parallel=False)
    a_entry = parsed["parsedFiles"][0]
    assert a_entry["importsTotal"] == 1
    assert a_entry["importsResolved"] == 0
    assert len(a_entry["unresolvedImports"]) == 1


def test_parse_project_resolved_internal_import_not_in_unresolved(tmp_path) -> None:
    (tmp_path / "a.py").write_text("from b import foo\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def foo(): pass\n", encoding="utf-8")
    parsed = parse_project(tmp_path, parallel=False)
    a_entry = next(f for f in parsed["parsedFiles"] if f["id"] == "a.py")
    assert a_entry["importsTotal"] == 1
    assert a_entry["importsResolved"] == 1
    assert a_entry["unresolvedImports"] == []


def test_parse_project_mixed_imports_count_correctly(tmp_path) -> None:
    # internal dep resolves; relative import to nonexistent file does not
    (tmp_path / "a.py").write_text(
        "from b import foo\nfrom . import ghost_module\n",
        encoding="utf-8",
    )
    (tmp_path / "b.py").write_text("def foo(): pass\n", encoding="utf-8")
    parsed = parse_project(tmp_path, parallel=False)
    a_entry = next(f for f in parsed["parsedFiles"] if f["id"] == "a.py")
    assert a_entry["importsTotal"] == 2
    assert a_entry["importsResolved"] == 1
    assert len(a_entry["unresolvedImports"]) == 1
