"""ELF parser: headers, segments, sections, dynamic linking, symbols, hardening."""

from __future__ import annotations

from typing import Any

from archmap.core.binary.entropy import shannon_entropy
from archmap.core.binary.reader import (
    MAX_SECTIONS,
    MAX_SYMBOLS,
    BinaryFormatError,
    ByteSource,
    ByteView,
)

_MACHINES = {
    0x02: "SPARC",
    0x03: "x86",
    0x08: "MIPS",
    0x14: "PowerPC",
    0x15: "PowerPC64",
    0x16: "S390",
    0x28: "ARM",
    0x2B: "SPARCv9",
    0x32: "IA-64",
    0x3E: "x86-64",
    0xB7: "AArch64",
    0xF3: "RISC-V",
    0xF7: "BPF",
    0x102: "LoongArch",
}
_TYPES = {0: "NONE", 1: "REL (object)", 2: "EXEC (executable)", 3: "DYN (shared/PIE)", 4: "CORE"}
_OSABI = {
    0: "SYSV",
    3: "Linux",
    6: "Solaris",
    9: "FreeBSD",
    12: "OpenBSD",
    97: "ARM",
    255: "Standalone",
}

PT_LOAD, PT_DYNAMIC, PT_INTERP = 1, 2, 3
PT_GNU_STACK, PT_GNU_RELRO = 0x6474E551, 0x6474E552
PF_X = 1
SHT_SYMTAB, SHT_DYNAMIC, SHT_DYNSYM = 2, 6, 11
DT_NULL, DT_NEEDED, DT_STRTAB, DT_SONAME, DT_RPATH = 0, 1, 5, 14, 15
DT_BIND_NOW, DT_FLAGS, DT_RUNPATH, DT_FLAGS_1 = 24, 30, 29, 0x6FFFFFFB
DF_BIND_NOW, DF_1_NOW, DF_1_PIE = 0x8, 0x1, 0x08000000
STB_GLOBAL, STB_WEAK = 1, 2
STT_OBJECT, STT_FUNC, STT_GNU_IFUNC = 1, 2, 10
SHN_UNDEF = 0


def parse_elf(data: ByteSource) -> dict[str, Any]:
    """Parse an ELF image. Raises :class:`BinaryFormatError` on a broken header."""
    if len(data) < 16 or bytes(data[:4]) != b"\x7fELF":
        raise BinaryFormatError("not an ELF file")
    ei_class = data[4]
    ei_data = data[5]
    if ei_class not in (1, 2) or ei_data not in (1, 2):
        raise BinaryFormatError("invalid ELF class or data encoding")
    is64 = ei_class == 2
    view = ByteView(data, little_endian=ei_data == 1)
    limitations: list[str] = []

    if is64:
        (e_type, e_machine, _ver, e_entry, e_phoff, e_shoff, _flags, _ehsize,
         e_phentsize, e_phnum, e_shentsize, e_shnum, e_shstrndx) = view.unpack("HHIQQQIHHHHHH", 16)
    else:
        (e_type, e_machine, _ver, e_entry, e_phoff, e_shoff, _flags, _ehsize,
         e_phentsize, e_phnum, e_shentsize, e_shnum, e_shstrndx) = view.unpack("HHIIIIIHHHHHH", 16)

    result: dict[str, Any] = {
        "class": "ELF64" if is64 else "ELF32",
        "endianness": "little" if ei_data == 1 else "big",
        "osabi": _OSABI.get(data[7], f"unknown ({data[7]})"),
        "type": _TYPES.get(e_type, f"unknown ({e_type})"),
        "machine": _MACHINES.get(e_machine, f"unknown ({e_machine:#x})"),
        "entryPoint": hex(e_entry),
    }

    segments = _parse_segments(view, is64, e_phoff, e_phentsize, e_phnum, limitations)
    sections = _parse_sections(view, is64, e_shoff, e_shentsize, e_shnum, e_shstrndx, limitations)
    result["segments"] = [
        {k: v for k, v in seg.items() if k != "_raw"} for seg in segments
    ]
    result["sections"] = [
        {k: v for k, v in sec.items() if not k.startswith("_")} for sec in sections
    ]

    interp = next((s for s in segments if s["_raw"]["type"] == PT_INTERP), None)
    if interp:
        try:
            result["interpreter"] = view.cstring(interp["_raw"]["offset"], 256)
        except BinaryFormatError as exc:
            limitations.append(f"interpreter: {exc}")

    dynamic = _parse_dynamic(view, is64, segments, sections, limitations)
    result.update({
        "neededLibraries": dynamic["needed"],
        "soname": dynamic["soname"],
        "rpath": dynamic["rpath"],
        "runpath": dynamic["runpath"],
    })

    symbols = _parse_symbols(view, is64, sections, limitations)
    result["importedSymbols"] = symbols["imported"]
    result["exportedSymbols"] = symbols["exported"]
    result["importedSymbolCount"] = symbols["importedCount"]
    result["exportedSymbolCount"] = symbols["exportedCount"]

    section_names = {sec["name"] for sec in sections}
    imported_names = set(symbols["imported"])
    result["hardening"] = _hardening(e_type, segments, dynamic, imported_names, section_names)
    result["language"] = _guess_language(section_names, imported_names)
    result["limitations"] = limitations
    return result


