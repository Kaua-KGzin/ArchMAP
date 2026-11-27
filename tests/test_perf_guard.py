from __future__ import annotations

import importlib.util
import json
import platform
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "perf_guard.py"


def _load():
    spec = importlib.util.spec_from_file_location("archmap_perf_guard", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _baseline(tmp_path: Path, seconds: float, plat: str | None = None) -> Path:
    path = tmp_path / "baseline.json"
    payload = {
        "rows": [
            {"files": 5000, "language": "python", "shape": "cycle", "seconds": seconds},
        ],
        "machine": {"platform": plat or platform.platform()},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _fake(monkeypatch, guard, times: dict[int, float]):
    monkeypatch.setattr(guard, "measure_seconds", lambda files, shape: times[files])


LINEAR = {1000: 1.0, 4000: 4.0, 5000: 5.0}


def test_slower_than_baseline_fails_with_message(tmp_path, monkeypatch, capsys):
    guard = _load()
    _fake(monkeypatch, guard, LINEAR)
    code = guard.main(["--baseline", str(_baseline(tmp_path, 0.001))])
    assert code == 1
    assert "perf regression: 5000 cycle took 5.000 s, baseline 0.001 s (> 2x)" in (
        capsys.readouterr().out
    )


def test_slow_baseline_passes(tmp_path, monkeypatch):
    guard = _load()
    _fake(monkeypatch, guard, LINEAR)
    assert guard.main(["--baseline", str(_baseline(tmp_path, 1000.0))]) == 0


def test_no_same_platform_row_is_skipped(tmp_path, monkeypatch, capsys):
    guard = _load()
    # Would fail the absolute check if the row counted.
    _fake(monkeypatch, guard, LINEAR)
    other = "Plan9-1.0" if not platform.platform().startswith("Plan9") else "Other-1"
    code = guard.main(["--baseline", str(_baseline(tmp_path, 0.001, other))])
    assert code == 0
    assert "no same-platform baseline, skipped" in capsys.readouterr().out


def test_missing_baseline_file_is_skipped(tmp_path, monkeypatch, capsys):
    guard = _load()
    _fake(monkeypatch, guard, LINEAR)
    assert guard.main(["--baseline", str(tmp_path / "nope.json")]) == 0
    assert "skipped" in capsys.readouterr().out


def test_scaling_over_limit_fails(tmp_path, monkeypatch, capsys):
    guard = _load()
    quadratic = {1000: 1.0, 4000: 16.0, 5000: 25.0}
    _fake(monkeypatch, guard, quadratic)
    code = guard.main(["--baseline", str(_baseline(tmp_path, 1000.0))])
    assert code == 1
    out = capsys.readouterr().out
    assert "perf regression: 4000 cycle took 16.000 s" in out
    assert "16.0x > 6x" in out


def test_scaling_limit_is_configurable(tmp_path, monkeypatch):
    guard = _load()
    _fake(monkeypatch, guard, {1000: 1.0, 4000: 8.0, 5000: 10.0})
    base = str(_baseline(tmp_path, 1000.0))
    assert guard.main(["--baseline", base]) == 1
    assert guard.main(["--baseline", base, "--max-scaling", "10"]) == 0
