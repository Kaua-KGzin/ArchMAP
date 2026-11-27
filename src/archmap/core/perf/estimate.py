"""Coefficient table and calibration workload for ``archmap analyze --estimate``."""
from __future__ import annotations

import json
import time
from collections.abc import Mapping
from importlib import resources
from pathlib import Path
from typing import Any, TypedDict

from archmap.core.perf.budget import CENTRALITY_REDUCED_SAMPLES

CALIBRATION_FILES = 100
# Shared by ``calibrate()`` and ``scripts/fit_estimate.py`` (which stored the reference).
CALIBRATION_REPEATS = 7
# ``calibrate()`` stops repeating once the workload has used this much time.
CALIBRATION_MAX_SECONDS = 0.5

# Share of total analysis time per stage (mean of the 20k-file python layered and hub
# rows in ``benchmarks/baseline.json``). Same keys as ``metrics.analysisQuality.timingsMs``.
STAGE_SHARES: dict[str, float] = {
    "discover": 0.363,
    "parse": 0.150,
    "cycles": 0.006,
    "impact": 0.103,
    "risk": 0.042,
    "testMapping": 0.021,
    "centrality": 0.313,
    "findings": 0.002,
}


class EstimateSeconds(TypedDict):
    low: float
    expected: float
    high: float


class Estimate(TypedDict):
    files: int
    bytes: int
    byLanguage: dict[str, int]
    seconds: EstimateSeconds
    peakMb: float
    speedFactor: float
    reductionsUnderBudget: list[str]


def load_coefficients() -> dict[str, Any]:
    """Read the packaged ``coefficients.json`` (fitted by ``scripts/fit_estimate.py``)."""
    text = (resources.files("archmap.core.perf") / "coefficients.json").read_text(
        encoding="utf-8"
    )
    data: dict[str, Any] = json.loads(text)
    return data


def calibration_once() -> float:
    """One run of the fixed micro-workload: parse 100 in-memory synthetic Python files."""
    from archmap.core.parser import parse_project
    from archmap.core.perf.synthetic import generate_sources

    sources = generate_sources(CALIBRATION_FILES, language="python", shape="layered", seed=0)
    started = time.perf_counter()
    parse_project(".", virtual_files=sources, parallel=False)
    return time.perf_counter() - started


def run_calibration_workload(
    repeats: int = CALIBRATION_REPEATS, max_seconds: float | None = None
) -> float:
    """Elapsed seconds of the calibration workload (best of ``repeats``).

    Deterministic input, no disk or process pool, so the ratio against
    ``reference.calibrationSeconds`` measures this machine's relative speed.
    With ``max_seconds`` it stops repeating once the runs so far have used that much time.
    """
    best = float("inf")
    spent = 0.0
    for _ in range(max(1, repeats)):
        elapsed = calibration_once()
        best = min(best, elapsed)
        spent += elapsed
        if max_seconds is not None and spent > max_seconds:
            break
    return best


def calibrate() -> float:
    """This machine's speed relative to the reference machine (above 1 means slower)."""
    reference = float(load_coefficients()["reference"]["calibrationSeconds"])
    measured = run_calibration_workload(CALIBRATION_REPEATS, CALIBRATION_MAX_SECONDS)
    return measured / reference


def estimate_project(
    root: Path,
    config: dict[str, Any],
    *,
    speed_factor: float | None = None,
    time_budget: float = 0.0,
) -> Estimate:
    """Predict analysis time and memory from a file listing alone; nothing is parsed."""
    from archmap.utils.file_utils import discover_source_files, file_language_from_id

    analysis = config.get("analysis", {})
    paths = discover_source_files(
        root,
        extra_ignored_dirs=analysis.get("ignore_dirs", []),
        max_file_size_bytes=int(analysis.get("max_file_size_bytes", 0) or 0),
        respect_gitignore=bool(analysis.get("respect_gitignore", True)),
    )
    by_language: dict[str, int] = {}
    kb_by_language: dict[str, float] = {}
    total_bytes = 0
    for path in paths:
        language = file_language_from_id(path.name) or "unknown"
        by_language[language] = by_language.get(language, 0) + 1
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        total_bytes += size
        kb_by_language[language] = kb_by_language.get(language, 0.0) + size / 1024

    coeffs = load_coefficients()
    if speed_factor is None:
        speed_factor = calibrate() if paths else 1.0
    base = 0.0
    for language, count in by_language.items():
        row = coeffs["languages"].get(language, coeffs["default"])
        base += count * row["secondsPerFile"] + kb_by_language[language] * row["secondsPerKb"]
    expected = base * speed_factor
    spread = coeffs["range"]
    memory = coeffs["memory"]
    estimate: Estimate = {
        "files": len(paths),
        "bytes": total_bytes,
        "byLanguage": dict(sorted(by_language.items(), key=lambda kv: (-kv[1], kv[0]))),
        "seconds": {
            "low": expected * spread["low"],
            "expected": expected,
            "high": expected * spread["high"],
        },
        "peakMb": memory["baseMb"] + memory["mbPerFile"] * len(paths) if paths else 0.0,
        "speedFactor": speed_factor,
        "reductionsUnderBudget": [],
    }
    estimate["reductionsUnderBudget"] = reductions_under_budget(estimate, time_budget)
    return estimate


