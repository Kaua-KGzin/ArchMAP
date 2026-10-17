"""Tests for structured-data inspection and directory inventory (archmap.core.inspect)."""

from __future__ import annotations

import csv
import gzip
import io
import json
import sqlite3
import tarfile
import zipfile
from pathlib import Path

from tests.binary_samples import build_elf, build_pe

from archmap.core.binary.analyzer import inspect_file
from archmap.core.inspect.inventory import inspect_directory


def test_json_schema(tmp_path: Path) -> None:
    target = tmp_path / "data.json"
    target.write_text(json.dumps({"users": [{"id": 1, "tags": ["a"]}, {"id": 2, "ok": True}]}))
    data = inspect_file(target)["data"]
    assert data["valid"] is True
    assert data["schema"] == {"users": [{"id": "integer", "tags": ["string"], "ok": "boolean"}]}


def test_invalid_json(tmp_path: Path) -> None:
    target = tmp_path / "broken.json"
    target.write_text('{"a": ')
    data = inspect_file(target)["data"]
    assert data["valid"] is False
    assert "error" in data


def test_jsonl(tmp_path: Path) -> None:
    target = tmp_path / "events.jsonl"
    target.write_text('{"a": 1}\n{"a": 2}\nnot json\n\n')
    data = inspect_file(target)["data"]
    assert data["records"] == 3
    assert data["invalidLines"] == 1


def test_csv_types(tmp_path: Path) -> None:
    target = tmp_path / "sales.csv"
    with target.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "amount", "day", "paid", "note"])
        for i in range(20):
            writer.writerow([i, f"{i}.5", "2024-03-01", "yes", "" if i % 2 else "x"])
        writer.writerow([1, 2])
    data = inspect_file(target)["data"]
    types = {col["name"]: col["type"] for col in data["columns"]}
    assert types == {
        "id": "integer",
        "amount": "number",
        "day": "date",
        "paid": "boolean",
        "note": "string",
    }
    assert data["rows"] == 21
    assert data["raggedRows"] == 1


def test_sqlite_is_read_only(tmp_path: Path) -> None:
    target = tmp_path / "app.db"
    connection = sqlite3.connect(target)
    connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
    connection.executemany("INSERT INTO users (email) VALUES (?)", [("a",), ("b",)])
    connection.execute("CREATE INDEX idx_email ON users(email)")
    connection.commit()
    connection.close()
    before = target.read_bytes()

    data = inspect_file(target)["data"]
    assert data["tables"][0]["name"] == "users"
    assert data["tables"][0]["rows"] == 2
    assert data["tables"][0]["columns"][0] == {"name": "id", "type": "INTEGER", "primaryKey": True}
    assert data["indexCount"] == 1
    assert target.read_bytes() == before
    assert not (tmp_path / "app.db-journal").exists()


def test_zip_slip_is_flagged(tmp_path: Path) -> None:
    target = tmp_path / "evil.zip"
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("ok.txt", "fine")
        archive.writestr("../../etc/cron.d/job", "boom")
    report = inspect_file(target)
    assert report["data"]["unsafePaths"] == ["../../etc/cron.d/job"]
    assert [f["category"] for f in report["findings"]] == ["suspicious_container"]


def test_tarball_red_flags(tmp_path: Path) -> None:
    target = tmp_path / "layer.tar.gz"
    with tarfile.open(target, "w:gz") as archive:
        link = tarfile.TarInfo("passwd")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        archive.addfile(link)
        suid = tarfile.TarInfo("bin/tool")
        suid.size = 1
        suid.mode = 0o4755
        archive.addfile(suid, io.BytesIO(b"x"))
    data = inspect_file(target)["data"]
    assert data["kind"] == "tar"
    assert data["escapingLinks"] == ["passwd"]
    assert data["setuidFiles"] == ["bin/tool"]
    assert len(data["warnings"]) == 2


def test_gzip_metadata(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt.gz"
    with gzip.open(target, "wb") as handle:
        handle.write(b"hello" * 10)
    data = inspect_file(target)["data"]
    assert data["uncompressedSizeMod32"] == 50


def test_inventory_builds_linkage_graph(tmp_path: Path) -> None:
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "libcore.so.1").write_bytes(
        build_elf(interp=False, soname="libcore.so.1", needed=("libc.so.6",))
    )
    (tmp_path / "app").write_bytes(build_elf(needed=("libcore.so.1", "libc.so.6")))
    (tmp_path / "tool.exe").write_bytes(build_pe(dll_characteristics=0))
    (tmp_path / "README.md").write_text("hello")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: x")

    inventory = inspect_directory(tmp_path)
    assert inventory["filesScanned"] == 4
    assert inventory["byFormat"]["elf"] == 2
    edges = {(e["source"], e["target"]) for e in inventory["graph"]["edges"]}
    assert ("app", "lib/libcore.so.1") in edges  # resolved inside the tree
    assert ("app", "lib:libc.so.6") in edges
    assert ("tool.exe", "lib:KERNEL32.dll") in edges
    assert inventory["mostLinkedLibraries"][0] == {"library": "lib:libc.so.6", "dependents": 2}
    ids = [f["id"] for f in inventory["findings"]]
    assert ids == [f"BIN-{i:03d}" for i in range(1, len(ids) + 1)]
    assert {f["file"] for f in inventory["findings"]} == {"tool.exe"}


def test_inventory_truncates(tmp_path: Path) -> None:
    for index in range(5):
        (tmp_path / f"f{index}.txt").write_text("x")
    inventory = inspect_directory(tmp_path, max_files=3)
    assert inventory["truncated"] is True
    assert inventory["filesScanned"] == 3
