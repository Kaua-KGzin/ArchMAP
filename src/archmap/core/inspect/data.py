"""Structured-data inspection: schema, size, and red flags for data files and containers.

Covers the formats a developer or agent most often needs to understand
without opening a dedicated tool: JSON/JSONL, CSV/TSV, SQLite, and archives
(ZIP/JAR/APK/OOXML, tar, gzip). Everything is read-only: SQLite is opened
with ``mode=ro&immutable=1`` and archives are listed, never extracted.
"""

from __future__ import annotations

import csv
import gzip
import json
import re
import sqlite3
import struct
import tarfile
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_CSV_SAMPLE_ROWS = 1000
MAX_ENTRIES_LISTED = 50
MAX_SCHEMA_DEPTH = 6
# Uncompressed/compressed ratio above which an archive is flagged as a possible bomb.
ZIP_BOMB_RATIO = 100

_ARCHIVE_FORMATS = {"zip", "jar", "apk", "docx", "xlsx", "pptx"}


def inspect_data(path: Path, fmt: str) -> dict[str, Any] | None:
    """Dispatch on ``fmt`` (from :func:`detect_format`); ``None`` if not a data format."""
    try:
        if fmt == "json" or path.suffix.lower() in (".jsonl", ".ndjson"):
            return _inspect_json(path)
        if fmt == "csv":
            return _inspect_csv(path)
        if fmt == "sqlite":
            return _inspect_sqlite(path)
        if fmt in _ARCHIVE_FORMATS:
            return _inspect_zip(path, fmt)
        if fmt == "tar" or (fmt in ("gzip", "bzip2", "xz") and _is_tarball(path)):
            return _inspect_tar(path)
        if fmt == "gzip":
            return _inspect_gzip(path)
    except (OSError, ValueError, sqlite3.Error, zipfile.BadZipFile, tarfile.TarError) as exc:
        return {"kind": fmt, "error": f"{type(exc).__name__}: {exc}", "warnings": []}
    return None


# --------------------------------------------------------------------------- JSON


def _schema(value: Any, depth: int = 0) -> Any:
    """Compact type tree: objects map keys to types, arrays describe their elements."""
    if depth >= MAX_SCHEMA_DEPTH:
        return "…"
    if isinstance(value, dict):
        return {key: _schema(item, depth + 1) for key, item in list(value.items())[:100]}
    if isinstance(value, list):
        if not value:
            return ["empty"]
        merged: dict[str, Any] = {}
        scalar_types: set[str] = set()
        for item in value[:50]:
            described = _schema(item, depth + 1)
            if isinstance(described, dict):
                for key, item_type in described.items():
                    merged.setdefault(key, item_type)
            else:
                scalar_types.add(
                    described if isinstance(described, str) else json.dumps(described)
                )
        if merged:
            return [merged]
        return [" | ".join(sorted(scalar_types))]
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return "string"


def _inspect_json(path: Path) -> dict[str, Any]:
    size = path.stat().st_size
    if path.suffix.lower() in (".jsonl", ".ndjson"):
        records = 0
        bad = 0
        sample: list[Any] = []
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                records += 1
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    bad += 1
                    continue
                if len(sample) < 50:
                    sample.append(obj)
        return {
            "kind": "jsonl",
            "records": records,
            "invalidLines": bad,
            "schema": _schema(sample),
            "warnings": [],
        }
    if size > MAX_JSON_BYTES:
        return {
            "kind": "json",
            "error": f"file larger than {MAX_JSON_BYTES} bytes; schema not inferred",
            "warnings": [],
        }
    try:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return {"kind": "json", "valid": False, "error": str(exc), "warnings": []}
    summary: dict[str, Any] = {"kind": "json", "valid": True, "rootType": type(document).__name__}
    if isinstance(document, list):
        summary["items"] = len(document)
    elif isinstance(document, dict):
        summary["keys"] = len(document)
    summary["schema"] = _schema(document)
    summary["warnings"] = []
    return summary


# --------------------------------------------------------------------------- CSV

_INT = re.compile(r"^[+-]?\d+$")
_FLOAT = re.compile(r"^[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?")
_BOOL = {"true", "false", "yes", "no", "t", "f"}


def _cell_type(value: str) -> str:
    text = value.strip()
    if not text:
        return "empty"
    if _INT.match(text):
        return "integer"
    if _FLOAT.match(text):
        return "number"
    if text.lower() in _BOOL:
        return "boolean"
    if _DATE.match(text):
        return "date"
    return "string"


