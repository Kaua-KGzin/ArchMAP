"""Single-file inspection: identify, parse, measure, and turn results into findings."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from archmap.core.binary.elf import parse_elf
from archmap.core.binary.entropy import HIGH_ENTROPY, entropy_profile
from archmap.core.binary.formats import detect_format
from archmap.core.binary.macho import parse_macho
from archmap.core.binary.pe import parse_pe
from archmap.core.binary.reader import BinaryFormatError, ByteSource, file_hashes, open_binary
from archmap.core.binary.strings import analyze_strings
from archmap.core.binary.wasm import parse_wasm
from archmap.types import Finding

_PARSERS: dict[str, Callable[[ByteSource], dict[str, Any]]] = {
    "elf": parse_elf,
    "pe": parse_pe,
    "macho": parse_macho,
    "macho-fat": parse_macho,
    "wasm": parse_wasm,
}
# Text formats get a data summary instead of a strings dump.
_STRINGS_CATEGORIES = {"executable", "bytecode", "data", "database", "archive", "capture"}

BASE_LIMITATIONS = [
    "Static inspection only: nothing is executed, disassembled, or decompiled.",
    "Mitigation flags come from headers and imports; they show what the binary "
    "requests, not what the target kernel/loader enforces.",
]


def inspect_file(
    path: str | Path,
    *,
    include_strings: bool = True,
    max_interesting_strings: int = 100,
    entropy_blocks: int = 64,
    entropy_sample_bytes: int = 64 * 1024,
) -> dict[str, Any]:
    """Inspect one file of any type and return a JSON-serialisable report."""
    # Imported lazily: data inspection pulls in sqlite3/csv/tarfile.
    from archmap.core.inspect.data import inspect_data

    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"not a file: {file_path}")

    errors: list[str] = []
    with open_binary(file_path) as data:
        fmt = detect_format(data, file_path.name)
        report: dict[str, Any] = {
            "path": str(file_path),
            "name": file_path.name,
            "size": len(data),
            "hashes": file_hashes(data),
            "format": fmt,
        }
        entropy = entropy_profile(
            data, blocks=entropy_blocks, sample_bytes=entropy_sample_bytes
        )
        report["entropy"] = entropy

        details: dict[str, Any] | None = None
        parser = _PARSERS.get(fmt["format"])
        if parser is not None:
            try:
                details = parser(data)
            except BinaryFormatError as exc:
                errors.append(f"{fmt['format']} parser: {exc}")
        report["details"] = details

        if include_strings and fmt["category"] in _STRINGS_CATEGORIES:
            report["strings"] = analyze_strings(data, max_interesting=max_interesting_strings)

    data_summary = inspect_data(file_path, fmt["format"])
    if data_summary is not None:
        report["data"] = data_summary

    limitations = list(BASE_LIMITATIONS)
    if details:
        limitations.extend(details.get("limitations", []))
    report["limitations"] = limitations
    report["errors"] = errors
    report["findings"] = build_binary_findings(report)
    return report


def build_binary_findings(report: dict[str, Any], start: int = 1) -> list[Finding]:
    """Derive ``BIN-*`` findings (mitigations, packing, embedded secrets)."""
    findings: list[Finding] = []
    path = report.get("path", "")
    fmt = report.get("format", {}).get("format")
    details = report.get("details") or {}

    def add(category: str, severity: str, confidence: float, message: str, *evidence: str) -> None:
        findings.append(
            Finding(
                id=f"BIN-{start + len(findings):03d}",
                domain="binary",
                category=category,
                severity=severity,
                confidence=confidence,
                message=f"{Path(path).name}: {message}",
                evidence=[f"File: {path}", *evidence],
                file=path,
            )
        )

    if fmt == "elf":
        _elf_findings(details, add)
    elif fmt == "pe":
        _pe_findings(details, add)
    elif fmt in ("macho", "macho-fat"):
        images = [details] if not details.get("universal") else [
            arch["image"] for arch in details.get("architectures", []) if "image" in arch
        ]
        for image in images[:1]:
            _macho_findings(image, add)

    entropy = report.get("entropy", {})
    category = report.get("format", {}).get("category")
    if category in ("data",) and float(entropy.get("overall", 0.0)) >= HIGH_ENTROPY:
        add(
            "high_entropy_data",
            "info",
            0.7,
            f"unidentified data with entropy {entropy.get('overall')} bits/byte "
            "(likely compressed or encrypted)",
        )

    for secret in report.get("strings", {}).get("secrets", [])[:10]:
        add(
            "embedded_secret",
            str(secret.get("severity", "medium")),
            float(secret.get("confidence", 0.5)),
            f"embedded {secret.get('name')} in {secret.get('encoding')} string",
            f"Offset: {int(secret.get('offset', 0)):#x}",
            f"Value (redacted): {secret.get('redacted')}",
        )

    data = report.get("data") or {}
    for warning in data.get("warnings", []):
        add("suspicious_container", "medium", 0.9, warning)
    return findings


_Add = Callable[..., None]


def _elf_findings(details: dict[str, Any], add: _Add) -> None:
    hardening = details.get("hardening") or {}
    elf_type = str(details.get("type", ""))
    if not elf_type.startswith(("EXEC", "DYN")):
        return
    if hardening.get("nx") is False:
        add("executable_stack", "high", 0.95,
            "stack is executable (missing or RWX PT_GNU_STACK)", "Mitigation: NX")
    if hardening.get("pie") == "no":
        add("no_pie", "medium", 0.95,
            "not position-independent; loads at a fixed address and weakens ASLR",
            "Mitigation: PIE")
    if hardening.get("relro") == "none":
        add("no_relro", "low", 0.95, "no RELRO; GOT stays writable at runtime",
            "Mitigation: RELRO")
    if hardening.get("dynamicallyLinked") and not hardening.get("stackCanary"):
        add("no_stack_canary", "low", 0.6,
            "no __stack_chk_fail import; stack protector likely disabled",
            "Mitigation: stack canary (heuristic: small functions may legitimately omit it)")
    rpath = hardening.get("rpath")
    if rpath:
        risky = [
            entry for entry in str(rpath).split(":")
            if not entry or not entry.startswith(("/", "$ORIGIN", "${ORIGIN}"))
        ]
        if risky:
            add("insecure_rpath", "medium", 0.9,
                "RPATH/RUNPATH contains relative or empty entries (library hijacking)",
                f"RPATH: {rpath}")


def _pe_findings(details: dict[str, Any], add: _Add) -> None:
    hardening = details.get("hardening") or {}
    if hardening.get("dep") is False:
        add("no_dep", "high", 0.95, "DEP/NX_COMPAT not enabled", "Mitigation: DEP")
    if hardening.get("aslr") is False:
        add("no_aslr", "medium", 0.95, "DYNAMIC_BASE not set; ASLR disabled",
            "Mitigation: ASLR")
    if hardening.get("highEntropyVA") is False:
        add("no_high_entropy_va", "low", 0.9, "64-bit image without high-entropy ASLR",
            "Mitigation: HIGH_ENTROPY_VA")
    if hardening.get("controlFlowGuard") is False and not details.get("dotnet"):
        add("no_cfg", "low", 0.8, "Control Flow Guard not enabled", "Mitigation: CFG")
    if hardening.get("signed") is False:
        add("unsigned", "info", 0.9, "no Authenticode signature present")
    for packer in details.get("packers", []):
        add("packed", "medium", 0.9, f"packed with {packer} (section names)",
            "Packed code hides its real imports and strings from static analysis")
    high = details.get("highEntropyCodeSections", [])
    if high and not details.get("packers"):
        add("possibly_packed", "medium", 0.6,
            f"executable section(s) {', '.join(high)} have entropy >= {HIGH_ENTROPY}")
    writable = details.get("writableCodeSections", [])
    if writable:
        add("writable_code_section", "high", 0.9,
            f"section(s) {', '.join(writable)} are both writable and executable")


def _macho_findings(image: dict[str, Any], add: _Add) -> None:
    hardening = image.get("hardening") or {}
    if hardening.get("stackExecutable"):
        add("executable_stack", "high", 0.95, "MH_ALLOW_STACK_EXECUTION is set")
    if image.get("fileType") == "executable" and not hardening.get("pie"):
        add("no_pie", "medium", 0.95, "executable is not PIE")
    if hardening.get("encrypted"):
        add("encrypted", "info", 0.95,
            "binary is FairPlay-encrypted; code is not statically readable")
