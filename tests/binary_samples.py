"""Builders for minimal, valid ELF/PE/Mach-O/WASM images used by the binary tests.

Real binaries differ across CI runners (Linux ELF, macOS Mach-O, Windows PE),
so the tests assemble small images by hand. Each builder exposes the flags
the hardening checks look at, so every mitigation can be toggled in isolation.
"""

from __future__ import annotations

import struct


def build_elf(
    *,
    e_type: int = 3,
    interp: bool = True,
    stack_exec: bool = False,
    gnu_stack: bool = True,
    relro: bool = True,
    bind_now: bool = True,
    needed: tuple[str, ...] = ("libc.so.6",),
    imports: tuple[str, ...] = ("__stack_chk_fail", "__printf_chk", "puts"),
    exports: tuple[str, ...] = ("main",),
    runpath: str | None = None,
    soname: str | None = None,
) -> bytes:
    """ELF64 little-endian x86-64 with .dynstr/.dynsym/.dynamic and section headers."""
    interp_bytes = b"/lib64/ld-linux-x86-64.so.2\x00"

    dynstr = bytearray(b"\x00")

    def add_str(value: str) -> int:
        offset = len(dynstr)
        dynstr.extend(value.encode() + b"\x00")
        return offset

    needed_offsets = [add_str(name) for name in needed]
    runpath_offset = add_str(runpath) if runpath else None
    soname_offset = add_str(soname) if soname else None
    import_offsets = [add_str(name) for name in imports]
    export_offsets = [add_str(name) for name in exports]

    dynsym = bytearray(b"\x00" * 24)
    for offset in import_offsets:
        dynsym += struct.pack("<IBBHQQ", offset, (1 << 4) | 2, 0, 0, 0, 0)
    for offset in export_offsets:
        dynsym += struct.pack("<IBBHQQ", offset, (1 << 4) | 2, 0, 1, 0x1000, 16)

    dynamic = bytearray()
    for offset in needed_offsets:
        dynamic += struct.pack("<qQ", 1, offset)
    if soname_offset is not None:
        dynamic += struct.pack("<qQ", 14, soname_offset)
    if runpath_offset is not None:
        dynamic += struct.pack("<qQ", 29, runpath_offset)
    if bind_now:
        dynamic += struct.pack("<qQ", 30, 0x8)
    dynamic += struct.pack("<qQ", 0, 0)

    shstrtab = b"\x00.shstrtab\x00.dynstr\x00.dynsym\x00.dynamic\x00"
    name_offsets = {".shstrtab": 1, ".dynstr": 11, ".dynsym": 19, ".dynamic": 27}

    phdrs: list[tuple[int, int]] = []  # (type, flags) — offsets patched below
    if interp:
        phdrs.append((3, 4))
    if gnu_stack:
        phdrs.append((0x6474E551, 7 if stack_exec else 6))
    if relro:
        phdrs.append((0x6474E552, 4))
    phdrs.append((2, 6))  # PT_DYNAMIC
    phdrs.append((1, 5))  # PT_LOAD covering the whole file

    header_size = 64
    ph_size = 56 * len(phdrs)
    cursor = header_size + ph_size
    blobs: dict[str, tuple[int, bytes]] = {}
    for name, blob in (
        ("interp", interp_bytes),
        ("dynstr", bytes(dynstr)),
        ("dynsym", bytes(dynsym)),
        ("dynamic", bytes(dynamic)),
        ("shstrtab", shstrtab),
    ):
        blobs[name] = (cursor, blob)
        cursor += len(blob)
    cursor = (cursor + 7) & ~7
    shoff = cursor
    total = shoff + 64 * 5

    out = bytearray(total)
    struct.pack_into(
        "<4sBBBBB7sHHIQQQIHHHHHH", out, 0,
        b"\x7fELF", 2, 1, 1, 0, 0, b"\x00" * 7,
        e_type, 0x3E, 1, 0x1000, header_size, shoff, 0, 64, 56, len(phdrs), 64, 5, 1,
    )
    for index, (p_type, p_flags) in enumerate(phdrs):
        if p_type == 3:
            offset, size = blobs["interp"][0], len(interp_bytes)
        elif p_type == 2:
            offset, size = blobs["dynamic"][0], len(blobs["dynamic"][1])
        elif p_type == 1:
            offset, size = 0, total
        else:
            offset, size = 0, 0
        struct.pack_into(
            "<IIQQQQQQ", out, header_size + index * 56,
            p_type, p_flags, offset, offset, offset, size, size, 8,
        )
    for offset, blob in blobs.values():
        out[offset : offset + len(blob)] = blob

    def section(index: int, name: str, sh_type: int, key: str, link: int, entsize: int) -> None:
        offset, blob = blobs[key]
        struct.pack_into(
            "<IIQQQQIIQQ", out, shoff + index * 64,
            name_offsets[name], sh_type, 2, offset, offset, len(blob), link, 0, 8, entsize,
        )

    section(1, ".shstrtab", 3, "shstrtab", 0, 0)
    section(2, ".dynstr", 3, "dynstr", 0, 0)
    section(3, ".dynsym", 11, "dynsym", 2, 24)
    section(4, ".dynamic", 6, "dynamic", 2, 16)
    return bytes(out)


