"""Bounds-checked access to untrusted binary data.

Every format parser in this package reads attacker-controlled bytes, so all
offsets go through :class:`ByteView`, which raises :class:`BinaryFormatError`
instead of ``struct.error``/``IndexError`` and caps how much a single
structure may claim. Parsers catch that one exception type and record a
limitation, so a truncated or malicious file degrades the report instead of
crashing the tool.
"""

from __future__ import annotations

import contextlib
import hashlib
import mmap
import struct
from collections.abc import Iterator
from pathlib import Path

ByteSource = bytes | mmap.mmap

# Hard caps that keep a hostile header from driving huge loops or allocations.
MAX_SECTIONS = 1024
MAX_SYMBOLS = 20_000
MAX_IMPORTS = 10_000
MAX_CSTRING = 4096


class BinaryFormatError(ValueError):
    """Raised when a binary structure points outside the file or is malformed."""


class ByteView:
    """Little helper around ``struct.unpack_from`` with explicit bounds checks."""

    def __init__(self, data: ByteSource, little_endian: bool = True) -> None:
        self.data = data
        self.size = len(data)
        self.prefix = "<" if little_endian else ">"

    def check(self, offset: int, length: int) -> None:
        if offset < 0 or length < 0 or offset + length > self.size:
            raise BinaryFormatError(
                f"read of {length} bytes at offset {offset:#x} is outside the file "
                f"({self.size} bytes)"
            )

    def unpack(self, fmt: str, offset: int) -> tuple[int, ...]:
        full = self.prefix + fmt
        self.check(offset, struct.calcsize(full))
        return struct.unpack_from(full, self.data, offset)

    def u8(self, offset: int) -> int:
        return self.unpack("B", offset)[0]

    def u16(self, offset: int) -> int:
        return self.unpack("H", offset)[0]

    def u32(self, offset: int) -> int:
        return self.unpack("I", offset)[0]

    def u64(self, offset: int) -> int:
        return self.unpack("Q", offset)[0]

    def bytes_at(self, offset: int, length: int) -> bytes:
        self.check(offset, length)
        return bytes(self.data[offset : offset + length])

    def cstring(self, offset: int, limit: int = MAX_CSTRING) -> str:
        """Read a NUL-terminated string (decoded leniently) starting at ``offset``."""
        self.check(offset, 1)
        end = min(self.size, offset + limit)
        raw = bytes(self.data[offset:end])
        nul = raw.find(b"\x00")
        if nul >= 0:
            raw = raw[:nul]
        return raw.decode("utf-8", errors="replace")


@contextlib.contextmanager
def open_binary(path: str | Path) -> Iterator[ByteSource]:
    """Yield the file's bytes, memory-mapped when possible.

    Memory mapping keeps large binaries (firmware, game assets) out of the
    Python heap; empty files and platforms without mmap fall back to a plain
    read.
    """
    file_path = Path(path)
    with file_path.open("rb") as handle:
        if file_path.stat().st_size == 0:
            yield b""
            return
        try:
            mapped = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
        except (OSError, ValueError):
            yield handle.read()
            return
        try:
            yield mapped
        finally:
            mapped.close()


def file_hashes(data: ByteSource) -> dict[str, str]:
    """MD5/SHA-1/SHA-256 — the identifiers threat-intel and malware databases key on."""
    hashes = {
        # md5/sha1 identify samples, they don't protect anything.
        "md5": hashlib.md5(usedforsecurity=False),
        "sha1": hashlib.sha1(usedforsecurity=False),
        "sha256": hashlib.sha256(),
    }
    view = memoryview(data)
    try:
        chunk = 1 << 20
        for start in range(0, len(view), chunk):
            with view[start : start + chunk] as piece:
                for digest in hashes.values():
                    digest.update(piece)
    finally:
        # An mmap can't be closed while a memoryview still exports its buffer.
        view.release()
    return {name: digest.hexdigest() for name, digest in hashes.items()}
