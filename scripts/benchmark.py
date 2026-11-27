"""
ArchMAP benchmark — measures analysis time, peak memory and per-stage timings
on deterministic synthetic projects.

Usage:
    python scripts/benchmark.py
    python scripts/benchmark.py --sizes 1000,5000 --language typescript --shape hub
    python scripts/benchmark.py --json out.json --repeat 3

Always runs ``analyze_project(..., use_cache=False)``.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Any

# Allow running from repo root without installing
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

sys.setrecursionlimit(10000)

from archmap.core import analyze_project  # noqa: E402
from archmap.core.perf.synthetic import generate_project  # noqa: E402

DEFAULT_SIZES = "100,500,1000,5000"


def _timed(root: Path) -> tuple[float, dict[str, Any]]:
    start = time.perf_counter()
    report = analyze_project(root, use_cache=False)
    return time.perf_counter() - start, report


def _peak_mb(root: Path) -> float:
    tracemalloc.start()
    try:
        analyze_project(root, use_cache=False)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak / (1024 * 1024)


def run_size(
    size: int, language: str, shape: str, repeat: int, measure_memory: bool = True
) -> dict[str, Any]:
    """Timing passes run untraced (tracemalloc skews them); memory is a separate pass."""
    best: tuple[float, dict[str, Any]] | None = None
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        generate_project(root, size, language=language, shape=shape)  # type: ignore[arg-type]
        for _ in range(max(1, repeat)):
            run = _timed(root)
            if best is None or run[0] < best[0]:
                best = run
        peak_mb = _peak_mb(root) if measure_memory else None
    assert best is not None
    elapsed, report = best
    metrics = report.get("metrics", {})
    return {
        "files": size,
        "language": language,
        "shape": shape,
        "seconds": round(elapsed, 3),
        "peakMb": round(peak_mb, 1) if peak_mb is not None else None,
        "edges": metrics.get("totalDependencies", 0),
        "stagesMs": metrics.get("analysisQuality", {}).get("timingsMs", {}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--sizes", default=DEFAULT_SIZES, help="comma-separated file counts")
    parser.add_argument("--language", choices=["python", "typescript"], default="python")
    parser.add_argument("--shape", choices=["layered", "hub", "cycle"], default="cycle")
    parser.add_argument("--json", dest="json_out", help="write rows to this JSON file")
    parser.add_argument("--repeat", type=int, default=1, help="runs per size (best is kept)")
    parser.add_argument("--no-memory", action="store_true", help="skip the tracemalloc pass")
    args = parser.parse_args()

    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]
    rows = [run_size(n, args.language, args.shape, args.repeat, not args.no_memory) for n in sizes]

    print(f"{'Files':>6}  {'Time (s)':>9}  {'Peak MB':>8}  {'Edges':>7}  Stages (ms)")
    print("-" * 78)
    for row in rows:
        stages = " ".join(f"{k}={v}" for k, v in row["stagesMs"].items())
        peak = row["peakMb"] if row["peakMb"] is not None else float("nan")
        print(
            f"{row['files']:>6}  {row['seconds']:>9.3f}  {peak:>8.1f}  "
            f"{row['edges']:>7}  {stages}"
        )

    if args.json_out:
        payload = {
            "rows": rows,
            "machine": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "cpuCount": os.cpu_count(),
            },
        }
        Path(args.json_out).write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