def build_pe(
    *,
    dll_characteristics: int = 0x0160 | 0x4000,
    is_dll: bool = False,
    section_names: tuple[str, str] = (".text", ".idata"),
    writable_code: bool = False,
    signed: bool = False,
) -> bytes:
    """PE32+ x86-64 with one import (KERNEL32.dll!CreateFileW + ordinal 7)."""
    out = bytearray(0x600)
    out[0:2] = b"MZ"
    struct.pack_into("<I", out, 0x3C, 0x40)
    out[0x40:0x44] = b"PE\x00\x00"
    characteristics = 0x0022 | (0x2000 if is_dll else 0)
    struct.pack_into("<HHIIIHH", out, 0x44, 0x8664, 2, 1_700_000_000, 0, 0, 240, characteristics)
    opt = 0x58
    struct.pack_into("<H", out, opt, 0x20B)
    struct.pack_into("<I", out, opt + 16, 0x1000)
    struct.pack_into("<Q", out, opt + 24, 0x140000000)
    struct.pack_into("<HH", out, opt + 68, 3, dll_characteristics)
    struct.pack_into("<I", out, opt + 108, 16)
    struct.pack_into("<II", out, opt + 112 + 1 * 8, 0x2000, 40)  # import directory
    if signed:
        struct.pack_into("<II", out, opt + 112 + 4 * 8, 0x500, 0x10)
    table = opt + 240
    text_flags = 0x60000020 | (0x80000000 if writable_code else 0)
    for index, (name, vaddr, raw, flags) in enumerate((
        (section_names[0], 0x1000, 0x200, text_flags),
        (section_names[1], 0x2000, 0x400, 0x40000040),
    )):
        entry = table + index * 40
        out[entry : entry + 8] = name.encode().ljust(8, b"\x00")
        struct.pack_into("<IIII", out, entry + 8, 0x200, vaddr, 0x200, raw)
        struct.pack_into("<I", out, entry + 36, flags)
    out[0x200:0x210] = bytes(range(16))

    idata = 0x400  # file offset of RVA 0x2000
    # Import descriptor: OriginalFirstThunk, ts, fwd, Name, FirstThunk (+ null terminator).
    struct.pack_into("<IIIII", out, idata, 0x2028, 0, 0, 0x2050, 0x2028)
    struct.pack_into("<QQQ", out, idata + 0x28, 0x2060, (1 << 63) | 7, 0)
    out[idata + 0x50 : idata + 0x5D] = b"KERNEL32.dll\x00"
    struct.pack_into("<H", out, idata + 0x60, 0)
    out[idata + 0x62 : idata + 0x6E] = b"CreateFileW\x00"
    return bytes(out)


def build_macho(
    *, pie: bool = True, stack_exec: bool = False, cputype: int = 0x01000007
) -> bytes:
    """Thin 64-bit Mach-O executable: __TEXT segment, libSystem, rpath, LC_MAIN."""
    name = b"/usr/lib/libSystem.B.dylib\x00"
    dylib_size = (24 + len(name) + 7) & ~7
    dylib = struct.pack("<IIIIII", 0xC, dylib_size, 24, 2, 0x10000, 0x10000)
    dylib += name.ljust(dylib_size - 24, b"\x00")
    rpath_name = b"@loader_path/../lib\x00"
    rpath_size = (12 + len(rpath_name) + 7) & ~7
    rpath = struct.pack("<III", 0x8000001C, rpath_size, 12) + rpath_name.ljust(
        rpath_size - 12, b"\x00"
    )
    main = struct.pack("<IIQQ", 0x80000028, 24, 0x1000, 0)
    segment = struct.pack(
        "<II16sQQQQiiII", 0x19, 72, b"__TEXT", 0x100000000, 0x1000, 0, 0, 5, 5, 0, 0
    )
    commands = segment + dylib + rpath + main
    flags = (0x200000 if pie else 0) | (0x20000 if stack_exec else 0)
    header = struct.pack("<IIIIIIII", 0xFEEDFACF, cputype, 3, 2, 4, len(commands), flags, 0)
    image = header + commands
    # Make the segment's file range real so entropy is computed over it.
    # 32-byte header + cmd/cmdsize/segname (24) + vmaddr/vmsize (16) = fileoff at 72.
    image = image[:72] + struct.pack("<QQ", 0, len(image)) + image[88:]
    return image


def build_fat_macho() -> bytes:
    """Universal binary with x86-64 and ARM64 slices."""
    slices = [build_macho(), build_macho(cputype=0x0100000C)]
    header = struct.pack(">II", 0xCAFEBABE, len(slices))
    offset = 0x1000
    table = b""
    body = b""
    for image in slices:
        cputype = struct.unpack("<I", image[4:8])[0]
        table += struct.pack(">IIIII", cputype, 3, offset + len(body), len(image), 12)
        body += image
    return (header + table).ljust(offset, b"\x00") + body


def _leb(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def _wasm_name(value: str) -> bytes:
    raw = value.encode()
    return _leb(len(raw)) + raw


def build_wasm() -> bytes:
    """Module importing wasi fd_write and exporting `_start` and `memory`."""
    imports = _leb(1) + _wasm_name("wasi_snapshot_preview1") + _wasm_name("fd_write") + b"\x00\x00"
    exports = _leb(2) + _wasm_name("_start") + b"\x00" + _leb(1)
    exports += _wasm_name("memory") + b"\x02" + _leb(0)
    producers = _wasm_name("producers") + _leb(1) + _wasm_name("language")
    producers += _leb(1) + _wasm_name("Rust") + _wasm_name("1.80")
    body = b"\x00asm" + struct.pack("<I", 1)
    for section_id, payload in ((2, imports), (3, _leb(1) + _leb(0)), (7, exports), (0, producers)):
        body += bytes([section_id]) + _leb(len(payload)) + payload
    return body
