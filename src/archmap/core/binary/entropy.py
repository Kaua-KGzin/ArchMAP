"""Shannon entropy — the cheapest signal for packed, compressed, or encrypted data.

Byte histograms are the expensive part (``collections.Counter`` runs at
roughly 25 MB/s), so large inputs are sampled: each block contributes at
most :data:`SAMPLE_BYTES` contiguous bytes, and the overall figure is
derived from the summed block histograms instead of a second full pass.
64 KiB of contiguous data is plenty to tell code (~6 bits/byte) from
compressed or encrypted payloads (~8 bits/byte).
"""

from __future__ import annotations

import math
from collections import Counter

from archmap.core.binary.reader import ByteSource

SAMPLE_BYTES = 64 * 1024
HIGH_ENTROPY = 7.2
LOW_ENTROPY = 1.0


def _histogram(data: bytes) -> Counter[int]:
    return Counter(data)


def _entropy(counts: Counter[int], length: int) -> float:
    if not length:
        return 0.0
    entropy = 0.0
    for count in counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return round(entropy, 4)


def shannon_entropy(data: bytes | memoryview, max_bytes: int = SAMPLE_BYTES) -> float:
    """Bits of entropy per byte, 0.0 (constant) to 8.0 (uniformly random).

    Only the first ``max_bytes`` are measured; pass ``0`` to measure everything.
    """
    sample = bytes(data[:max_bytes]) if max_bytes else bytes(data)
    return _entropy(_histogram(sample), len(sample))


def classify_entropy(value: float) -> str:
    if value >= HIGH_ENTROPY:
        return "high: compressed, encrypted, or packed"
    if value <= LOW_ENTROPY:
        return "low: padding or sparse"
    return "normal"


def entropy_profile(
    data: ByteSource, blocks: int = 64, sample_bytes: int = SAMPLE_BYTES
) -> dict[str, object]:
    """Overall entropy plus a coarse per-block profile for spotting embedded payloads.

    The block profile is what a reverse engineer eyeballs in a tool like
    binwalk: a flat ~6 bits/byte code region followed by a 7.9 plateau is an
    appended compressed or encrypted blob.
    """
    size = len(data)
    block_size = max(256, -(-size // max(1, blocks))) if size else 0
    total: Counter[int] = Counter()
    measured = 0
    profile: list[dict[str, float | int]] = []
    for offset in range(0, size, block_size or 1):
        chunk = bytes(data[offset : offset + min(block_size, sample_bytes)])
        counts = _histogram(chunk)
        total.update(counts)
        measured += len(chunk)
        profile.append({"offset": offset, "entropy": _entropy(counts, len(chunk))})
    overall = _entropy(total, measured)
    return {
        "overall": overall,
        "classification": classify_entropy(overall),
        "sampled": measured < size,
        "bytesMeasured": measured,
        "blockSize": block_size,
        "profile": profile,
        "highEntropyBlocks": sum(1 for p in profile if float(p["entropy"]) >= HIGH_ENTROPY),
    }
