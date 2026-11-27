"""
ArchMAP perf guard — fails when analysis time regresses.

Two checks on deterministic synthetic projects (no cache):

1. Scaling (machine independent): t(4000 files) / t(1000 files) must stay
   under ``--max-scaling``. Linear growth gives about 4, quadratic about 16, so
   the default of 6 catches an accidental O(n^2) on any hardware.
2. Absolute (needs a same-platform baseline row): the time for ``--files``
   files must stay within ``--max-ratio`` of the matching row in the baseline
   file. With no row measured on this platform the check is skipped, because
   numbers from another machine say nothing about this one.

Usage:
    python scripts/perf_guard.py --baseline benchmarks/baseline.json \
        --files 5000 --shape cycle --max-ratio 2.0

Exit code 0 when every active check passes, 1 on a regression.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

SCALING_SMALL = 1000
SCALING_LARGE = 4000
LANGUAGE = "python"


def measure_seconds(files: int, shape: str) -> float:
    """Best-of-2 wall time of one uncached analysis of a synthetic project."""
    import benchmark

    row = benchmark.run_size(files, LANGUAGE, shape, repeat=2, measure_memory=False)
    return float(row["seconds"])


def _platform_family(name: str) -> str:
    return name.split("-", 1)[0].lower()


def baseline_seconds(baseline: dict[str, Any], files: int, shape: str) -> float | None:
    """Time of the matching row measured on this platform, or ``None``."""
    here = _platform_family(platform.platform())
    for row in baseline.get("rows", []):
        if (row.get("files"), row.get("shape"), row.get("language")) != (files, shape, LANGUAGE):
            continue
        machine = row.get("machine") or baseline.get("machine") or {}
        if _platform_family(str(machine.get("platform", ""))) == here:
            return float(row["seconds"])
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--baseline", default="benchmarks/baseline.json")
    parser.add_argument("--files", type=int, default=5000)
    parser.add_argument("--shape", choices=["layered", "hub", "cycle"], default="cycle")
    parser.add_argument("--max-ratio", type=float, default=2.0)
    parser.add_argument("--max-scaling", type=float, default=6.0)
    args = parser.parse_args(argv)

    failures: list[str] = []

    small = measure_seconds(SCALING_SMALL, args.shape)
    large = measure_seconds(SCALING_LARGE, args.shape)
    scaling = large / small if small > 0 else float("inf")
    print(
        f"scaling: {SCALING_LARGE} {args.shape} took {large:.3f} s, {SCALING_SMALL} took "
        f"{small:.3f} s (ratio {scaling:.1f}x, limit {args.max_scaling:g}x)"
    )
    if scaling > args.max_scaling:
        failures.append(
            f"perf regression: {SCALING_LARGE} {args.shape} took {large:.3f} s, "
            f"{SCALING_SMALL} took {small:.3f} s ({scaling:.1f}x > {args.max_scaling:g}x; "
            "linear growth is about 4x)"
        )

    baseline_path = Path(args.baseline)
    baseline: dict[str, Any] = {}
    if baseline_path.is_file():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    reference = baseline_seconds(baseline, args.files, args.shape)
    if reference is None:
        print(f"absolute: no same-platform baseline, skipped ({args.files} {args.shape})")
    else:
        took = measure_seconds(args.files, args.shape)
        print(f"absolute: {args.files} {args.shape} took {took:.3f} s, baseline {reference:.3f} s")
        if took > reference * args.max_ratio:
            failures.append(
                f"perf regression: {args.files} {args.shape} took {took:.3f} s, "
                f"baseline {reference:.3f} s (> {args.max_ratio:g}x)"
            )

    for message in failures:
        print(message)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
