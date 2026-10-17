"""Tests for the binary / reverse-engineering engine (archmap.core.binary)."""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest
from tests.binary_samples import build_elf, build_macho, build_pe, build_wasm

from archmap.core.binary.analyzer import build_binary_findings, inspect_file
from archmap.core.binary.elf import parse_elf
from archmap.core.binary.entropy import entropy_profile, shannon_entropy
from archmap.core.binary.formats import detect_format
from archmap.core.binary.hexdump import hexdump
from archmap.core.binary.macho import parse_macho
from archmap.core.binary.pe import parse_pe
from archmap.core.binary.reader import BinaryFormatError, ByteView, file_hashes, open_binary
from archmap.core.binary.strings import analyze_strings, classify_string, extract_strings
from archmap.core.binary.wasm import parse_wasm

# --------------------------------------------------------------------------- formats


@pytest.mark.parametrize(
    ("data", "name", "expected"),
    [
        (build_elf(), "a", "elf"),
        (build_pe(), "a.exe", "pe"),
        (build_macho(), "a", "macho"),
        (build_wasm(), "a.wasm", "wasm"),
        (b"MZ" + b"\x00" * 100, "a.com", "mz"),
        (b"\xca\xfe\xba\xbe\x00\x00\x00\x02" + b"\x00" * 40, "u", "macho-fat"),
        (b"\xca\xfe\xba\xbe\x00\x00\x00\x41", "A.class", "java-class"),
        (b"dex\n035\x00", "classes.dex", "dex"),
        (b"SQLite format 3\x00" + b"\x00" * 84, "x.db", "sqlite"),
        (b"%PDF-1.7\n", "x.pdf", "pdf"),
        (b"\x89PNG\r\n\x1a\n", "x.png", "png"),
        (b"\x1f\x8b\x08\x00", "x.gz", "gzip"),
        (b"\xfd7zXZ\x00", "x.xz", "xz"),
        (b"\xd4\xc3\xb2\xa1", "x.pcap", "pcap"),
        (b"\x00" * 257 + b"ustar\x00", "x.tar", "tar"),
        (b"#!/bin/sh\necho hi\n", "run", "script"),
        (b'{"a": 1}', "x.json", "json"),
        (b"a,b\n1,2\n", "x.csv", "csv"),
        (b"plain words", "x.txt", "text"),
        (b"\x00\x01\x02\xff", "blob", "data"),
        (b"", "empty", "empty"),
        (b"\x6f\x0d\x0d\x0a" + b"\x00" * 12, "m.pyc", "pyc"),
    ],
)
def test_detect_format(data: bytes, name: str, expected: str) -> None:
    assert detect_format(data, name)["format"] == expected


def test_java_class_version() -> None:
    info = detect_format(b"\xca\xfe\xba\xbe\x00\x00\x00\x41", "A.class")
    assert "Java 21" in info["description"]


def test_zip_flavours(tmp_path: Path) -> None:
    import zipfile

    apk = tmp_path / "app.apk"
    with zipfile.ZipFile(apk, "w") as archive:
        archive.writestr("AndroidManifest.xml", b"\x03\x00")
        archive.writestr("classes.dex", b"dex\n035\x00")
        archive.writestr("lib/arm64-v8a/libnative.so", build_elf())
    with open_binary(apk) as data:
        assert detect_format(data, apk.name)["format"] == "apk"
    summary = inspect_file(apk)["data"]
    assert summary["android"]["abis"] == ["arm64-v8a"]
    assert summary["android"]["dexFiles"] == ["classes.dex"]


# --------------------------------------------------------------------------- primitives


def test_byteview_bounds() -> None:
    view = ByteView(b"\x01\x02\x03\x04")
    assert view.u32(0) == 0x04030201
    with pytest.raises(BinaryFormatError):
        view.u32(1)
    with pytest.raises(BinaryFormatError):
        view.bytes_at(-1, 2)
    assert view.cstring(0, 2) == "\x01\x02"


def test_entropy() -> None:
    assert shannon_entropy(b"\x00" * 1000) == 0.0
    rng = random.Random(1)
    noisy = bytes(rng.getrandbits(8) for _ in range(65536))
    assert shannon_entropy(noisy) > 7.9
    profile = entropy_profile(b"\x00" * len(noisy) + noisy, blocks=2)
    assert profile["highEntropyBlocks"] == 1
    assert profile["profile"][0]["entropy"] == 0.0
    assert profile["profile"][1]["offset"] == len(noisy)


