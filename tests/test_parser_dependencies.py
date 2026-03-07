"""Tests for Python dependency resolution, including absolute from-imports."""
from __future__ import annotations

from archmap.core.parser import parse_project


def _virtual(files: dict[str, str]):
    return parse_project(".", virtual_files=files)


def test_from_pkg_import_submodule_resolves_to_submodule_file() -> None:
    """from pkg import utils should produce an edge to pkg/utils.py, not pkg/__init__.py."""
    virtual = {
        "main.py": "from pkg import utils\n",
        "pkg/__init__.py": "",
        "pkg/utils.py": "",
    }
    result = _virtual(virtual)
    main_file = next(f for f in result["parsedFiles"] if f["id"] == "main.py")
    dep_ids = {d["id"] for d in main_file["dependencies"]}
    assert "pkg/utils.py" in dep_ids, f"Expected pkg/utils.py in deps, got {dep_ids}"
    assert "pkg/__init__.py" not in dep_ids, "Should not depend on __init__.py when submodule exists"


def test_from_pkg_import_multiple_submodules() -> None:
    """from pkg import utils, models should resolve both submodule files."""
    virtual = {
        "main.py": "from pkg import utils, models\n",
        "pkg/__init__.py": "",
        "pkg/utils.py": "",
        "pkg/models.py": "",
    }
    result = _virtual(virtual)
    main_file = next(f for f in result["parsedFiles"] if f["id"] == "main.py")
    dep_ids = {d["id"] for d in main_file["dependencies"]}
    assert "pkg/utils.py" in dep_ids
    assert "pkg/models.py" in dep_ids


def test_from_pkg_import_symbol_falls_back_to_init() -> None:
    """from pkg import MyClass (not a submodule) should fall back to pkg/__init__.py."""
    virtual = {
        "main.py": "from pkg import MyClass\n",
        "pkg/__init__.py": "class MyClass: pass\n",
    }
    result = _virtual(virtual)
    main_file = next(f for f in result["parsedFiles"] if f["id"] == "main.py")
    dep_ids = {d["id"] for d in main_file["dependencies"]}
    assert "pkg/__init__.py" in dep_ids


def test_from_external_pkg_import_produces_package_dependency() -> None:
    """from os import path should produce a package dependency, not a file dep."""
    virtual = {
        "main.py": "from os import path\n",
    }
    result = _virtual(virtual)
    main_file = next(f for f in result["parsedFiles"] if f["id"] == "main.py")
    dep_types = {d["type"] for d in main_file["dependencies"]}
    assert "package" in dep_types
    assert "file" not in dep_types
