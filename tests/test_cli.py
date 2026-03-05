from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_cli_analyze_with_both_exports_json_and_mermaid(tmp_path) -> None:
    fixture = tmp_path / "fixture"
    fixture.mkdir()

    (fixture / "server.py").write_text(
        "import requests\nfrom .auth import token\n",
        encoding="utf-8",
    )
    (fixture / "auth.py").write_text("token = 'ok'\n", encoding="utf-8")

    json_output = tmp_path / "out.json"
    mermaid_output = tmp_path / "out.mmd"

    result = _run_cli(
        [
            "analyze",
            str(fixture),
            "--format",
            "both",
            "--out",
            str(json_output),
            "--out-mermaid",
            str(mermaid_output),
        ]
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert json_output.exists()
    assert mermaid_output.exists()


def test_cli_analyze_with_mermaid_only_exports_mermaid(tmp_path) -> None:
    fixture = tmp_path / "fixture2"
    fixture.mkdir()
    (fixture / "entry.js").write_text('import "./module.js";\n', encoding="utf-8")
    (fixture / "module.js").write_text("export {};\n", encoding="utf-8")

    json_output = tmp_path / "out.json"
    mermaid_output = tmp_path / "out.mmd"

    result = _run_cli(
        [
            "analyze",
            str(fixture),
            "--format",
            "mermaid",
            "--out",
            str(json_output),
            "--out-mermaid",
            str(mermaid_output),
        ]
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert mermaid_output.exists()
    assert not json_output.exists()


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    src_path = str(repo_root / "src")
    env["PYTHONPATH"] = src_path + os.pathsep + env.get("PYTHONPATH", "")

    return subprocess.run(
        [sys.executable, "-m", "archmap.cli.main", *args],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
