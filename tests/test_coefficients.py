from __future__ import annotations

from archmap.core.perf.estimate import load_coefficients, run_calibration_workload
from archmap.utils.file_utils import SUPPORTED_EXTENSIONS


def _is_row(row: object) -> bool:
    return (
        isinstance(row, dict)
        and isinstance(row.get("secondsPerFile"), float)
        and isinstance(row.get("secondsPerKb"), float)
        and row["secondsPerFile"] >= 0
        and row["secondsPerKb"] >= 0
    )


def test_coefficients_schema() -> None:
    coeffs = load_coefficients()
    assert coeffs["schema"] == 1
    assert coeffs["reference"]["calibrationSeconds"] > 0
    assert coeffs["range"] == {"low": 0.5, "high": 2.0}
    assert coeffs["memory"]["baseMb"] >= 0
    assert coeffs["memory"]["mbPerFile"] > 0
    assert _is_row(coeffs["default"])
    assert coeffs["languages"]
    assert all(_is_row(row) for row in coeffs["languages"].values())


def test_every_supported_language_resolves() -> None:
    coeffs = load_coefficients()
    for language in set(SUPPORTED_EXTENSIONS.values()):
        row = coeffs["languages"].get(language, coeffs["default"])
        assert _is_row(row), language


def test_calibration_workload_is_fast_and_positive() -> None:
    seconds = run_calibration_workload()
    assert isinstance(seconds, float)
    assert 0 < seconds < 0.5
