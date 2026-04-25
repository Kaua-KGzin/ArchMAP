from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from archmap.core.parser.project_parser import ParsedFile

logger = logging.getLogger(__name__)

_CACHE_VERSION = 1
_CACHE_FILENAME = ".archmap-cache.json"


class ParseCache:
    """File-level incremental parse cache keyed by (file_id, mtime)."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, ParsedFile]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, file_id: str, mtime: float) -> ParsedFile | None:
        entry = self._store.get(file_id)
        if entry is not None and entry[0] == mtime:
            return entry[1]
        return None

    def put(self, file_id: str, mtime: float, result: ParsedFile) -> None:
        self._store[file_id] = (mtime, result)

    def size(self) -> int:
        return len(self._store)

    # ------------------------------------------------------------------
    # Disk persistence
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, project_root: Path) -> ParseCache:
        cache_path = project_root / _CACHE_FILENAME
        instance = cls()
        if not cache_path.is_file():
            return instance
        try:
            raw = json.loads(cache_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or raw.get("version") != _CACHE_VERSION:
                return instance
            for file_id, entry in raw.get("entries", {}).items():
                if not isinstance(entry, dict):
                    continue
                mtime = entry.get("mtime")
                if not isinstance(mtime, float | int):
                    continue
                parsed: ParsedFile = {
                    "id": entry.get("id", file_id),
                    "label": entry.get("label", file_id),
                    "type": entry.get("type", "file"),
                    "language": entry.get("language", ""),
                    "dependencies": entry.get("dependencies", []),
                }
                instance._store[file_id] = (float(mtime), parsed)
        except Exception as exc:
            logger.warning("Could not load parse cache: %s", exc)
        return instance

    def save(self, project_root: Path) -> None:
        cache_path = project_root / _CACHE_FILENAME
        entries: dict[str, object] = {}
        for file_id, (mtime, parsed) in self._store.items():
            entries[file_id] = {
                "mtime": mtime,
                "id": parsed["id"],
                "label": parsed["label"],
                "type": parsed["type"],
                "language": parsed["language"],
                "dependencies": parsed["dependencies"],
            }
        payload = {"version": _CACHE_VERSION, "entries": entries}
        try:
            cache_path.write_text(json.dumps(payload), encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not save parse cache: %s", exc)
