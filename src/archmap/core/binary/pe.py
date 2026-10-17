"""PE/COFF parser (Windows EXE/DLL/.NET): headers, sections, imports, exports, mitigations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from archmap.core.binary.entropy import HIGH_ENTROPY, shannon_entropy
from archmap.core.binary.reader import (
    MAX_IMPORTS,
    MAX_SECTIONS,
    BinaryFormatError,
    ByteSource,
    ByteView,
)

_MACHINES = {
    0x014C: "x86",
    0x8664: "x86-64",
    0x01C0: "ARM",
    0x01C4: "ARMv7 (Thumb-2)",
    0xAA64: "ARM64",
    0xA641: "ARM64EC",
    0x0200: "IA-64",
    0x5064: "RISC-V64",
}
_SUBSYSTEMS = {
    1: "native",
    2: "Windows GUI",
    3: "Windows console",
    9: "Windows CE GUI",
    10: "EFI application",
    11: "EFI boot service driver",
    12: "EFI runtime driver",
    14: "Xbox",
    16: "Windows boot application",
}
# IMAGE_DLLCHARACTERISTICS_*
_DLL_FLAGS = {
    "highEntropyVA": 0x0020,
    "aslr": 0x0040,
    "forceIntegrity": 0x0080,
    "dep": 0x0100,
    "noSEH": 0x0400,
    "controlFlowGuard": 0x4000,
}
_IMAGE_FILE_DLL = 0x2000
_IMAGE_SCN_MEM_EXECUTE = 0x20000000
_IMAGE_SCN_MEM_READ = 0x40000000
_IMAGE_SCN_MEM_WRITE = 0x80000000
_DIR_EXPORT, _DIR_IMPORT, _DIR_SECURITY, _DIR_DELAY_IMPORT, _DIR_CLR = 0, 1, 4, 13, 14
_PACKER_SECTIONS = {
    "UPX0": "UPX",
    "UPX1": "UPX",
    ".aspack": "ASPack",
    ".adata": "ASPack",
    ".MPRESS1": "MPRESS",
    ".petite": "Petite",
    ".themida": "Themida",
    ".vmp0": "VMProtect",
    ".vmp1": "VMProtect",
    ".enigma1": "Enigma",
}


def parse_pe(data: ByteSource) -> dict[str, Any]:
    """Parse a PE image. Raises :class:`BinaryFormatError` on a broken header."""
    view = ByteView(data, little_endian=True)
    if view.bytes_at(0, 2) != b"MZ":
        raise BinaryFormatError("missing MZ header")
    pe_offset = view.u32(0x3C)
    if view.bytes_at(pe_offset, 4) != b"PE\x00\x00":
        raise BinaryFormatError("missing PE signature")
    limitations: list[str] = []

    coff = pe_offset + 4
    machine, num_sections, timestamp, _symptr, _nsyms, opt_size, characteristics = view.unpack(
        "HHIIIHH", coff
    )
    opt = coff + 20
    magic = view.u16(opt)
    if magic == 0x10B:
        is64 = False
    elif magic == 0x20B:
        is64 = True
    else:
        raise BinaryFormatError(f"unknown optional header magic {magic:#x}")

    entry_rva = view.u32(opt + 16)
    image_base = view.u64(opt + 24) if is64 else view.u32(opt + 28)
    subsystem = view.u16(opt + 68)
    dll_characteristics = view.u16(opt + 70)
    dir_count_offset = opt + (108 if is64 else 92)
    dir_count = min(view.u32(dir_count_offset), 16)
    directories: list[tuple[int, int]] = []
    for index in range(dir_count):
        try:
            rva, size = view.unpack("II", dir_count_offset + 4 + index * 8)
            directories.append((rva, size))
        except BinaryFormatError:
            limitations.append("data directories truncated")
            break

    sections = _parse_sections(view, opt + opt_size, num_sections, limitations)

    def directory(index: int) -> tuple[int, int]:
        return directories[index] if index < len(directories) else (0, 0)

    imports = _parse_imports(view, sections, directory(_DIR_IMPORT)[0], is64, limitations)
    delay_imports = _parse_delay_imports(
        view, sections, directory(_DIR_DELAY_IMPORT)[0], is64, limitations
    )
    exports = _parse_exports(view, sections, *directory(_DIR_EXPORT), limitations)

    try:
        compiled = datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (OverflowError, OSError, ValueError):
        compiled = None

    hardening = {name: bool(dll_characteristics & bit) for name, bit in _DLL_FLAGS.items()}
    hardening["signed"] = directory(_DIR_SECURITY)[1] > 0
    if not is64:
        # High-entropy ASLR only exists for 64-bit images.
        hardening.pop("highEntropyVA")

    packers = sorted(
        {_PACKER_SECTIONS[s["name"]] for s in sections if s["name"] in _PACKER_SECTIONS}
    )
    high_entropy_code = [
        s["name"]
        for s in sections
        if "X" in s["flags"] and float(s.get("entropy", 0.0)) >= HIGH_ENTROPY
    ]
    writable_code = [s["name"] for s in sections if "X" in s["flags"] and "W" in s["flags"]]

    return {
        "format": "PE32+" if is64 else "PE32",
        "machine": _MACHINES.get(machine, f"unknown ({machine:#x})"),
        "kind": "DLL" if characteristics & _IMAGE_FILE_DLL else "EXE",
        "subsystem": _SUBSYSTEMS.get(subsystem, f"unknown ({subsystem})"),
        "compiledAt": compiled,
        "imageBase": hex(image_base),
        "entryPoint": hex(entry_rva),
        "dotnet": directory(_DIR_CLR)[0] != 0,
        "sections": sections,
        "imports": imports,
        "delayImports": delay_imports,
        "importedLibraries": sorted({entry["library"] for entry in imports + delay_imports}),
        "importedFunctionCount": sum(len(entry["functions"]) for entry in imports),
        "exports": exports,
        "hardening": hardening,
        "packers": packers,
        "highEntropyCodeSections": high_entropy_code,
        "writableCodeSections": writable_code,
        "limitations": limitations,
    }


def _parse_sections(
    view: ByteView, table_offset: int, count: int, limitations: list[str]
) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for index in range(min(count, MAX_SECTIONS)):
        offset = table_offset + index * 40
        try:
            raw_name = view.bytes_at(offset, 8)
            vsize, vaddr, raw_size, raw_ptr = view.unpack("IIII", offset + 8)
            characteristics = view.u32(offset + 36)
        except BinaryFormatError as exc:
            limitations.append(f"section table truncated: {exc}")
            break
        flags = "".join(
            flag
            for flag, bit in (
                ("R", _IMAGE_SCN_MEM_READ),
                ("W", _IMAGE_SCN_MEM_WRITE),
                ("X", _IMAGE_SCN_MEM_EXECUTE),
            )
            if characteristics & bit
        )
        entry: dict[str, Any] = {
            "name": raw_name.rstrip(b"\x00").decode("utf-8", errors="replace"),
            "virtualAddress": vaddr,
            "virtualSize": vsize,
            "rawSize": raw_size,
            "rawOffset": raw_ptr,
            "flags": flags,
        }
        if raw_size and raw_ptr + raw_size <= view.size:
            entry["entropy"] = shannon_entropy(
                view.data[raw_ptr : raw_ptr + min(raw_size, 1 << 16)]
            )
        sections.append(entry)
    return sections


def _rva_to_offset(sections: list[dict[str, Any]], rva: int) -> int:
    for section in sections:
        start = section["virtualAddress"]
        span = max(section["virtualSize"], section["rawSize"])
        if start <= rva < start + span:
            return int(section["rawOffset"] + (rva - start))
    # Headers (and some tiny images) are mapped 1:1.
    if sections and rva < sections[0]["virtualAddress"]:
        return rva
    raise BinaryFormatError(f"RVA {rva:#x} is not inside any section")


def _read_thunks(
    view: ByteView, sections: list[dict[str, Any]], thunk_rva: int, is64: bool, budget: list[int]
) -> list[str]:
    functions: list[str] = []
    if not thunk_rva:
        return functions
    offset = _rva_to_offset(sections, thunk_rva)
    step = 8 if is64 else 4
    ordinal_flag = 1 << 63 if is64 else 1 << 31
    while budget[0] > 0:
        value = view.u64(offset) if is64 else view.u32(offset)
        if value == 0:
            break
        if value & ordinal_flag:
            functions.append(f"ordinal#{value & 0xFFFF}")
        else:
            functions.append(view.cstring(_rva_to_offset(sections, value & 0x7FFFFFFF) + 2, 512))
        offset += step
        budget[0] -= 1
    return functions


def _parse_imports(
    view: ByteView, sections: list[dict[str, Any]], rva: int, is64: bool, limitations: list[str]
) -> list[dict[str, Any]]:
    if not rva:
        return []
    imports: list[dict[str, Any]] = []
    budget = [MAX_IMPORTS]
    try:
        offset = _rva_to_offset(sections, rva)
        for index in range(1024):
            original_thunk, _ts, _fwd, name_rva, first_thunk = view.unpack(
                "IIIII", offset + index * 20
            )
            if not name_rva and not first_thunk:
                break
            library = view.cstring(_rva_to_offset(sections, name_rva), 256)
            functions = _read_thunks(view, sections, original_thunk or first_thunk, is64, budget)
            imports.append({"library": library, "functions": functions})
    except BinaryFormatError as exc:
        limitations.append(f"import table: {exc}")
    if budget[0] <= 0:
        limitations.append(f"import list capped at {MAX_IMPORTS} functions")
    return imports


def _parse_delay_imports(
    view: ByteView, sections: list[dict[str, Any]], rva: int, is64: bool, limitations: list[str]
) -> list[dict[str, Any]]:
    if not rva:
        return []
    imports: list[dict[str, Any]] = []
    budget = [MAX_IMPORTS]
    try:
        offset = _rva_to_offset(sections, rva)
        for index in range(1024):
            fields = view.unpack("IIIIIIII", offset + index * 32)
            name_rva, int_rva = fields[1], fields[4]
            if not name_rva:
                break
            library = view.cstring(_rva_to_offset(sections, name_rva), 256)
            functions = _read_thunks(view, sections, int_rva, is64, budget)
            imports.append({"library": library, "functions": functions, "delayed": True})
    except BinaryFormatError as exc:
        limitations.append(f"delay-import table: {exc}")
    return imports


def _parse_exports(
    view: ByteView, sections: list[dict[str, Any]], rva: int, size: int, limitations: list[str]
) -> dict[str, Any] | None:
    if not rva:
        return None
    try:
        offset = _rva_to_offset(sections, rva)
        name_rva, base, n_functions, n_names, _funcs, names_rva, _ords = view.unpack(
            "IIIIIII", offset + 12
        )
        dll_name = view.cstring(_rva_to_offset(sections, name_rva), 256)
        names: list[str] = []
        if n_names:
            names_offset = _rva_to_offset(sections, names_rva)
            for index in range(min(n_names, MAX_IMPORTS)):
                entry_rva = view.u32(names_offset + index * 4)
                names.append(view.cstring(_rva_to_offset(sections, entry_rva), 512))
    except BinaryFormatError as exc:
        limitations.append(f"export table: {exc}")
        return None
    return {
        "dllName": dll_name,
        "ordinalBase": base,
        "functionCount": n_functions,
        "names": names[:2000],
        "nameCount": len(names),
    }