def _parse_segments(
    view: ByteView, is64: bool, phoff: int, phentsize: int, phnum: int, limitations: list[str]
) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    names = {0: "NULL", 1: "LOAD", 2: "DYNAMIC", 3: "INTERP", 4: "NOTE", 6: "PHDR", 7: "TLS",
             PT_GNU_STACK: "GNU_STACK", PT_GNU_RELRO: "GNU_RELRO", 0x6474E550: "GNU_EH_FRAME",
             0x6474E553: "GNU_PROPERTY"}
    for index in range(min(phnum, MAX_SECTIONS)):
        offset = phoff + index * phentsize
        try:
            if is64:
                p_type, p_flags, p_offset, p_vaddr, _paddr, p_filesz, p_memsz, _align = view.unpack(
                    "IIQQQQQQ", offset
                )
            else:
                p_type, p_offset, p_vaddr, _paddr, p_filesz, p_memsz, p_flags, _align = view.unpack(
                    "IIIIIIII", offset
                )
        except BinaryFormatError as exc:
            limitations.append(f"program headers truncated: {exc}")
            break
        flags = "".join(
            flag if p_flags & bit else "-" for flag, bit in (("R", 4), ("W", 2), ("X", 1))
        )
        segments.append({
            "type": names.get(p_type, hex(p_type)),
            "offset": p_offset,
            "virtualAddress": hex(p_vaddr),
            "fileSize": p_filesz,
            "memorySize": p_memsz,
            "flags": flags,
            "_raw": {"type": p_type, "flags": p_flags, "offset": p_offset, "vaddr": p_vaddr,
                     "filesz": p_filesz},
        })
    return segments


def _parse_sections(
    view: ByteView,
    is64: bool,
    shoff: int,
    shentsize: int,
    shnum: int,
    shstrndx: int,
    limitations: list[str],
) -> list[dict[str, Any]]:
    if shoff == 0 or shnum == 0:
        limitations.append("no section header table (stripped or packed binary)")
        return []
    raw: list[tuple[int, ...]] = []
    for index in range(min(shnum, MAX_SECTIONS)):
        offset = shoff + index * shentsize
        try:
            if is64:
                raw.append(view.unpack("IIQQQQIIQQ", offset))
            else:
                raw.append(view.unpack("IIIIIIIIII", offset))
        except BinaryFormatError as exc:
            limitations.append(f"section headers truncated: {exc}")
            break

    strtab_offset = raw[shstrndx][4] if 0 <= shstrndx < len(raw) else None
    sections: list[dict[str, Any]] = []
    for header in raw:
        name_off, sh_type, sh_flags, sh_addr, sh_offset, sh_size, sh_link = header[:7]
        sh_entsize = header[9]
        name = ""
        if strtab_offset is not None:
            try:
                name = view.cstring(strtab_offset + name_off, 256)
            except BinaryFormatError:
                name = ""
        entry: dict[str, Any] = {
            "name": name,
            "type": sh_type,
            "address": hex(sh_addr),
            "offset": sh_offset,
            "size": sh_size,
            "flags": "".join(f for f, bit in (("W", 1), ("A", 2), ("X", 4)) if sh_flags & bit),
            "_link": sh_link,
            "_entsize": sh_entsize,
        }
        if sh_type != 8 and sh_size and sh_offset + sh_size <= view.size:  # 8 = NOBITS (.bss)
            entry["entropy"] = shannon_entropy(
                view.data[sh_offset : sh_offset + min(sh_size, 1 << 16)]
            )
        sections.append(entry)
    return sections


