"""WebAssembly module parser: sections, imports, exports, producer metadata."""

from __future__ import annotations

from typing import Any

from archmap.core.binary.reader import MAX_IMPORTS, BinaryFormatError, ByteSource

_SECTION_NAMES = {
    0: "custom",
    1: "type",
    2: "import",
    3: "function",
    4: "table",
    5: "memory",
    6: "global",
    7: "export",
    8: "start",
    9: "element",
    10: "code",
    11: "data",
    12: "datacount",
    13: "tag",
}
_KINDS = {0: "function", 1: "table", 2: "memory", 3: "global", 4: "tag"}


class _Cursor:
    def __init__(self, data: bytes, pos: int = 0, end: int | None = None) -> None:
        self.data = data
        self.pos = pos
        self.end = len(data) if end is None else end

    def byte(self) -> int:
        if self.pos >= self.end:
            raise BinaryFormatError("unexpected end of WASM data")
        value = self.data[self.pos]
        self.pos += 1
        return value

    def uleb(self) -> int:
        result = 0
        shift = 0
        while True:
            byte = self.byte()
            result |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return result
            shift += 7
            if shift > 63:
                raise BinaryFormatError("LEB128 value too long")

    def name(self) -> str:
        length = self.uleb()
        if self.pos + length > self.end:
            raise BinaryFormatError("name runs past section end")
        raw = self.data[self.pos : self.pos + length]
        self.pos += length
        return raw.decode("utf-8", errors="replace")

    def skip_limits(self) -> None:
        flags = self.uleb()
        self.uleb()
        if flags & 1:
            self.uleb()


def parse_wasm(data: ByteSource) -> dict[str, Any]:
    raw = bytes(data)
    if raw[:4] != b"\x00asm":
        raise BinaryFormatError("not a WebAssembly module")
    version = int.from_bytes(raw[4:8], "little")
    cursor = _Cursor(raw, 8)
    sections: list[dict[str, Any]] = []
    imports: list[dict[str, str]] = []
    exports: list[dict[str, str]] = []
    custom: list[str] = []
    producers: dict[str, list[str]] = {}
    function_count = 0
    limitations: list[str] = []

    while cursor.pos < cursor.end:
        try:
            section_id = cursor.byte()
            size = cursor.uleb()
        except BinaryFormatError as exc:
            limitations.append(str(exc))
            break
        start = cursor.pos
        end = start + size
        if end > len(raw):
            limitations.append(f"section {section_id} runs past end of file")
            break
        name = _SECTION_NAMES.get(section_id, f"unknown({section_id})")
        body = _Cursor(raw, start, end)
        try:
            if section_id == 0:
                custom_name = body.name()
                custom.append(custom_name)
                name = f"custom:{custom_name}"
                if custom_name == "producers":
                    producers = _parse_producers(body)
            elif section_id == 2:
                for _ in range(min(body.uleb(), MAX_IMPORTS)):
                    module, field = body.name(), body.name()
                    kind = body.byte()
                    if kind == 0:
                        body.uleb()
                    elif kind == 1:
                        body.byte()
                        body.skip_limits()
                    elif kind == 2:
                        body.skip_limits()
                    elif kind == 3:
                        body.byte()
                        body.byte()
                    elif kind == 4:
                        body.byte()
                        body.uleb()
                    imports.append({"module": module, "name": field, "kind": _KINDS.get(kind, "?")})
            elif section_id == 3:
                function_count = body.uleb()
            elif section_id == 7:
                for _ in range(min(body.uleb(), MAX_IMPORTS)):
                    field = body.name()
                    kind = body.byte()
                    body.uleb()
                    exports.append({"name": field, "kind": _KINDS.get(kind, "?")})
        except BinaryFormatError as exc:
            limitations.append(f"{name} section: {exc}")
        sections.append({"id": section_id, "name": name, "offset": start, "size": size})
        cursor.pos = end

    import_modules = sorted({entry["module"] for entry in imports})
    return {
        "version": version,
        "sections": sections,
        "imports": imports[:2000],
        "importModules": import_modules,
        "exports": exports[:2000],
        "definedFunctionCount": function_count,
        "customSections": custom,
        "producers": producers,
        "toolchain": _guess_toolchain(import_modules, producers),
        "limitations": limitations,
    }


def _parse_producers(body: _Cursor) -> dict[str, list[str]]:
    """Decode the `producers` custom section: language, processed-by, sdk."""
    fields: dict[str, list[str]] = {}
    for _ in range(min(body.uleb(), 16)):
        field = body.name()
        values: list[str] = []
        for _ in range(min(body.uleb(), 32)):
            tool, version = body.name(), body.name()
            values.append(f"{tool} {version}".strip())
        fields[field] = values
    return fields


def _guess_toolchain(modules: list[str], producers: dict[str, list[str]]) -> str | None:
    languages = producers.get("language", [])
    tools = producers.get("processed-by", [])
    if languages or tools:
        return "; ".join(languages + tools)
    if any(m.startswith("wasi") for m in modules):
        return "WASI"
    if "wbg" in modules or any("wbindgen" in m for m in modules):
        return "Rust (wasm-bindgen)"
    if "go" in modules or "gojs" in modules:
        return "Go"
    if "env" in modules:
        return "Emscripten / C/C++ (env imports)"
    return None