def _split_total(total: float) -> dict[str, float]:
    return {stage: total * share for stage, share in STAGE_SHARES.items()}


def stage_seconds(estimate: Estimate) -> dict[str, float]:
    """Predicted expected seconds per analysis stage."""
    return _split_total(estimate["seconds"]["expected"])


def projected_stage_seconds(measured_ms: Mapping[str, float]) -> dict[str, float]:
    """Expected seconds per stage, extrapolated from the stages this run already timed.

    The run's own timings replace the file-listing estimate (no calibration, no
    second discovery): the timed stages' share of ``STAGE_SHARES`` scales them
    up to a whole-run total, which is then split like ``stage_seconds``.
    """
    timed = [stage for stage in STAGE_SHARES if stage in measured_ms]
    share = sum(STAGE_SHARES[stage] for stage in timed)
    if share <= 0:
        return _split_total(0.0)
    total_seconds = sum(float(measured_ms[stage]) for stage in timed) / 1000.0 / share
    return _split_total(total_seconds)


def reductions_under_budget(estimate: Estimate, time_budget: float) -> list[str]:
    """What the real run would reduce to fit ``time_budget`` seconds (``0`` means no limit).

    Mirrors ``analyze_graph``: stages run in ``STAGE_SHARES`` order; impact drops
    lists once the budget is used up; centrality is skipped when the budget is gone
    before it starts, or sampled when its share does not fit what is left.
    """
    if time_budget <= 0 or estimate["seconds"]["expected"] <= time_budget:
        return []
    stages = stage_seconds(estimate)
    started: dict[str, float] = {}
    elapsed = 0.0
    for stage, seconds in stages.items():
        started[stage] = elapsed
        elapsed += seconds
    reductions: list[str] = []
    if stages["impact"] > 0 and started["impact"] + stages["impact"] > time_budget:
        reductions.append(
            "impact would leave out impacted-file lists once the budget runs out "
            "(impactCount and risk stay exact)"
        )
    left = time_budget - started["centrality"]
    if left <= 0:
        reductions.append("centrality would be skipped (the budget is used up before it starts)")
    elif stages["centrality"] > left and estimate["files"] > CENTRALITY_REDUCED_SAMPLES:
        reductions.append(f"centrality would run on a {CENTRALITY_REDUCED_SAMPLES}-file sample")
    return reductions


def format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "0 s"
    if seconds < 1:
        return "<1 s"
    whole = round(seconds)
    if whole < 60:
        return f"{whole} s"
    minutes, secs = divmod(whole, 60)
    if minutes < 60:
        return f"{minutes} min {secs} s" if secs else f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min" if minutes else f"{hours} h"


def format_estimate(estimate: Estimate, time_budget: float = 0.0) -> list[str]:
    """The human-readable ``[estimate]`` lines."""
    languages = " · ".join(f"{lang} {n:,}" for lang, n in estimate["byLanguage"].items())
    detail = f" ({languages})" if languages else ""
    seconds = estimate["seconds"]
    lines = [
        f"[estimate] {estimate['files']:,} source files{detail}, "
        f"{estimate['bytes'] / 1_000_000:.1f} MB",
        f"[estimate] expected time: {format_duration(seconds['expected'])} "
        f"(range {format_duration(seconds['low'])} – {format_duration(seconds['high'])}) "
        "on this machine",
        f"[estimate] expected peak Python heap (tracemalloc): ~{estimate['peakMb']:.0f} MB",
    ]
    lines.extend(
        f"[estimate] with --time-budget {time_budget:g}: {reduction}"
        for reduction in estimate["reductionsUnderBudget"]
    )
    lines.append("[estimate] no analysis was run. Remove --estimate to analyze.")
    return lines