def _vaddr_to_offset(segments: list[dict[str, Any]], vaddr: int) -> int | None:
    for seg in segments:
        raw = seg["_raw"]
        if raw["type"] == PT_LOAD and raw["vaddr"] <= vaddr < raw["vaddr"] + raw["filesz"]:
            return int(raw["offset"] + (vaddr - raw["vaddr"]))
    return None


def _parse_dynamic(
    view: ByteView,
    is64: bool,
    segments: list[dict[str, Any]],
    sections: list[dict[str, Any]],
    limitations: list[str],
) -> dict[str, Any]:
    info: dict[str, Any] = {
        "needed": [], "soname": None, "rpath": None, "runpath": None,
        "bindNow": False, "pieFlag": False, "present": False,
    }
    dyn_section = next((s for s in sections if s["type"] == SHT_DYNAMIC), None)
    if dyn_section is not None:
        dyn_offset, dyn_size = dyn_section["offset"], dyn_section["size"]
    else:
        dyn_seg = next((s for s in segments if s["_raw"]["type"] == PT_DYNAMIC), None)
        if dyn_seg is None:
            return info
        dyn_offset, dyn_size = dyn_seg["_raw"]["offset"], dyn_seg["_raw"]["filesz"]
    info["present"] = True

    entry_size = 16 if is64 else 8
    entries: list[tuple[int, int]] = []
    for index in range(min(dyn_size // entry_size, 4096)):
        try:
            tag, value = view.unpack("qQ" if is64 else "iI", dyn_offset + index * entry_size)
        except BinaryFormatError as exc:
            limitations.append(f"dynamic section truncated: {exc}")
            break
        if tag == DT_NULL:
            break
        entries.append((tag, value))

    # Prefer the string table linked from the .dynamic section header; fall back
    # to DT_STRTAB (a virtual address) for binaries without section headers.
    strtab: int | None = None
    if dyn_section is not None and 0 <= dyn_section["_link"] < len(sections):
        strtab = sections[dyn_section["_link"]]["offset"]
    if strtab is None:
        strtab_vaddr = next((v for t, v in entries if t == DT_STRTAB), None)
        if strtab_vaddr is not None:
            strtab = _vaddr_to_offset(segments, strtab_vaddr)
    if strtab is None:
        limitations.append("dynamic string table not found; library names unavailable")

    def _name(value: int) -> str | None:
        if strtab is None:
            return None
        try:
            return view.cstring(strtab + value, 512)
        except BinaryFormatError:
            return None

    for tag, value in entries:
        if tag == DT_NEEDED:
            name = _name(value)
            if name:
                info["needed"].append(name)
        elif tag == DT_SONAME:
            info["soname"] = _name(value)
        elif tag == DT_RPATH:
            info["rpath"] = _name(value)
        elif tag == DT_RUNPATH:
            info["runpath"] = _name(value)
        elif tag == DT_BIND_NOW:
            info["bindNow"] = True
        elif tag == DT_FLAGS and value & DF_BIND_NOW:
            info["bindNow"] = True
        elif tag == DT_FLAGS_1:
            if value & DF_1_NOW:
                info["bindNow"] = True
            if value & DF_1_PIE:
                info["pieFlag"] = True
    return info


def _parse_symbols(
    view: ByteView, is64: bool, sections: list[dict[str, Any]], limitations: list[str]
) -> dict[str, Any]:
    imported: list[str] = []
    exported: list[str] = []
    seen_imported: set[str] = set()
    seen_exported: set[str] = set()
    # .dynsym is what the dynamic linker sees; fall back to .symtab for static binaries.
    table = next((s for s in sections if s["type"] == SHT_DYNSYM), None) or next(
        (s for s in sections if s["type"] == SHT_SYMTAB), None
    )
    if table is None or not (0 <= table["_link"] < len(sections)):
        return {"imported": [], "exported": [], "importedCount": 0, "exportedCount": 0}
    strtab = sections[table["_link"]]["offset"]
    entsize = table["_entsize"] or (24 if is64 else 16)
    count = min(table["size"] // entsize, MAX_SYMBOLS)
    if table["size"] // entsize > MAX_SYMBOLS:
        limitations.append(f"symbol table capped at {MAX_SYMBOLS} entries")
    for index in range(1, count):
        offset = table["offset"] + index * entsize
        try:
            if is64:
                st_name, st_info, _other, st_shndx, _value, _size = view.unpack("IBBHQQ", offset)
            else:
                st_name, _value, _size, st_info, _other, st_shndx = view.unpack("IIIBBH", offset)
        except BinaryFormatError as exc:
            limitations.append(f"symbol table truncated: {exc}")
            break
        bind, sym_type = st_info >> 4, st_info & 0xF
        if bind not in (STB_GLOBAL, STB_WEAK) or not st_name:
            continue
        try:
            name = view.cstring(strtab + st_name, 512)
        except BinaryFormatError:
            continue
        if not name:
            continue
        if st_shndx == SHN_UNDEF:
            if name not in seen_imported:
                seen_imported.add(name)
                imported.append(name)
        elif sym_type in (STT_FUNC, STT_OBJECT, STT_GNU_IFUNC) and name not in seen_exported:
            seen_exported.add(name)
            exported.append(name)
    return {
        "imported": sorted(imported)[:2000],
        "exported": sorted(exported)[:2000],
        "importedCount": len(imported),
        "exportedCount": len(exported),
    }


def _hardening(
    e_type: int,
    segments: list[dict[str, Any]],
    dynamic: dict[str, Any],
    imported: set[str],
    section_names: set[str],
) -> dict[str, Any]:
    stack = next((s for s in segments if s["_raw"]["type"] == PT_GNU_STACK), None)
    # No PT_GNU_STACK means the loader defaults to an executable stack on most arches.
    nx = stack is not None and not (stack["_raw"]["flags"] & PF_X)
    has_relro = any(s["_raw"]["type"] == PT_GNU_RELRO for s in segments)
    if not has_relro:
        relro = "none"
    elif dynamic["bindNow"]:
        relro = "full"
    else:
        relro = "partial"
    is_dyn = e_type == 3
    has_interp = any(s["_raw"]["type"] == PT_INTERP for s in segments)
    if is_dyn and (has_interp or dynamic["pieFlag"]):
        pie: str = "yes"
    elif is_dyn:
        pie = "shared-library"
    elif e_type == 2:
        pie = "no"
    else:
        pie = "n/a"
    return {
        "nx": nx,
        "pie": pie,
        "relro": relro,
        "stackCanary": any(name.startswith("__stack_chk_fail") for name in imported),
        "fortifySource": any(name.endswith("_chk") and name.startswith("__") for name in imported),
        "stripped": ".symtab" not in section_names,
        "dynamicallyLinked": dynamic["present"],
        "rpath": dynamic["rpath"] or dynamic["runpath"],
    }


def _guess_language(section_names: set[str], imported: set[str]) -> str | None:
    if ".go.buildinfo" in section_names or ".gopclntab" in section_names:
        return "go"
    if any(name.startswith("_ZN") and "rust" in name for name in imported) or any(
        name.startswith("rust_") for name in imported
    ):
        return "rust"
    if any(name.startswith("_Z") for name in imported):
        return "c++"
    return None
