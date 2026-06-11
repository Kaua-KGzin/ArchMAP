"""Shared text-preprocessing helpers for the regex parser fallbacks.

The regex fallbacks (used when the optional tree-sitter extra is not installed)
historically matched import-like text inside comments, which produced false
dependencies. ``strip_comments`` removes comments while staying inside string
literals, so genuine specifiers embedded in strings (``require("x")``,
``#include "x"``) are preserved. Newlines are kept intact so that
``re.MULTILINE`` anchors keep working on the cleaned source.
"""
from __future__ import annotations

from collections.abc import Sequence


def strip_comments(
    source: str,
    *,
    line_comments: Sequence[str] = ("//",),
    block_comments: Sequence[tuple[str, str]] = (("/*", "*/"),),
    string_delims: Sequence[str] = ('"', "'"),
) -> str:
    """Return ``source`` with comments blanked out (replaced by spaces).

    Comment characters are replaced with spaces rather than removed so that
    byte offsets and, more importantly, line counts are preserved. The scanner
    is string-aware: ``//`` inside ``"http://..."`` is not treated as a comment.
    """
    out: list[str] = []
    i = 0
    n = len(source)
    active_string: str | None = None

    while i < n:
        ch = source[i]

        if active_string is not None:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(source[i + 1])
                i += 2
                continue
            if ch == active_string:
                active_string = None
            i += 1
            continue

        # Entering a string literal
        if ch in string_delims:
            active_string = ch
            out.append(ch)
            i += 1
            continue

        # Block comments
        matched_block = False
        for opener, closer in block_comments:
            if source.startswith(opener, i):
                end = source.find(closer, i + len(opener))
                if end == -1:
                    end = n
                else:
                    end += len(closer)
                for j in range(i, end):
                    out.append("\n" if source[j] == "\n" else " ")
                i = end
                matched_block = True
                break
        if matched_block:
            continue

        # Line comments
        matched_line = False
        for marker in line_comments:
            if source.startswith(marker, i):
                while i < n and source[i] != "\n":
                    out.append(" ")
                    i += 1
                matched_line = True
                break
        if matched_line:
            continue

        out.append(ch)
        i += 1

    return "".join(out)
