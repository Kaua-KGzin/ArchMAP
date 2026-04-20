from __future__ import annotations

from pathlib import Path

from archmap.cache import (
    _cache_path,
    compute_fingerprint,
    invalidate_cache,
    load_cached_report,
    save_cached_report,
)


def _write_py(path: Path, content: str = "pass") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _dummy_config(ignore_dirs: list | None = None) -> dict:
    return {
        "analysis": {
            "ignore_dirs": ignore_dirs or [],
            "max_file_size_bytes": 1048576,
            "parallel": True,
        },
        "architecture": {"rules": {"forbid": [], "allow": []}},
        "risks": {"layer_order": {}},
    }


def test_compute_fingerprint_is_stable(tmp_path):
    _write_py(tmp_path / "src" / "main.py")
    config = _dummy_config()
    fp1 = compute_fingerprint(tmp_path, config)
    fp2 = compute_fingerprint(tmp_path, config)
    assert fp1 == fp2


def test_compute_fingerprint_changes_on_file_modification(tmp_path):
    f = tmp_path / "src" / "main.py"
    _write_py(f, "x = 1")
    config = _dummy_config()
    fp1 = compute_fingerprint(tmp_path, config)

    import time
    time.sleep(0.01)
    f.touch()  # update mtime
    fp2 = compute_fingerprint(tmp_path, config)
    assert fp1 != fp2


def test_compute_fingerprint_changes_on_config_change(tmp_path):
    _write_py(tmp_path / "a.py")
    fp1 = compute_fingerprint(tmp_path, _dummy_config([]))
    fp2 = compute_fingerprint(tmp_path, _dummy_config(["vendor"]))
    assert fp1 != fp2


def test_compute_fingerprint_changes_on_new_file(tmp_path):
    _write_py(tmp_path / "a.py")
    config = _dummy_config()
    fp1 = compute_fingerprint(tmp_path, config)

    _write_py(tmp_path / "b.py")
    fp2 = compute_fingerprint(tmp_path, config)
    assert fp1 != fp2


def test_cache_roundtrip(tmp_path):
    report = {"projectRoot": str(tmp_path), "nodes": [], "cycles": []}
    fingerprint = "abc123"
    save_cached_report(tmp_path, fingerprint, report)
    loaded = load_cached_report(tmp_path, fingerprint)
    assert loaded == report


def test_cache_miss_on_wrong_fingerprint(tmp_path):
    report = {"projectRoot": str(tmp_path)}
    save_cached_report(tmp_path, "fp1", report)
    assert load_cached_report(tmp_path, "fp2") is None


def test_cache_miss_when_no_file(tmp_path):
    assert load_cached_report(tmp_path, "any") is None


def test_cache_handles_corrupt_file(tmp_path):
    cache = _cache_path(tmp_path)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("not valid json", encoding="utf-8")
    assert load_cached_report(tmp_path, "any") is None


def test_invalidate_removes_cache(tmp_path):
    save_cached_report(tmp_path, "fp", {"x": 1})
    assert _cache_path(tmp_path).exists()
    invalidate_cache(tmp_path)
    assert not _cache_path(tmp_path).exists()


def test_invalidate_is_safe_when_no_cache(tmp_path):
    # Should not raise even if cache doesn't exist
    invalidate_cache(tmp_path)


def test_cache_file_inside_archmap_dir(tmp_path):
    save_cached_report(tmp_path, "fp", {"x": 1})
    cache = _cache_path(tmp_path)
    assert cache.parent.name == ".archmap"
    assert cache.name == "cache.json"


def test_save_does_not_raise_on_readonly_dir(tmp_path):
    # If directory is read-only, save should silently fail
    import stat
    cache_dir = tmp_path / ".archmap"
    cache_dir.mkdir()
    cache_dir.chmod(stat.S_IREAD | stat.S_IEXEC)
    try:
        # Should not raise
        save_cached_report(tmp_path, "fp", {"x": 1})
    finally:
        cache_dir.chmod(stat.S_IRWXU)


def test_cache_atomic_write_uses_temp_file(tmp_path, monkeypatch):
    """Verify that tmp file is used (indirectly: test that file ends up valid)."""
    report = {"projectRoot": str(tmp_path), "data": list(range(100))}
    save_cached_report(tmp_path, "fp", report)
    loaded = load_cached_report(tmp_path, "fp")
    assert loaded["data"] == list(range(100))
