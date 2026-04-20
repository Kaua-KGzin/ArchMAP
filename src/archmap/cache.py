from __future__ import annotations

import hashlib
import json
from pathlib import Path

_CACHE_DIR = ".archmap"
_CACHE_FILE = "cache.json"
# Hard cap: refuse to write cache files larger than 50 MB to prevent disk exhaustion.
_MAX_CACHE_BYTES = 50 * 1024 * 1024


def compute_fingerprint(project_root: Path, config: dict) -> str:
    """Compute a stable fingerprint for cache invalidation.

    The fingerprint encodes the project config and the mtime+size of every
    source file so that any change — including config edits or file additions
    and deletions — causes a cache miss.
    """
    from archmap.utils.file_utils import discover_source_files

    config_blob = json.dumps(config, sort_keys=True, default=str)

    source_files = sorted(discover_source_files(project_root))
    file_meta_parts: list[str] = []
    for f in source_files:
        try:
            stat = f.stat()
            rel = f.relative_to(project_root).as_posix()
            file_meta_parts.append(f"{rel}:{stat.st_mtime_ns}:{stat.st_size}")
        except OSError:
            continue

    combined = config_blob + "\n" + "\n".join(file_meta_parts)
    return hashlib.sha256(combined.encode("utf-8", errors="replace")).hexdigest()


def load_cached_report(project_root: Path, fingerprint: str) -> dict | None:
    """Return the cached report if the fingerprint matches, otherwise None."""
    cache_path = _cache_path(project_root)
    if not cache_path.exists():
        return None
    try:
        raw = cache_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("fingerprint") == fingerprint:
            report = data.get("report")
            if isinstance(report, dict):
                return report
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        pass
    return None


def save_cached_report(project_root: Path, fingerprint: str, report: dict) -> None:
    """Persist the report to the cache.  Failures are silently ignored."""
    cache_path = _cache_path(project_root)
    try:
        payload = json.dumps({"fingerprint": fingerprint, "report": report})
        if len(payload.encode("utf-8")) > _MAX_CACHE_BYTES:
            return
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp file first, then rename for atomic update.
        tmp_path = cache_path.with_suffix(".tmp")
        tmp_path.write_text(payload, encoding="utf-8")
        tmp_path.replace(cache_path)
    except (OSError, TypeError, ValueError):
        pass


def invalidate_cache(project_root: Path) -> None:
    """Remove the cache file if it exists."""
    try:
        _cache_path(project_root).unlink(missing_ok=True)
    except OSError:
        pass


def _cache_path(project_root: Path) -> Path:
    resolved = project_root.resolve()
    return resolved / _CACHE_DIR / _CACHE_FILE
