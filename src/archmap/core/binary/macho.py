"""Mach-O parser (macOS/iOS): thin and universal binaries, dylibs, segments, hardening."""

from __future__ import annotations

from typing import Any

from archmap.core.binary.entropy import shannon_entropy
from archmap.core.binary.reader import MAX_SECTIONS, BinaryFormatError, ByteSource, ByteView

_CPU_ARCH_ABI64 = 0x01000000
_CPUS = {
    7: "x86",
    7 | _CPU_ARCH_ABI64: "x86-64",
    12: "ARM",
    12 | _CPU_ARCH_ABI64: "ARM64",
    12 | 0x02000000: "ARM64_32",
    18: "PowerPC",
    18 | _CPU_ARCH_ABI64: "PowerPC64",
}
_FILETYPES = {
    1: "object",
    2: "executable",
    3: "fixed VM library",
    4: "core",
    5: "preload",
    6: "dylib",
    7: "dylinker",
    8: "bundle",
    9: "dylib stub",
    10: "dSYM companion",
    11: "kext bundle",
}
LC_SEGMENT, LC_SEGMENT_64 = 0x1, 0x19
LC_LOAD_DYLIB, LC_ID_DYLIB = 0xC, 0xD
LC_LOAD_WEAK_DYLIB, LC_REEXPORT_DYLIB, LC_LAZY_LOAD_DYLIB = 0x80000018, 0x8000001F, 0x20
LC_RPATH, LC_MAIN, LC_CODE_SIGNATURE = 0x8000001C, 0x80000028, 0x1D
LC_ENCRYPTION_INFO, LC_ENCRYPTION_INFO_64 = 0x21, 0x2C
MH_PIE, MH_ALLOW_STACK_EXECUTION, MH_NO_HEAP_EXECUTION = 0x200000, 0x20000, 0x1000000
_MAX_FAT_ARCHS = 8


def parse_macho(data: ByteSource) -> dict[str, Any]:
    """Parse a thin or universal (fat) Mach-O file."""
    head = bytes(data[:4])
    if head == b"\xca\xfe\xba\xbe":
        return _parse_fat(data)
    return _parse_thin(data, 0)


def _parse_fat(data: ByteSource) -> dict[str, Any]:
    view = ByteView(data, little_endian=False)
    count = view.u32(4)
    archs: list[dict[str, Any]] = []
    limitations: list[str] = []
    for index in range(min(count, _MAX_FAT_ARCHS)):
        cputype, _sub, offset, size, _align = view.unpack("IIIII", 8 + index * 20)
        entry: dict[str, Any] = {
            "cpu": _CPUS.get(cputype, hex(cputype)),
            "offset": offset,
            "size": size,
        }
        try:
            entry["image"] = _parse_thin(data, offset)
        except BinaryFormatError as exc:
            limitations.append(f"slice {index}: {exc}")
        archs.append(entry)
    return {"universal": True, "architectures": archs, "limitations": limitations}


def _parse_thin(data: ByteSource, base: int) -> dict[str, Any]:
    magic = bytes(data[base : base + 4])
    if magic in (b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf"):
        little = False
    elif magic in (b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe"):
        little = True
    else:
        raise BinaryFormatError("not a Mach-O image")
    is64 = magic in (b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe")
    view = ByteView(data, little_endian=little)
    cputype, _sub, filetype, ncmds, _sizeofcmds, flags = view.unpack("IIIIII", base + 4)
    cursor = base + (32 if is64 else 28)
    limitations: list[str] = []

    dylibs: list[dict[str, str]] = []
    rpaths: list[str] = []
    segments: list[dict[str, Any]] = []
    install_name: str | None = None
    has_main = False
    signed = False
    encrypted = False

    for _ in range(min(ncmds, MAX_SECTIONS)):
        try:
            cmd, cmdsize = view.unpack("II", cursor)
        except BinaryFormatError as exc:
            limitations.append(f"load commands truncated: {exc}")
            break
        if cmdsize < 8:
            limitations.append("malformed load command size")
            break
        try:
            if cmd in (LC_LOAD_DYLIB, LC_LOAD_WEAK_DYLIB, LC_REEXPORT_DYLIB, LC_LAZY_LOAD_DYLIB):
                name = view.cstring(cursor + view.u32(cursor + 8), 512)
                kind = {
                    LC_LOAD_WEAK_DYLIB: "weak",
                    LC_REEXPORT_DYLIB: "reexport",
                    LC_LAZY_LOAD_DYLIB: "lazy",
                }.get(cmd, "load")
                dylibs.append({"name": name, "kind": kind})
            elif cmd == LC_ID_DYLIB:
                install_name = view.cstring(cursor + view.u32(cursor + 8), 512)
            elif cmd == LC_RPATH:
                rpaths.append(view.cstring(cursor + view.u32(cursor + 8), 512))
            elif cmd == LC_MAIN:
                has_main = True
            elif cmd == LC_CODE_SIGNATURE:
                signed = True
            elif cmd in (LC_ENCRYPTION_INFO, LC_ENCRYPTION_INFO_64):
                encrypted = view.u32(cursor + 16) != 0
            elif cmd in (LC_SEGMENT, LC_SEGMENT_64):
                segments.append(_segment(view, cursor, cmd == LC_SEGMENT_64, base))
        except BinaryFormatError as exc:
            limitations.append(f"load command {cmd:#x}: {exc}")
        cursor += cmdsize

    return {
        "universal": False,
        "class": "Mach-O 64" if is64 else "Mach-O 32",
        "endianness": "little" if little else "big",
        "cpu": _CPUS.get(cputype, hex(cputype)),
        "fileType": _FILETYPES.get(filetype, f"unknown ({filetype})"),
        "installName": install_name,
        "linkedLibraries": dylibs,
        "rpaths": rpaths,
        "segments": segments,
        "hasMain": has_main,
        "hardening": {
            "pie": bool(flags & MH_PIE),
            "stackExecutable": bool(flags & MH_ALLOW_STACK_EXECUTION),
            "heapNonExecutable": bool(flags & MH_NO_HEAP_EXECUTION),
            "codeSignature": signed,
            "encrypted": encrypted,
        },
        "limitations": limitations,
    }


def _segment(view: ByteView, cursor: int, is64: bool, base: int) -> dict[str, Any]:
    name = view.bytes_at(cursor + 8, 16).rstrip(b"\x00").decode("utf-8", errors="replace")
    if is64:
        vmaddr, vmsize, fileoff, filesize, _maxprot, initprot, nsects, _flags = view.unpack(
            "QQQQiiII", cursor + 24
        )
    else:
        vmaddr, vmsize, fileoff, filesize, _maxprot, initprot, nsects, _flags = view.unpack(
            "IIIIiiII", cursor + 24
        )
    prot = "".join(flag if initprot & bit else "-" for flag, bit in (("R", 1), ("W", 2), ("X", 4)))
    entry: dict[str, Any] = {
        "name": name,
        "vmAddress": hex(vmaddr),
        "vmSize": vmsize,
        "fileOffset": fileoff,
        "fileSize": filesize,
        "protection": prot,
        "sectionCount": nsects,
    }
    start = base + fileoff
    if filesize and start + filesize <= view.size:
        entry["entropy"] = shannon_entropy(
            view.data[start : start + min(filesize, 1 << 16)]
        )
    return entry
