from __future__ import annotations

import json
from pathlib import Path

from archmap.core.cache import _CACHE_FILENAME, _CACHE_VERSION, ParseCache


def _make_parsed(file_id: str = "src/foo.py") -> dict:
    return {
        "id": file_id,
        "label": file_id,
        "type": "file",
        "language": "python",
        "dependencies": [],
    }


# ---------------------------------------------------------------------------
# ParseCache.get / put
# ---------------------------------------------------------------------------

def test_get_returns_none_when_empty() -> None:
    cache = ParseCache()
    assert cache.get("src/foo.py", 1000.0) is None


def test_put_and_get_hit() -> None:
    cache = ParseCache()
    parsed = _make_parsed()
    cache.put("src/foo.py", 1000.0, parsed)
    assert cache.get("src/foo.py", 1000.0) == parsed


def test_get_miss_on_mtime_mismatch() -> None:
    cache = ParseCache()
    parsed = _make_parsed()
    cache.put("src/foo.py", 1000.0, parsed)
    assert cache.get("src/foo.py", 2000.0) is None


def test_put_overwrites_stale_entry() -> None:
    cache = ParseCache()
    old = _make_parsed()
    new = {**_make_parsed(), "language": "typescript"}
    cache.put("src/foo.py", 1000.0, old)
    cache.put("src/foo.py", 2000.0, new)
    assert cache.get("src/foo.py", 2000.0) == new
    assert cache.get("src/foo.py", 1000.0) is None


def test_size_reflects_unique_file_ids() -> None:
    cache = ParseCache()
    cache.put("a.py", 1.0, _make_parsed("a.py"))
    cache.put("b.py", 2.0, _make_parsed("b.py"))
    cache.put("a.py", 3.0, _make_parsed("a.py"))  # overwrite a.py
    assert cache.size() == 2


# ---------------------------------------------------------------------------
# Disk persistence — save / load
# ---------------------------------------------------------------------------

def test_save_creates_cache_file(tmp_path: Path) -> None:
    cache = ParseCache()
    cache.put("src/foo.py", 1234.5, _make_parsed())
    cache.save(tmp_path)
    cache_file = tmp_path / _CACHE_FILENAME
    assert cache_file.is_file()
    raw = json.loads(cache_file.read_text())
    assert raw["version"] == _CACHE_VERSION
    assert "src/foo.py" in raw["entries"]


def test_load_restores_entries(tmp_path: Path) -> None:
    parsed = _make_parsed()
    cache = ParseCache()
    cache.put("src/foo.py", 1234.5, parsed)
    cache.save(tmp_path)

    loaded = ParseCache.load(tmp_path)
    assert loaded.get("src/foo.py", 1234.5) == parsed


def test_load_returns_empty_when_no_file(tmp_path: Path) -> None:
    loaded = ParseCache.load(tmp_path)
    assert loaded.size() == 0


def test_load_ignores_wrong_version(tmp_path: Path) -> None:
    bad = {
        "version": 999,
        "entries": {
            "src/foo.py": {
                "mtime": 1.0, "id": "src/foo.py", "label": "src/foo.py",
                "type": "file", "language": "python", "dependencies": [],
            }
        },
    }
    (tmp_path / _CACHE_FILENAME).write_text(json.dumps(bad))
    loaded = ParseCache.load(tmp_path)
    assert loaded.size() == 0


def test_load_ignores_malformed_json(tmp_path: Path) -> None:
    (tmp_path / _CACHE_FILENAME).write_text("not json{{{")
    loaded = ParseCache.load(tmp_path)
    assert loaded.size() == 0


def test_load_skips_entries_without_mtime(tmp_path: Path) -> None:
    payload = {
        "version": _CACHE_VERSION,
        "entries": {
            "good.py": {
                "mtime": 1.0, "id": "good.py", "label": "good.py",
                "type": "file", "language": "python", "dependencies": [],
            },
            "bad.py": {
                "id": "bad.py", "label": "bad.py",
                "type": "file", "language": "python", "dependencies": [],
            },
        },
    }
    (tmp_path / _CACHE_FILENAME).write_text(json.dumps(payload))
    loaded = ParseCache.load(tmp_path)
    assert loaded.size() == 1
    assert loaded.get("good.py", 1.0) is not None


# ---------------------------------------------------------------------------
# Integration with parse_project
# ---------------------------------------------------------------------------

def test_parse_project_uses_cache_for_unchanged_files(tmp_path: Path) -> None:
    """Files whose mtime matches cache are not re-parsed (parse count stays low)."""
    from archmap.core.parser.project_parser import parse_project

    src = tmp_path / "main.py"
    src.write_text("x = 1\n")

    # First parse — populates cache
    result1 = parse_project(tmp_path)
    assert any(f["id"] == "main.py" for f in result1["parsedFiles"])

    cache_file = tmp_path / _CACHE_FILENAME
    assert cache_file.is_file()

    # Second parse — should hit cache (no mtime change)
    result2 = parse_project(tmp_path)
    ids1 = {f["id"] for f in result1["parsedFiles"]}
    ids2 = {f["id"] for f in result2["parsedFiles"]}
    assert ids1 == ids2


def test_parse_project_reparsed_on_mtime_change(tmp_path: Path) -> None:
    from archmap.core.parser.project_parser import parse_project

    src = tmp_path / "util.py"
    src.write_text("def foo(): pass\n")

    parse_project(tmp_path)

    # Simulate file change by writing new content and touching mtime
    src.write_text("def bar(): pass\n")
    import os
    current_mtime = os.path.getmtime(src)
    os.utime(src, (current_mtime + 5, current_mtime + 5))

    result = parse_project(tmp_path)
    assert any(f["id"] == "util.py" for f in result["parsedFiles"])


def test_parse_project_cache_disabled_via_config(tmp_path: Path) -> None:
    from archmap.config import default_project_config
    from archmap.core.parser.project_parser import parse_project

    cfg = default_project_config()
    cfg["analysis"]["cache"] = False

    src = tmp_path / "main.py"
    src.write_text("x = 1\n")

    parse_project(tmp_path, config=cfg)
    assert not (tmp_path / _CACHE_FILENAME).exists()
