"""
ArchMAP benchmark — measures analysis time for projects of different sizes.

Usage:
    python scripts/benchmark.py

Generates synthetic Python projects (100 / 500 / 1000 / 5000 files),
runs archmap.core.analyze_project on each, and prints a timing table.
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

# Allow running from repo root without installing
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from archmap.core import analyze_project

SIZES = [100, 500, 1_000, 5_000]
IMPORTS_PER_FILE = 5  # each file imports from 5 others (approximate)


def _generate_project(root: Path, n_files: int) -> None:
    """Create n_files Python files with cross-imports inside root."""
    root.mkdir(parents=True, exist_ok=True)

    filenames = [f"module_{i:04d}.py" for i in range(n_files)]

    for idx, name in enumerate(filenames):
        imports: list[str] = []
        for j in range(1, IMPORTS_PER_FILE + 1):
            target_idx = (idx + j) % n_files
            target = Path(filenames[target_idx]).stem
            imports.append(f"import {target}")

        content = "\n".join(imports) + f"\n\ndef func_{idx}(): pass\n"
        (root / name).write_text(content, encoding="utf-8")


def _run_once(project_root: Path) -> tuple[float, dict]:
    start = time.perf_counter()
    report = analyze_project(project_root)
    elapsed = time.perf_counter() - start
    return elapsed, report


def main() -> None:
    print(f"{'Files':>6}  {'Time (s)':>9}  {'Deps':>6}  {'Cycles':>6}  {'Files/s':>8}")
    print("-" * 45)

    for size in SIZES:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _generate_project(root, size)

            # warm-up run (discard result)
            _run_once(root)

            # timed run
            elapsed, report = _run_once(root)

        metrics = report.get("metrics", {})
        deps = metrics.get("totalDependencies", "?")
        cycles = metrics.get("circularDependencyCount", "?")
        rate = int(size / elapsed) if elapsed > 0 else "∞"

        print(f"{size:>6}  {elapsed:>9.3f}  {deps:>6}  {cycles:>6}  {rate:>8}")

    print()
    print("* Each file imports from 5 neighbour modules (wrapping).")
    print("* Times include filesystem I/O for reading generated files.")
    print("* Warm-up run discarded; result is single timed run.")


if __name__ == "__main__":
    main()