def _inspect_csv(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig", errors="replace", newline="") as handle:
        head = handle.read(64 * 1024)
        handle.seek(0)
        try:
            dialect: Any = csv.Sniffer().sniff(head, delimiters=",;\t|")
            has_header = csv.Sniffer().has_header(head)
        except csv.Error:
            dialect = csv.excel_tab if path.suffix.lower() == ".tsv" else csv.excel
            has_header = True
        reader = csv.reader(handle, dialect)
        header = next(reader, [])
        columns = header if has_header else [f"column_{i + 1}" for i in range(len(header))]
        type_counts: list[Counter[str]] = [Counter() for _ in columns]
        rows = 0 if has_header else 1
        ragged = 0
        if not has_header:
            for index, cell in enumerate(header):
                type_counts[index][_cell_type(cell)] += 1
        for row in reader:
            rows += 1
            if len(row) != len(columns):
                ragged += 1
            if rows <= MAX_CSV_SAMPLE_ROWS:
                for index, cell in enumerate(row[: len(columns)]):
                    type_counts[index][_cell_type(cell)] += 1

    described = []
    for name, counts in zip(columns, type_counts, strict=False):
        non_empty = {k: v for k, v in counts.items() if k != "empty"}
        if not non_empty:
            inferred = "empty"
        elif set(non_empty) <= {"integer"}:
            inferred = "integer"
        elif set(non_empty) <= {"integer", "number"}:
            inferred = "number"
        else:
            inferred = max(non_empty, key=lambda key: non_empty[key])
        described.append({"name": name, "type": inferred, "empty": counts.get("empty", 0)})
    warnings = []
    if ragged:
        warnings.append(f"{ragged} row(s) have a different column count than the header")
    return {
        "kind": "csv",
        "delimiter": getattr(dialect, "delimiter", ","),
        "hasHeader": has_header,
        "rows": rows,
        "columns": described,
        "raggedRows": ragged,
        "warnings": warnings,
    }


# --------------------------------------------------------------------------- SQLite


def _inspect_sqlite(path: Path) -> dict[str, Any]:
    # immutable=1: no locks, no WAL/journal writes — safe on read-only media too.
    uri = f"{path.resolve().as_uri()}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    try:
        objects = connection.execute(
            "SELECT type, name FROM sqlite_master WHERE type IN ('table','view') "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        tables = []
        for obj_type, name in objects[:200]:
            quoted = '"' + str(name).replace('"', '""') + '"'
            columns = [
                {"name": col[1], "type": col[2] or "ANY", "primaryKey": bool(col[5])}
                # PRAGMA takes no bound parameters; `quoted` escapes the identifier.
                for col in connection.execute(  # archmap-ignore: py-sql-format
                    f"PRAGMA table_info({quoted})"
                ).fetchall()
            ]
            entry: dict[str, Any] = {"name": name, "type": obj_type, "columns": columns}
            if obj_type == "table":
                try:
                    # Table names come from the inspected file; `quoted` escapes them.
                    count_sql = f"SELECT COUNT(*) FROM {quoted}"
                    # archmap-ignore: identifier quoted above, no bound-parameter form
                    entry["rows"] = connection.execute(count_sql).fetchone()[0]
                except sqlite3.Error as exc:
                    entry["rows"] = None
                    entry["error"] = str(exc)
            tables.append(entry)
        indexes = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'index'"
        ).fetchone()[0]
        user_version = connection.execute("PRAGMA user_version").fetchone()[0]
    finally:
        connection.close()
    return {
        "kind": "sqlite",
        "tables": tables,
        "tableCount": sum(1 for t in tables if t["type"] == "table"),
        "viewCount": sum(1 for t in tables if t["type"] == "view"),
        "indexCount": indexes,
        "userVersion": user_version,
        "warnings": [],
    }


# --------------------------------------------------------------------------- Archives


def _unsafe_member(name: str) -> bool:
    """Absolute paths and ``..`` components escape the extraction directory (zip-slip)."""
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        return True
    return ".." in PurePosixPath(normalized).parts


def _inspect_zip(path: Path, fmt: str) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
    compressed = sum(info.compress_size for info in infos)
    uncompressed = sum(info.file_size for info in infos)
    ratio = round(uncompressed / compressed, 1) if compressed else 0.0
    unsafe = [info.filename for info in infos if _unsafe_member(info.filename)]
    encrypted = sum(1 for info in infos if info.flag_bits & 0x1)
    extensions = Counter(Path(info.filename).suffix.lower() or "(none)" for info in infos)

    warnings = []
    if unsafe:
        warnings.append(f"{len(unsafe)} entry path(s) escape the extraction directory (zip-slip)")
    if ratio >= ZIP_BOMB_RATIO and uncompressed > 50 * 1024 * 1024:
        warnings.append(f"compression ratio {ratio}:1 — possible decompression bomb")

    summary: dict[str, Any] = {
        "kind": fmt,
        "entries": len(infos),
        "compressedSize": compressed,
        "uncompressedSize": uncompressed,
        "compressionRatio": ratio,
        "encryptedEntries": encrypted,
        "extensions": dict(extensions.most_common(15)),
        "largestEntries": [
            {"name": info.filename, "size": info.file_size}
            for info in sorted(infos, key=lambda i: i.file_size, reverse=True)[:10]
        ],
        "unsafePaths": unsafe[:MAX_ENTRIES_LISTED],
        "warnings": warnings,
    }
    if fmt == "apk":
        names = [info.filename for info in infos]
        native = [n for n in names if n.startswith("lib/") and n.endswith(".so")]
        summary["android"] = {
            "dexFiles": sorted(n for n in names if re.match(r"^classes\d*\.dex$", n)),
            "nativeLibraries": native[:MAX_ENTRIES_LISTED],
            "abis": sorted({n.split("/")[1] for n in native if n.count("/") >= 2}),
            "signatureFiles": sorted(n for n in names if n.startswith("META-INF/"))[:10],
        }
    elif fmt == "jar":
        summary["java"] = {
            "classes": extensions.get(".class", 0),
            "nestedJars": extensions.get(".jar", 0),
        }
    return summary


def _is_tarball(path: Path) -> bool:
    try:
        return tarfile.is_tarfile(path)
    except (OSError, tarfile.TarError):
        return False


def _inspect_tar(path: Path) -> dict[str, Any]:
    with tarfile.open(path) as archive:
        members = archive.getmembers()
    kinds = Counter(
        "dir" if m.isdir() else "symlink" if m.issym() else "hardlink" if m.islnk()
        else "device" if (m.ischr() or m.isblk()) else "file"
        for m in members
    )
    unsafe = [m.name for m in members if _unsafe_member(m.name)]
    escaping_links = [
        m.name for m in members
        if (m.issym() or m.islnk()) and _unsafe_member(m.linkname)
    ]
    setuid = [m.name for m in members if m.isfile() and m.mode & 0o6000]
    warnings = []
    if unsafe:
        warnings.append(f"{len(unsafe)} member path(s) escape the extraction directory")
    if escaping_links:
        warnings.append(f"{len(escaping_links)} link(s) point outside the archive")
    if kinds.get("device"):
        warnings.append(f"{kinds['device']} device node(s) in archive")
    if setuid:
        warnings.append(f"{len(setuid)} setuid/setgid file(s) in archive")
    return {
        "kind": "tar",
        "members": len(members),
        "memberTypes": dict(kinds),
        "totalSize": sum(m.size for m in members if m.isfile()),
        "unsafePaths": unsafe[:MAX_ENTRIES_LISTED],
        "escapingLinks": escaping_links[:MAX_ENTRIES_LISTED],
        "setuidFiles": setuid[:MAX_ENTRIES_LISTED],
        "warnings": warnings,
    }


def _inspect_gzip(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        header = handle.read(10)
        flags = header[3] if len(header) >= 4 else 0
        original_name = None
        if flags & 0x08:  # FNAME
            if flags & 0x04:  # FEXTRA
                (extra_len,) = struct.unpack("<H", handle.read(2))
                handle.seek(extra_len, 1)
            name = bytearray()
            while (byte := handle.read(1)) and byte != b"\x00" and len(name) < 1024:
                name += byte
            original_name = name.decode("latin-1")
        handle.seek(-4, 2)
        (isize,) = struct.unpack("<I", handle.read(4))
    with gzip.open(path, "rb") as stream:
        stream.read(1)  # validates the header
    return {
        "kind": "gzip",
        "originalName": original_name,
        "uncompressedSizeMod32": isize,
        "warnings": [],
    }