def test_entropy_sampling_marks_large_inputs() -> None:
    profile = entropy_profile(b"ab" * 100_000, blocks=2, sample_bytes=1024)
    assert profile["sampled"] is True
    assert profile["overall"] == pytest.approx(1.0)


def test_hexdump_layout() -> None:
    dump = hexdump(b"ELF!" + bytes(range(20)), length=16)
    first = dump.splitlines()[0]
    assert first.startswith("00000000  45 4c 46 21")
    assert first.endswith("|ELF!............|")
    assert dump.splitlines()[-1] == "00000010"
    tail = hexdump(b"0123456789", offset=-4)
    assert tail.startswith("00000006  36 37 38 39")


def test_file_hashes() -> None:
    hashes = file_hashes(b"abc")
    assert hashes["sha256"].startswith("ba7816bf")
    assert hashes["md5"] == "900150983cd24fb0d6963f7d28e17f72"


def test_strings_extraction_and_classification() -> None:
    blob = (
        b"\x00\x01https://evil.example.com/payload\x00"
        + "C:\\Windows\\System32\\cmd.exe".encode("utf-16-le")
        + b"\x00\x00ok\x00HKEY_LOCAL_MACHINE\\Software\\Run\x00"
    )
    found = extract_strings(blob)
    encodings = {(s["encoding"], s["value"]) for s in found}
    assert ("ascii", "https://evil.example.com/payload") in encodings
    assert ("utf16le", "C:\\Windows\\System32\\cmd.exe") in encodings
    assert all(s["value"] != "ok" for s in found)  # below min length
    assert "url" in classify_string("see https://x.io/a")
    assert "registry-key" in classify_string("HKLM\\Software")


def test_strings_redact_secrets() -> None:
    key = "AKIA" + "ABCDEFGHIJKLMNOP"
    summary = analyze_strings(f"\x00config {key} end\x00".encode())
    assert summary["secrets"][0]["rule"] == "aws-access-key"
    assert key not in str(summary)
    assert summary["interesting"][0]["value"] == "[redacted secret]"


# --------------------------------------------------------------------------- ELF


def test_parse_elf_dynamic_info() -> None:
    elf = parse_elf(build_elf(needed=("libssl.so.3", "libc.so.6"), soname="libfoo.so.1"))
    assert elf["class"] == "ELF64"
    assert elf["machine"] == "x86-64"
    assert elf["interpreter"] == "/lib64/ld-linux-x86-64.so.2"
    assert elf["neededLibraries"] == ["libssl.so.3", "libc.so.6"]
    assert elf["soname"] == "libfoo.so.1"
    assert elf["importedSymbols"] == ["__printf_chk", "__stack_chk_fail", "puts"]
    assert elf["exportedSymbols"] == ["main"]
    assert elf["hardening"] == {
        "nx": True,
        "pie": "yes",
        "relro": "full",
        "stackCanary": True,
        "fortifySource": True,
        "stripped": True,
        "dynamicallyLinked": True,
        "rpath": None,
    }


def _categories(data: bytes, tmp_path: Path, name: str = "bin") -> set[str]:
    target = tmp_path / name
    target.write_bytes(data)
    return {f["category"] for f in inspect_file(target)["findings"]}


def test_hardened_elf_has_no_findings(tmp_path: Path) -> None:
    assert _categories(build_elf(), tmp_path) == set()


def test_weak_elf_findings(tmp_path: Path) -> None:
    weak = build_elf(
        e_type=2,
        stack_exec=True,
        relro=False,
        bind_now=False,
        imports=("puts",),
        runpath="lib:/opt/x",
    )
    assert _categories(weak, tmp_path) == {
        "executable_stack",
        "no_pie",
        "no_relro",
        "no_stack_canary",
        "insecure_rpath",
    }
    partial = parse_elf(build_elf(bind_now=False))
    assert partial["hardening"]["relro"] == "partial"
    no_stack_header = parse_elf(build_elf(gnu_stack=False))
    assert no_stack_header["hardening"]["nx"] is False


def test_shared_library_is_not_flagged_as_no_pie() -> None:
    lib = parse_elf(build_elf(interp=False, soname="libx.so"))
    assert lib["hardening"]["pie"] == "shared-library"


# --------------------------------------------------------------------------- PE


def test_parse_pe() -> None:
    pe = parse_pe(build_pe())
    assert pe["format"] == "PE32+"
    assert pe["machine"] == "x86-64"
    assert pe["kind"] == "EXE"
    assert pe["subsystem"] == "Windows console"
    assert pe["compiledAt"] == "2023-11-14T22:13:20Z"
    assert pe["imports"] == [{"library": "KERNEL32.dll", "functions": ["CreateFileW", "ordinal#7"]}]
    assert pe["hardening"]["aslr"] and pe["hardening"]["dep"]
    assert pe["hardening"]["controlFlowGuard"]


