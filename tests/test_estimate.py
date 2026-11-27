from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from archmap.cli.args import _time_budget
from archmap.cli.main import main
from archmap.config import default_project_config
from archmap.core import analyze_project
from archmap.core.perf.estimate import (
    CALIBRATION_REPEATS,
    STAGE_SHARES,
    calibrate,
    estimate_project,
    format_duration,
    stage_seconds,
)
from archmap.core.perf.synthetic import generate_project


def _config() -> dict:
    return dict(default_project_config())


def test_empty_directory_estimates_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    estimate = estimate_project(tmp_path, _config())
    assert estimate["files"] == 0
    assert estimate["seconds"]["expected"] == 0

    assert main(["analyze", str(tmp_path), "--estimate"]) == 0
    out = capsys.readouterr().out
    assert "0 source files" in out
    assert "expected time: 0 s" in out


def test_source_less_directory_estimates_zero(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    estimate = estimate_project(tmp_path, _config())
    assert estimate["files"] == 0
    assert estimate["seconds"] == {"low": 0, "expected": 0, "high": 0}


def test_json_mode_stdout_is_only_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    generate_project(tmp_path, 20)
    assert main(["analyze", str(tmp_path), "--estimate", "--format", "json"]) == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["files"] == 20
    assert data["byLanguage"] == {"python": 20}
    assert set(data["seconds"]) == {"low", "expected", "high"}


def test_estimate_json_in_subprocess_has_clean_stdout(tmp_path: Path) -> None:
    generate_project(tmp_path, 10)
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src") + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-m", "archmap.cli.main", "analyze", str(tmp_path),
         "--estimate", "--format", "json"],
        cwd=repo_root, env=env, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["files"] == 10


def test_text_output_and_no_side_effects(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    generate_project(tmp_path, 30)
    before = sorted(p.name for p in tmp_path.rglob("*"))
    assert main(["analyze", str(tmp_path), "--estimate"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("[estimate] 30 source files (python 30), ")
    assert out[1].startswith("[estimate] expected time: ")
    assert out[2].startswith("[estimate] expected peak Python heap (tracemalloc): ~")
    assert out[-1] == "[estimate] no analysis was run. Remove --estimate to analyze."
    assert sorted(p.name for p in tmp_path.rglob("*")) == before


def test_speed_factor_scales_expected(tmp_path: Path) -> None:
    generate_project(tmp_path, 50)
    one = estimate_project(tmp_path, _config(), speed_factor=1.0)
    two = estimate_project(tmp_path, _config(), speed_factor=2.0)
    assert one["seconds"]["expected"] > 0
    assert two["seconds"]["expected"] == pytest.approx(2 * one["seconds"]["expected"])
    assert two["seconds"]["low"] < two["seconds"]["expected"] < two["seconds"]["high"]


def test_stage_seconds_sum_to_expected(tmp_path: Path) -> None:
    generate_project(tmp_path, 50)
    estimate = estimate_project(tmp_path, _config(), speed_factor=1.0)
    stages = stage_seconds(estimate)
    assert set(stages) == set(STAGE_SHARES)
    assert sum(stages.values()) == pytest.approx(estimate["seconds"]["expected"], rel=0.01)


def test_time_budget_lists_reductions(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    generate_project(tmp_path, 100)
    unlimited = estimate_project(tmp_path, _config(), speed_factor=1.0)
    assert unlimited["reductionsUnderBudget"] == []
    tight = estimate_project(tmp_path, _config(), speed_factor=1.0, time_budget=1e-9)
    assert tight["reductionsUnderBudget"] == [
        "impact would leave out impacted-file lists once the budget runs out "
        "(impactCount and risk stay exact)",
        "centrality would be skipped (the budget is used up before it starts)",
    ]
    stages = stage_seconds(unlimited)
    before_centrality = sum(
        seconds for stage, seconds in stages.items() if stage not in ("centrality", "findings")
    )
    # Enough budget to reach centrality, not enough to run it in full: sampled.
    squeezed = estimate_project(
        tmp_path,
        _config(),
        speed_factor=1.0,
        time_budget=before_centrality + stages["centrality"] / 2,
    )
    assert squeezed["reductionsUnderBudget"] == ["centrality would run on a 64-file sample"]

    assert main(["analyze", str(tmp_path), "--estimate", "--time-budget", "0.000001"]) == 0
    assert "with --time-budget 1e-06: centrality would be skipped" in capsys.readouterr().out
    assert main(["analyze", str(tmp_path), "--estimate", "--time-budget", "0"]) == 0
    assert "--time-budget" not in capsys.readouterr().out.replace("Remove --estimate", "")


def test_negative_time_budget_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["analyze", ".", "--estimate", "--time-budget", "-5"])
    assert exc.value.code == 2
    assert "must be 0 or more seconds" in capsys.readouterr().err
    with pytest.raises(argparse.ArgumentTypeError):
        _time_budget("abc")
    assert _time_budget("0") == 0.0


def test_format_duration() -> None:
    assert format_duration(0) == "0 s"
    assert format_duration(0.2) == "<1 s"
    assert format_duration(38) == "38 s"
    assert format_duration(76) == "1 min 16 s"
    assert format_duration(3900) == "1 h 5 min"


def test_calibrate_is_positive_and_bounded() -> None:
    started = time.perf_counter()
    factor = calibrate()
    assert factor > 0
    assert time.perf_counter() - started < 5
    assert CALIBRATION_REPEATS == 7


def test_estimate_tracks_real_analysis_time(tmp_path: Path) -> None:
    generate_project(tmp_path, 2000, shape="layered")
    estimate = estimate_project(tmp_path, _config())
    started = time.perf_counter()
    analyze_project(tmp_path, use_cache=False)
    actual = time.perf_counter() - started
    assert estimate["seconds"]["low"] * 0.5 <= actual <= estimate["seconds"]["high"] * 2
