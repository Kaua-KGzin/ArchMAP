"""
Fit the ``archmap analyze --estimate`` coefficient table from benchmark rows.

Usage:
    python scripts/fit_estimate.py --collect   # run the benchmark grid, rewrite baseline.json, fit
    python scripts/fit_estimate.py             # re-fit from the existing benchmarks/baseline.json

Grid: 1k/5k/20k/50k files x python/typescript x layered/hub/cycle. Layered and hub rows are
fitted (least squares through the origin); cycle rows are only checked against the fit.
Writes ``src/archmap/core/perf/coefficients.json``. Languages without a generator
use ``default`` (= the python row). ``secondsPerKb`` is 0.0: the synthetic files all have
about the same size, so file count and size are collinear and cannot be fitted separately.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

BASELINE = ROOT / "benchmarks" / "baseline.json"
COEFFICIENTS = ROOT / "src" / "archmap" / "core" / "perf" / "coefficients.json"
SIZES = (1000, 5000, 20000, 50000)
LANGUAGES = ("python", "typescript")
SHAPES = ("layered", "hub", "cycle")
FITTED_SHAPES = ("layered", "hub")


def collect() -> dict[str, Any]:
    from benchmark import run_size

    rows: list[dict[str, Any]] = []
    for language in LANGUAGES:
        for shape in SHAPES:
            for size in SIZES:
                # best of 2: the first run on freshly written files pays cold-cache/AV cost
                row = run_size(size, language, shape, repeat=2)
                print(f"{language} {shape} {size}: {row['seconds']}s {row['peakMb']}MB", flush=True)
                rows.append(row)
    return {
        "rows": rows,
        "machine": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpuCount": os.cpu_count(),
        },
    }


def slope_through_origin(points: list[tuple[float, float]]) -> float:
    """Least squares y = k * x."""
    return sum(x * y for x, y in points) / sum(x * x for x, _ in points)


def fit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    languages: dict[str, dict[str, float]] = {}
    for language in LANGUAGES:
        pts = [
            (float(r["files"]), float(r["seconds"]))
            for r in rows
            if r["language"] == language and r["shape"] in FITTED_SHAPES
        ]
        languages[language] = {
            "secondsPerFile": slope_through_origin(pts),
            "secondsPerKb": 0.0,
        }
    mem_pts = [
        (float(r["files"]), float(r["peakMb"]))
        for r in rows
        if r["shape"] in FITTED_SHAPES and r.get("peakMb") is not None
    ]
    from archmap.core.perf.estimate import CALIBRATION_REPEATS, run_calibration_workload

    return {
        "schema": 1,
        "reference": {"calibrationSeconds": run_calibration_workload(CALIBRATION_REPEATS)},
        "languages": languages,
        "default": dict(languages["python"]),
        "memory": {"baseMb": 0.0, "mbPerFile": slope_through_origin(mem_pts)},
        "range": {"low": 0.5, "high": 2.0},
    }


def report(rows: list[dict[str, Any]], table: dict[str, Any]) -> None:
    print(f"{'lang':<11}{'shape':<8}{'files':>6}{'actual s':>10}{'pred s':>9}{'ratio':>7}")
    for r in rows:
        pred = table["languages"][r["language"]]["secondsPerFile"] * r["files"]
        tag = "" if r["shape"] in FITTED_SHAPES else "  (checked, not fitted)"
        print(
            f"{r['language']:<11}{r['shape']:<8}{r['files']:>6}{r['seconds']:>10.2f}"
            f"{pred:>9.2f}{pred / r['seconds']:>7.2f}{tag}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--collect", action="store_true", help="re-run the benchmark grid first")
    args = parser.parse_args()

    if args.collect:
        data = collect()
        BASELINE.parent.mkdir(exist_ok=True)
        BASELINE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    else:
        data = json.loads(BASELINE.read_text(encoding="utf-8"))
    table = fit(data["rows"])
    COEFFICIENTS.write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8")
    report(data["rows"], table)


if __name__ == "__main__":
    main()