def test_pe_findings(tmp_path: Path) -> None:
    weak = build_pe(dll_characteristics=0, section_names=("UPX0", "UPX1"), writable_code=True)
    assert _categories(weak, tmp_path, "weak.exe") == {
        "no_dep",
        "no_aslr",
        "no_high_entropy_va",
        "no_cfg",
        "unsigned",
        "packed",
        "writable_code_section",
    }
    assert _categories(build_pe(signed=True), tmp_path, "good.exe") == set()


# --------------------------------------------------------------------------- Mach-O / WASM


def test_parse_macho() -> None:
    image = parse_macho(build_macho())
    assert image["cpu"] == "x86-64"
    assert image["fileType"] == "executable"
    assert image["linkedLibraries"] == [{"name": "/usr/lib/libSystem.B.dylib", "kind": "load"}]
    assert image["hasMain"] is True


def test_macho_findings(tmp_path: Path) -> None:
    assert _categories(build_macho(pie=False, stack_exec=True), tmp_path) == {
        "no_pie",
        "executable_stack",
    }


def test_parse_wasm() -> None:
    module = parse_wasm(build_wasm())
    assert module["importModules"] == ["wasi_snapshot_preview1"]
    assert {e["name"] for e in module["exports"]} == {"_start", "memory"}
    assert module["definedFunctionCount"] == 1
    assert module["producers"] == {"language": ["Rust 1.80"]}
    assert module["toolchain"] == "Rust 1.80"


# --------------------------------------------------------------------------- robustness


@pytest.mark.parametrize("builder", [build_elf, build_pe, build_macho, build_wasm])
def test_truncated_and_mutated_inputs_never_crash(builder, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    original = builder()
    rng = random.Random(42)
    target = tmp_path / "sample"
    cases = [original[:cut] for cut in range(0, len(original), max(1, len(original) // 40))]
    for _ in range(60):
        mutated = bytearray(original)
        for _ in range(8):
            mutated[rng.randrange(len(mutated))] = rng.getrandbits(8)
        cases.append(bytes(mutated))
    for case in cases:
        target.write_bytes(case)
        report = inspect_file(target)
        assert "findings" in report
        assert isinstance(report["errors"], list)


def test_inspect_python_interpreter() -> None:
    """The running interpreter is a real ELF, Mach-O, or PE depending on the CI runner."""
    report = inspect_file(Path(sys.executable).resolve())
    assert report["format"]["category"] == "executable"
    assert report["errors"] == []
    assert report["details"] is not None


def test_findings_numbering_and_shape() -> None:
    report = {
        "path": "/x/app",
        "format": {"format": "pe", "category": "executable"},
        "details": parse_pe(build_pe(dll_characteristics=0)),
    }
    findings = build_binary_findings(report, start=5)
    assert findings[0]["id"] == "BIN-005"
    assert all(f["domain"] == "binary" and f["file"] == "/x/app" for f in findings)


def test_inspect_file_rejects_directories(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        inspect_file(tmp_path)


def test_parse_fat_macho_and_rpath() -> None:
    from tests.binary_samples import build_fat_macho

    fat = parse_macho(build_fat_macho())
    assert fat["universal"] is True
    assert [arch["cpu"] for arch in fat["architectures"]] == ["x86-64", "ARM64"]
    image = fat["architectures"][1]["image"]
    assert image["rpaths"] == ["@loader_path/../lib"]
    assert image["segments"][0]["name"] == "__TEXT"
    assert image["segments"][0]["protection"] == "R-X"
    assert "entropy" in image["segments"][0]


def test_inspect_fat_macho_findings(tmp_path: Path) -> None:
    from tests.binary_samples import build_fat_macho

    target = tmp_path / "universal"
    target.write_bytes(build_fat_macho())
    report = inspect_file(target)
    assert report["format"]["format"] == "macho-fat"
    assert report["findings"] == []


def test_wasm_toolchain_guesses() -> None:
    from archmap.core.binary.wasm import _guess_toolchain

    assert _guess_toolchain(["wasi_snapshot_preview1"], {}) == "WASI"
    assert _guess_toolchain(["wbg"], {}) == "Rust (wasm-bindgen)"
    assert _guess_toolchain(["go"], {}) == "Go"
    assert _guess_toolchain(["env"], {}).startswith("Emscripten")
    assert _guess_toolchain([], {}) is None
