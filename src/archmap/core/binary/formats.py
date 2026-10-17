"""File-format identification by magic bytes (libmagic-style, stdlib only)."""

from __future__ import annotations

import io
import struct
import zipfile
from typing import Any, TypedDict

from archmap.core.binary.reader import ByteSource


class FormatInfo(TypedDict):
    format: str
    description: str
    category: str


# (offset, magic, format id, description, category). Checked in order; the
# first match wins, so more specific signatures come before generic ones.
_SIGNATURES: list[tuple[int, bytes, str, str, str]] = [
    (0, b"\x7fELF", "elf", "ELF executable/library", "executable"),
    (0, b"\xfe\xed\xfa\xce", "macho", "Mach-O 32-bit (big-endian)", "executable"),
    (0, b"\xce\xfa\xed\xfe", "macho", "Mach-O 32-bit", "executable"),
    (0, b"\xfe\xed\xfa\xcf", "macho", "Mach-O 64-bit (big-endian)", "executable"),
    (0, b"\xcf\xfa\xed\xfe", "macho", "Mach-O 64-bit", "executable"),
    (0, b"\x00asm", "wasm", "WebAssembly module", "bytecode"),
    (0, b"dex\n", "dex", "Android Dalvik executable", "bytecode"),
    (0, b"SQLite format 3\x00", "sqlite", "SQLite 3 database", "database"),
    (0, b"%PDF-", "pdf", "PDF document", "document"),
    (0, b"\x89PNG\r\n\x1a\n", "png", "PNG image", "image"),
    (0, b"\xff\xd8\xff", "jpeg", "JPEG image", "image"),
    (0, b"GIF87a", "gif", "GIF image", "image"),
    (0, b"GIF89a", "gif", "GIF image", "image"),
    (0, b"\x1f\x8b", "gzip", "gzip compressed data", "compressed"),
    (0, b"BZh", "bzip2", "bzip2 compressed data", "compressed"),
    (0, b"\xfd7zXZ\x00", "xz", "xz compressed data", "compressed"),
    (0, b"\x28\xb5\x2f\xfd", "zstd", "Zstandard compressed data", "compressed"),
    (0, b"7z\xbc\xaf\x27\x1c", "7z", "7-Zip archive", "archive"),
    (0, b"Rar!\x1a\x07", "rar", "RAR archive", "archive"),
    (0, b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "ole", "OLE2 compound document", "document"),
    (0, b"\xd4\xc3\xb2\xa1", "pcap", "pcap capture (little-endian)", "capture"),
    (0, b"\xa1\xb2\xc3\xd4", "pcap", "pcap capture (big-endian)", "capture"),
    (0, b"\x0a\x0d\x0d\x0a", "pcapng", "pcapng capture", "capture"),
    (0, b"BC\xc0\xde", "llvm-bc", "LLVM bitcode", "bytecode"),
    (0, b"\x1bLua", "lua-bytecode", "Lua bytecode", "bytecode"),
    (0, b"PK\x03\x04", "zip", "ZIP archive", "archive"),
    (0, b"PK\x05\x06", "zip", "ZIP archive (empty)", "archive"),
    (257, b"ustar", "tar", "tar archive", "archive"),
    (0, b"#!", "script", "Script with shebang", "text"),
]

# Mach-O universal binaries and Java class files share 0xCAFEBABE; the next
# word is the arch count for the former (tiny) and the class version for the
# latter (major version >= 45).
_CAFEBABE = b"\xca\xfe\xba\xbe"

_ZIP_FLAVOURS: list[tuple[str, str, str]] = [
    ("AndroidManifest.xml", "apk", "Android application package (APK)"),
    ("word/document.xml", "docx", "Word document (OOXML)"),
    ("xl/workbook.xml", "xlsx", "Excel workbook (OOXML)"),
    ("ppt/presentation.xml", "pptx", "PowerPoint presentation (OOXML)"),
    ("META-INF/MANIFEST.MF", "jar", "Java archive (JAR)"),
]


