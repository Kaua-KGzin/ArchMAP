"""CLI tests for inspect / hexdump / strings / audit / commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.binary_samples import build_elf, build_pe

from archmap.cli.main import main


def _run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = main(argv)
    return code, capsys.readouterr().out


def test_inspect_file_text_and_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "app"
    target.write_bytes(build_elf(e_type=2, stack_exec=True))
    code, out = _run(["inspect", str(target)], capsys)
    assert code == 0
    assert "Hardening: NX no | PIE no" in out
    assert "executable_stack" not in out  # text output shows messages, not categories
    assert "stack is executable" in out

    out_file = tmp_path / "r.json"
    code, out = _run(["inspect", str(target), "--json", "--out", str(out_file)], capsys)
    report = json.loads(out)
    assert report["format"]["format"] == "elf"
    assert json.loads(out_file.read_text())["hashes"] == report["hashes"]


def test_inspect_fail_on_gate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "weak.exe"
    target.write_bytes(build_pe(dll_characteristics=0))
    assert _run(["inspect", str(target), "--fail-on", "high"], capsys)[0] == 2
    good = tmp_path / "good.exe"
    good.write_bytes(build_pe(signed=True))
    assert _run(["inspect", str(good), "--fail-on", "info"], capsys)[0] == 0


def test_inspect_directory(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "app").write_bytes(build_elf())
    (tmp_path / "notes.txt").write_text("hi")
    code, out = _run(["inspect", str(tmp_path)], capsys)
    assert code == 0
    assert "2 files" in out
    assert "lib:libc.so.6 <- 1" in out


def test_inspect_missing_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inspect", str(tmp_path / "nope")]) == 1


def test_hexdump_and_strings(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "blob"
    target.write_bytes(b"\x00\x01hello world\x00visit https://example.org/x\x00")
    code, out = _run(["hexdump", str(target), "-n", "0x10"], capsys)
    assert code == 0
    assert out.splitlines()[0].startswith("00000000  00 01 68 65")

    code, out = _run(["strings", str(target), "--offsets"], capsys)
    assert "0x00000002  hello world" in out
    code, out = _run(["strings", str(target), "--interesting", "--json"], capsys)
    assert json.loads(out)["interesting"][0]["categories"] == ["url"]


def test_audit_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": ["Bash(*)"]}})
    )
    code, out = _run(["audit", str(tmp_path), "--fail-on", "high"], capsys)
    assert code == 2
    assert "AGENT-001" in out
    code, out = _run(["audit", str(tmp_path), "--json"], capsys)
    assert json.loads(out)["agentFindings"] == 1


def test_commands_catalog(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = _run(["commands", "--json"], capsys)
    catalog = json.loads(out)
    names = {c["name"] for c in catalog["commands"]}
    assert {"analyze", "inspect", "hexdump", "strings", "audit", "commands"} <= names
    inspect = next(c for c in catalog["commands"] if c["name"] == "inspect")
    fail_on = next(o for o in inspect["options"] if "--fail-on" in o["name"])
    assert fail_on["choices"] == ["info", "low", "medium", "high", "critical"]


def test_text_renderers_for_each_format(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import sqlite3
    import zipfile

    from tests.binary_samples import build_fat_macho, build_wasm

    samples = {
        "lib.wasm": build_wasm(),
        "universal": build_fat_macho(),
        "tool.exe": build_pe(section_names=("UPX0", "UPX1")),
    }
    for name, data in samples.items():
        (tmp_path / name).write_bytes(data)
    (tmp_path / "rows.csv").write_text("a,b\n1,2\n")
    (tmp_path / "doc.json").write_text('{"k": [1, 2]}')
    with zipfile.ZipFile(tmp_path / "app.apk", "w") as archive:
        archive.writestr("AndroidManifest.xml", b"\x03\x00")
        archive.writestr("lib/x86_64/libx.so", build_elf())
    connection = sqlite3.connect(tmp_path / "db.sqlite")
    connection.execute("CREATE TABLE t (x INTEGER)")
    connection.commit()
    connection.close()

    expectations = {
        "lib.wasm": "Toolchain: Rust 1.80",
        "universal": "Image: Mach-O 64 ARM64 executable",
        "tool.exe": "Packer: UPX",
        "rows.csv": "Columns: a:integer, b:integer",
        "doc.json": 'JSON schema: {"k": ["integer"]}',
        "app.apk": "ABIs ['x86_64']",
        "db.sqlite": "t (0 rows) — x:INTEGER",
    }
    for name, expected in expectations.items():
        assert main(["inspect", str(tmp_path / name)]) == 0
        assert expected in capsys.readouterr().out, name


def test_commands_text_and_empty_context(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["commands"]) == 0
    assert "inspect" in capsys.readouterr().out
    (tmp_path / "a.py").write_text("x = 1\n")
    assert main(["context", "zzz qqq", str(tmp_path)]) == 0
    assert "No files matched" in capsys.readouterr().out
