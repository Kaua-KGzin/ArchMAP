"""Canonical hexdump (``hexdump -C`` / ``xxd`` layout) over a byte range."""

from __future__ import annotations

from archmap.core.binary.reader import ByteSource

MAX_HEXDUMP_BYTES = 64 * 1024


def hexdump(
    data: ByteSource,
    offset: int = 0,
    length: int = 256,
    width: int = 16,
) -> str:
    """Render ``length`` bytes starting at ``offset``.

    Negative offsets count from the end of the data (``-64`` dumps the last 64
    bytes), which is how trailers, overlays, and appended payloads are usually
    inspected. Output is capped at :data:`MAX_HEXDUMP_BYTES`.
    """
    size = len(data)
    if offset < 0:
        offset = max(0, size + offset)
    offset = min(offset, size)
    length = max(0, min(length, MAX_HEXDUMP_BYTES, size - offset))
    width = max(1, min(width, 64))
    chunk = bytes(data[offset : offset + length])

    lines: list[str] = []
    for start in range(0, len(chunk), width):
        row = chunk[start : start + width]
        if width >= 8:
            # Split the row in two halves like `hexdump -C`.
            half = width // 2
            left = " ".join(f"{b:02x}" for b in row[:half])
            right = " ".join(f"{b:02x}" for b in row[half:])
            hex_part = f"{left}  {right}" if right else left
        else:
            hex_part = " ".join(f"{b:02x}" for b in row)
        pad = width * 3 + (1 if width >= 8 else 0)
        ascii_part = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in row)
        lines.append(f"{offset + start:08x}  {hex_part:<{pad}} |{ascii_part}|")
    lines.append(f"{offset + len(chunk):08x}")
    return "\n".join(lines)