def detect_format(data: ByteSource, name: str = "") -> FormatInfo:
    """Identify ``data`` by its magic bytes, falling back to text heuristics."""
    head = bytes(data[:512])

    if head.startswith(_CAFEBABE) and len(head) >= 8:
        (second,) = struct.unpack(">I", head[4:8])
        if second < 45:
            return {
                "format": "macho-fat",
                "description": "Mach-O universal binary",
                "category": "executable",
            }
        major = second & 0xFFFF
        return {
            "format": "java-class",
            "description": f"Java class file (class version {major}, Java {major - 44})",
            "category": "bytecode",
        }

    if head.startswith(b"MZ"):
        return _detect_mz(data)

    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return {"format": "webp", "description": "WebP image", "category": "image"}
    if head[4:8] == b"ftyp":
        return {"format": "mp4", "description": "ISO media (MP4/MOV)", "category": "media"}

    for offset, magic, fmt, description, category in _SIGNATURES:
        if head[offset : offset + len(magic)] == magic:
            if fmt == "zip":
                return _refine_zip(data, description)
            return {"format": fmt, "description": description, "category": category}

    if name.lower().endswith(".pyc") and head[2:4] == b"\r\n":
        (magic_number,) = struct.unpack("<H", head[:2])
        return {
            "format": "pyc",
            "description": f"Python bytecode (magic {magic_number})",
            "category": "bytecode",
        }

    return _detect_text(head, name)


def _detect_mz(data: ByteSource) -> FormatInfo:
    head = bytes(data[:0x40])
    if len(head) >= 0x40:
        (pe_offset,) = struct.unpack("<I", head[0x3C:0x40])
        signature = bytes(data[pe_offset : pe_offset + 4]) if pe_offset > 0 else b""
        if signature == b"PE\x00\x00":
            return {
                "format": "pe",
                "description": "PE executable/DLL (Windows)",
                "category": "executable",
            }
    return {"format": "mz", "description": "MS-DOS executable", "category": "executable"}


def _refine_zip(data: ByteSource, description: str) -> FormatInfo:
    # An mmap is already seekable/file-like; only plain bytes need wrapping.
    handle: Any = io.BytesIO(data) if isinstance(data, bytes) else data
    try:
        with zipfile.ZipFile(handle) as archive:
            names = set(archive.namelist())
    except (zipfile.BadZipFile, OSError, ValueError):
        return {"format": "zip", "description": description, "category": "archive"}
    for marker, fmt, flavour in _ZIP_FLAVOURS:
        if marker in names:
            return {"format": fmt, "description": flavour, "category": "archive"}
    return {"format": "zip", "description": description, "category": "archive"}


def _detect_text(head: bytes, name: str) -> FormatInfo:
    if not head:
        return {"format": "empty", "description": "Empty file", "category": "data"}
    if b"\x00" in head:
        return {"format": "data", "description": "Unknown binary data", "category": "data"}
    try:
        text = head.decode("utf-8")
    except UnicodeDecodeError:
        # A multi-byte character may be cut at the 512-byte boundary.
        try:
            text = head[:-3].decode("utf-8")
        except UnicodeDecodeError:
            return {"format": "data", "description": "Unknown binary data", "category": "data"}
    stripped = text.lstrip("﻿ \t\r\n")
    lower = name.lower()
    if stripped.startswith(("{", "[")) or lower.endswith((".json", ".jsonl", ".ndjson")):
        return {"format": "json", "description": "JSON text", "category": "text"}
    if lower.endswith((".csv", ".tsv")):
        return {"format": "csv", "description": "Delimited text (CSV/TSV)", "category": "text"}
    if stripped.startswith("<?xml") or stripped.startswith("<"):
        return {"format": "xml", "description": "XML/HTML markup", "category": "text"}
    return {"format": "text", "description": "UTF-8 text", "category": "text"}
