"""`strings(1)` with classification: the first pass of almost every RE workflow.

Extracts printable ASCII and UTF-16LE runs (the latter is how Windows
binaries store most text), then tags the ones a reverse engineer actually
looks for — URLs, IPs, file paths, registry keys, crypto/library markers,
and secrets — so an agent gets the 30 strings that matter instead of 30,000.
"""

from __future__ import annotations

import bisect
import re
from collections import Counter
from typing import Any, TypedDict

from archmap.core.audit.secrets import scan_text
from archmap.core.binary.reader import ByteSource

MAX_SCAN_BYTES = 128 * 1024 * 1024
MAX_STRING_LENGTH = 1024


class ExtractedString(TypedDict):
    offset: int
    encoding: str
    value: str


class ClassifiedString(TypedDict):
    offset: int
    encoding: str
    value: str
    categories: list[str]


_CATEGORIES: list[tuple[str, re.Pattern[str]]] = [
    ("url", re.compile(r"\b(?:https?|ftp|wss?|file)://[^\s\"'<>]{3,}", re.I)),
    ("ipv4", re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b")),
    ("windows-path", re.compile(r"\b[A-Za-z]:\\[^\s\"'<>|]{2,}")),
    (
        "unix-path",
        re.compile(
            r"(?:^|\s)/(?:usr|etc|bin|sbin|var|tmp|home|opt|lib|proc|dev|system)/\S*"
        ),
    ),
    ("registry-key", re.compile(r"\b(?:HKEY_[A-Z_]+|HKLM|HKCU|HKCR)\\", re.I)),
    (
        "shell-command",
        re.compile(
            r"\b(?:cmd\.exe|powershell|/bin/sh|/bin/bash|wget |curl |chmod \+x)", re.I
        ),
    ),
    (
        "crypto",
        re.compile(
            r"\b(?:AES|RSA|SHA-?(?:1|256|512)|MD5|ChaCha20|Salsa20|RC4|Blowfish|X25519|ECDSA|HMAC)\b"
        ),
    ),
    ("library", re.compile(r"\b[\w.+-]+\.(?:dll|so(?:\.\d+)*|dylib)\b", re.I)),
    (
        "build-toolchain",
        re.compile(
            r"\b(?:GCC: \(|clang version|rustc version|Go build ID|go1\.\d+|MSVC|mingw)", re.I
        ),
    ),
    (
        "format-string",
        re.compile(
            r"%(?:\d+\$)?[-+ #0]*\d*(?:\.\d+)?(?:hh|h|ll|l|z|j|t)?[diouxXsScpn]"
        ),
    ),
]
# Categories considered "interesting" enough to surface individually.
_INTERESTING = {
    "url",
    "ipv4",
    "email",
    "windows-path",
    "unix-path",
    "registry-key",
    "shell-command",
    "crypto",
    "build-toolchain",
    "secret",
}

_ASCII_RUN = "[\x20-\x7e\t]{%d,%d}"
_UTF16_RUN = "(?:[\x20-\x7e\t]\x00){%d,%d}"


def extract_strings(
    data: ByteSource,
    min_length: int = 4,
    encodings: tuple[str, ...] = ("ascii", "utf16le"),
    limit: int = 50_000,
) -> list[ExtractedString]:
    """Return printable strings in file order (ASCII first, then UTF-16LE)."""
    min_length = max(2, min_length)
    # finditer's endpos bounds the scan without copying an mmap into memory.
    end = min(len(data), MAX_SCAN_BYTES)
    results: list[ExtractedString] = []
    if "ascii" in encodings:
        pattern = re.compile((_ASCII_RUN % (min_length, MAX_STRING_LENGTH)).encode("latin-1"))
        for found in pattern.finditer(data, 0, end):
            results.append({
                "offset": found.start(),
                "encoding": "ascii",
                "value": found.group().decode("ascii"),
            })
            if len(results) >= limit:
                return results
    if "utf16le" in encodings:
        # The last char of an ASCII string plus its NUL terminator looks like one
        # UTF-16 code unit ("d\x00"), so a UTF-16 run may start inside an ASCII
        # string. Advance such starts past the ASCII span (`strings -el` doesn't).
        ascii_starts = [r["offset"] for r in results]
        ascii_ends = [r["offset"] + len(r["value"]) for r in results]
        pattern = re.compile((_UTF16_RUN % (min_length, MAX_STRING_LENGTH)).encode("latin-1"))
        for found in pattern.finditer(data, 0, end):
            start = found.start()
            index = bisect.bisect_right(ascii_starts, start) - 1
            while index >= 0 and start < ascii_ends[index] and start < found.end():
                start += 2
            if (found.end() - start) // 2 < min_length:
                continue
            results.append({
                "offset": start,
                "encoding": "utf16le",
                "value": bytes(data[start : found.end()]).decode("utf-16-le"),
            })
            if len(results) >= limit:
                break
    return results


def classify_string(value: str) -> list[str]:
    categories = [name for name, pattern in _CATEGORIES if pattern.search(value)]
    if scan_text(value, max_matches=1):
        categories.append("secret")
    return categories


def analyze_strings(
    data: ByteSource,
    min_length: int = 4,
    max_interesting: int = 200,
) -> dict[str, Any]:
    """Extract, classify, and summarise strings. Secret values come back redacted."""
    extracted = extract_strings(data, min_length=min_length)
    by_category: Counter[str] = Counter()
    interesting: list[ClassifiedString] = []
    seen_values: set[str] = set()
    secrets: list[dict[str, object]] = []

    for item in extracted:
        categories = classify_string(item["value"])
        by_category.update(categories)
        if not categories or not _INTERESTING.intersection(categories):
            continue
        value = item["value"]
        if "secret" in categories:
            for match in scan_text(value, max_matches=5):
                secrets.append({**match, "offset": item["offset"], "encoding": item["encoding"]})
            value = "[redacted secret]"
        if value in seen_values or len(interesting) >= max_interesting:
            continue
        seen_values.add(value)
        interesting.append({
            "offset": item["offset"],
            "encoding": item["encoding"],
            "value": value[:256],
            "categories": categories,
        })

    return {
        "total": len(extracted),
        "truncated": len(data) > MAX_SCAN_BYTES,
        "byCategory": dict(sorted(by_category.items())),
        "interesting": interesting,
        "secrets": secrets[:50],
    }
