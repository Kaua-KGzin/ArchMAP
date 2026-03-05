from __future__ import annotations

import re
from typing import TypedDict


class RustImportEntry(TypedDict):
    type: str
    path: str
    module: str
    crate: str


USE_RE = re.compile(r"^\s*use\s+([^;]+);", re.MULTILINE)
MOD_RE = re.compile(r"^\s*mod\s+([a-zA-Z0-9_]+)\s*;", re.MULTILINE)
EXTERN_RE = re.compile(r"^\s*extern\s+crate\s+([a-zA-Z0-9_]+)\s*;", re.MULTILINE)


def parse_rust_imports(source_code: str) -> list[RustImportEntry]:
    dependencies: list[RustImportEntry] = []

    for match in USE_RE.finditer(source_code):
        normalized = _normalize_use_path(match.group(1))
        if not normalized:
            continue
        dependencies.append({"type": "use", "path": normalized, "module": "", "crate": ""})

    for match in MOD_RE.finditer(source_code):
        dependencies.append(
            {"type": "mod", "path": "", "module": match.group(1).strip(), "crate": ""}
        )

    for match in EXTERN_RE.finditer(source_code):
        dependencies.append(
            {"type": "extern", "path": "", "module": "", "crate": match.group(1).strip()}
        )

    return dependencies


def _normalize_use_path(raw_path: str) -> str:
    compact = " ".join(raw_path.split()).removeprefix("pub ").strip()
    without_alias = compact.split(" as ", maxsplit=1)[0].strip()
    without_group = re.sub(r"\{.*\}", "", without_alias).strip()
    without_wildcard = without_group.removesuffix("::*").strip()
    return without_wildcard.removesuffix("::").strip()
