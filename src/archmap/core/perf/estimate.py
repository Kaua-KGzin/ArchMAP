"""Coefficient table and calibration workload for ``archmap analyze --estimate``."""
from __future__ import annotations

import json
import time
from importlib import resources
from typing import Any

CALIBRATION_FILES = 100
CALIBRATION_REPEATS = 5


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


def run_calibration_workload(repeats: int = 1) -> float:
    """Elapsed seconds of the calibration workload (best of ``repeats``).

    Deterministic input, no disk or process pool, so the ratio against
    ``reference.calibrationSeconds`` measures this machine's relative speed.
    """
    return min(calibration_once() for _ in range(max(1, repeats)))
