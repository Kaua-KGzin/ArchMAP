"""Directory inventory: classify every file and map how binaries link to each other.

Pointing ArchMAP at an unpacked firmware image, an APK's ``lib/`` folder, a
Docker layer, or a ``dist/`` directory answers "what is in here and what
depends on what" in one pass: every executable's shared-library imports
become edges in the same node/edge shape the source-code graph uses, and
libraries found inside the directory resolve to real files.
"""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from typing import Any

from archmap.core.binary.analyzer import inspect_file
from archmap.core.binary.formats import detect_format
from archmap.core.binary.reader import open_binary
from archmap.types import Finding

MAX_INVENTORY_FILES = 5000
_SKIP_DIRS = {".git", ".hg", ".svn", "__pycache__", ".archmap"}
_LINKABLE = {"elf", "pe", "macho", "macho-fat", "wasm"}


def _linked_libraries(fmt: str, details: dict[str, Any] | None) -> list[str]:
    if not details:
        return []
    if fmt == "elf":
        return list(details.get("neededLibraries", []))
    if fmt == "pe":
        return list(details.get("importedLibraries", []))
    if fmt == "wasm":
        return list(details.get("importModules", []))
    if fmt in ("macho", "macho-fat"):
        image = details
        if details.get("universal"):
            archs = [a for a in details.get("architectures", []) if "image" in a]
            image = archs[0]["image"] if archs else {}
        return [entry["name"] for entry in image.get("linkedLibraries", [])]
    return []


def inspect_directory(
    root: str | Path,
    *,
    max_files: int = MAX_INVENTORY_FILES,
    include_strings: bool = False,
) -> dict[str, Any]:
    """Classify files under ``root`` and build the binary linkage graph."""
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise NotADirectoryError(f"not a directory: {root_path}")

    files: list[Path] = []
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        for filename in sorted(filenames):
            candidate = Path(dirpath) / filename
            if candidate.is_symlink() or not candidate.is_file():
                continue
            files.append(candidate)
            if len(files) >= max_files:
                truncated = True
                break
        if truncated:
            break

    by_format: Counter[str] = Counter()
    by_category: Counter[str] = Counter()
    total_size = 0
    binaries: list[dict[str, Any]] = []
    errors: list[str] = []
    findings: list[Finding] = []
    # Maps a library's basename to the file inside the tree that provides it.
    provided: dict[str, str] = {}

    for file_path in files:
        rel = file_path.relative_to(root_path).as_posix()
        try:
            size = file_path.stat().st_size
            with open_binary(file_path) as data:
                fmt = detect_format(data, file_path.name)
        except OSError as exc:
            errors.append(f"{rel}: {exc}")
            continue
        total_size += size
        by_format[fmt["format"]] += 1
        by_category[fmt["category"]] += 1
        if fmt["format"] not in _LINKABLE and fmt["category"] not in ("archive", "database"):
            continue
        try:
            report = inspect_file(
                file_path,
                include_strings=include_strings,
                entropy_blocks=16,
                entropy_sample_bytes=16 * 1024,
            )
        except (OSError, ValueError) as exc:
            errors.append(f"{rel}: {exc}")
            continue
        details = report.get("details")
        libraries = _linked_libraries(fmt["format"], details)
        provided.setdefault(file_path.name, rel)
        soname = (details or {}).get("soname") or (details or {}).get("installName")
        if soname:
            provided.setdefault(Path(str(soname)).name, rel)
        for finding in report["findings"]:
            finding["file"] = rel
            finding["evidence"] = [f"File: {rel}", *finding["evidence"][1:]]
            findings.append(finding)
        binaries.append({
            "file": rel,
            "format": fmt["format"],
            "description": fmt["description"],
            "size": size,
            "sha256": report["hashes"]["sha256"],
            "libraries": libraries,
            "findingCount": len(report["findings"]),
            "hardening": (details or {}).get("hardening"),
        })

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []
    library_users: Counter[str] = Counter()
    # Only formats that link libraries belong in the linkage graph; archives and
    # databases are listed in `binaries` but would be isolated nodes here.
    linkable = [b for b in binaries if b["format"] in _LINKABLE]
    for binary in linkable:
        nodes[binary["file"]] = {"id": binary["file"], "type": "binary", "format": binary["format"]}
    for binary in linkable:
        for library in binary["libraries"]:
            target = provided.get(Path(library).name)
            target_id = target if target else f"lib:{library}"
            if target_id not in nodes:
                nodes[target_id] = {"id": target_id, "type": "library", "format": "external"}
            edges.append({"source": binary["file"], "target": target_id})
            library_users[target_id] += 1

    for index, finding in enumerate(findings, start=1):
        finding["id"] = f"BIN-{index:03d}"

    return {
        "root": str(root_path),
        "filesScanned": len(files),
        "truncated": truncated,
        "totalSize": total_size,
        "byFormat": dict(by_format.most_common()),
        "byCategory": dict(by_category.most_common()),
        "binaries": binaries,
        "graph": {"nodes": list(nodes.values()), "edges": edges},
        "mostLinkedLibraries": [
            {"library": name, "dependents": count} for name, count in library_users.most_common(15)
        ],
        "findings": findings,
        "errors": errors[:100],
    }
