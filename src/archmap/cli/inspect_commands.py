"""CLI handlers for file/binary inspection, hexdump, strings, audit, and the command catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from archmap.core.analyzer.findings import SEVERITY_LEVELS

# Exit code used by every quality gate in the CLI.
GATE_EXIT_CODE = 2


def _write_json(result: Any, args: argparse.Namespace) -> None:
    out = getattr(args, "out", None)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"[info] Report written to {out}", file=sys.stderr)


def _gate(findings: list[dict[str, Any]], threshold: str | None) -> int:
    """Exit 2 when any finding is at or above ``threshold`` severity."""
    if not threshold:
        return 0
    floor = SEVERITY_LEVELS.index(threshold)
    hits = [f for f in findings if SEVERITY_LEVELS.index(f.get("severity", "info")) >= floor]
    if hits:
        print(
            f"[gate] {len(hits)} finding(s) at or above '{threshold}' severity",
            file=sys.stderr,
        )
        return GATE_EXIT_CODE
    return 0


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def _print_findings(findings: list[dict[str, Any]], limit: int = 25) -> None:
    if not findings:
        print("  Findings: none")
        return
    print(f"  Findings ({len(findings)}):")
    order = {level: index for index, level in enumerate(reversed(SEVERITY_LEVELS))}
    for finding in sorted(findings, key=lambda f: order.get(f.get("severity", "info"), 9))[:limit]:
        print(f"    [{finding['severity']:<8}] {finding['id']}  {finding['message']}")
    if len(findings) > limit:
        print(f"    ...and {len(findings) - limit} more (use --json for all)")


# --------------------------------------------------------------------------- inspect


def run_inspect(args: argparse.Namespace) -> int:
    from archmap.core.binary.analyzer import inspect_file
    from archmap.core.inspect.inventory import inspect_directory

    target = Path(args.path)
    if not target.exists():
        print(f"[error] path does not exist: {target}", file=sys.stderr)
        return 1
    if target.is_dir():
        result = inspect_directory(
            target,
            max_files=args.max_files,
            include_strings=not args.no_strings,
        )
    else:
        result = inspect_file(
            target,
            include_strings=not args.no_strings,
            max_interesting_strings=args.max_strings,
        )
    _write_json(result, args)
    if args.json:
        print(json.dumps(result, indent=2))
    elif target.is_dir():
        _print_inventory(result)
    else:
        _print_file_report(result)
    return _gate(result["findings"], args.fail_on)


def _yes(value: Any) -> str:
    return "yes" if value else "no"


def _print_file_report(report: dict[str, Any]) -> None:
    fmt = report["format"]
    print(f"[ok] {report['path']}")
    print(f"  Type: {fmt['description']} ({fmt['format']}, {fmt['category']}), "
          f"{_human_size(report['size'])}")
    print(f"  SHA-256: {report['hashes']['sha256']}")
    details = report.get("details") or {}
    if fmt["format"] == "elf" and details:
        print(f"  Header: {details['class']} {details['machine']} {details['type']}, "
              f"entry {details['entryPoint']}")
        if details.get("interpreter"):
            print(f"  Interpreter: {details['interpreter']}")
        print(f"  Libraries: {', '.join(details['neededLibraries']) or '(none)'}")
        print(f"  Symbols: {details['importedSymbolCount']} imported, "
              f"{details['exportedSymbolCount']} exported")
        h = details["hardening"]
        print(f"  Hardening: NX {_yes(h['nx'])} | PIE {h['pie']} | RELRO {h['relro']} | "
              f"canary {_yes(h['stackCanary'])} | FORTIFY {_yes(h['fortifySource'])} | "
              f"stripped {_yes(h['stripped'])}")
        if details.get("language"):
            print(f"  Language hint: {details['language']}")
    elif fmt["format"] == "pe" and details:
        print(f"  Header: {details['format']} {details['machine']} {details['kind']}, "
              f"{details['subsystem']}, compiled {details['compiledAt']}"
              f"{', .NET' if details['dotnet'] else ''}")
        print(f"  Libraries: {', '.join(details['importedLibraries']) or '(none)'} "
              f"({details['importedFunctionCount']} imported functions)")
        if details.get("exports"):
            print(f"  Exports: {details['exports']['nameCount']} "
                  f"({details['exports']['dllName']})")
        h = details["hardening"]
        print("  Hardening: " + " | ".join(f"{key} {_yes(value)}" for key, value in h.items()))
        if details.get("packers"):
            print(f"  Packer: {', '.join(details['packers'])}")
    elif fmt["format"] in ("macho", "macho-fat") and details:
        images = [details] if not details.get("universal") else [
            a["image"] for a in details.get("architectures", []) if "image" in a
        ]
        for image in images:
            print(f"  Image: {image['class']} {image['cpu']} {image['fileType']}")
            libs = ", ".join(lib["name"] for lib in image["linkedLibraries"])
            print(f"    Libraries: {libs or '(none)'}")
            print("    Hardening: " + " | ".join(
                f"{key} {_yes(value)}" for key, value in image["hardening"].items()
            ))
    elif fmt["format"] == "wasm" and details:
        print(f"  Module: {len(details['imports'])} imports from "
              f"{', '.join(details['importModules']) or '(none)'}; "
              f"{len(details['exports'])} exports; {details['definedFunctionCount']} functions")
        if details.get("toolchain"):
            print(f"  Toolchain: {details['toolchain']}")

    entropy = report["entropy"]
    print(f"  Entropy: {entropy['overall']} bits/byte ({entropy['classification']})")

    data = report.get("data")
    if data:
        _print_data_summary(data)

    strings = report.get("strings")
    if strings:
        categories = ", ".join(f"{k} {v}" for k, v in strings["byCategory"].items())
        print(f"  Strings: {strings['total']} total{' — ' + categories if categories else ''}")
        for item in strings["interesting"][:12]:
            tags = ",".join(item["categories"])
            print(f"    {item['offset']:#010x}  [{tags}] {item['value'][:90]}")
    _print_findings(report["findings"])
    for error in report.get("errors", []):
        print(f"  [warn] {error}")


def _print_data_summary(data: dict[str, Any]) -> None:
    kind = data.get("kind")
    if data.get("error"):
        print(f"  Data ({kind}): {data['error']}")
        return
    if kind == "sqlite":
        print(f"  SQLite: {data['tableCount']} table(s), {data['viewCount']} view(s), "
              f"{data['indexCount']} index(es)")
        for table in data["tables"][:15]:
            cols = ", ".join(f"{c['name']}:{c['type']}" for c in table["columns"][:8])
            rows = f"{table.get('rows')} rows" if table["type"] == "table" else "view"
            print(f"    {table['name']} ({rows}) — {cols}")
    elif kind == "csv":
        print(f"  CSV: {data['rows']} rows, delimiter {data['delimiter']!r}")
        print("    Columns: " + ", ".join(f"{c['name']}:{c['type']}" for c in data["columns"]))
    elif kind in ("json", "jsonl"):
        schema = json.dumps(data.get("schema"))
        print(f"  {kind.upper()} schema: {schema[:300]}{'…' if len(schema) > 300 else ''}")
    elif kind == "tar":
        print(f"  Tar: {data['members']} members {data['memberTypes']}, "
              f"{_human_size(data['totalSize'])}")
    elif kind == "gzip":
        print(f"  Gzip: original name {data.get('originalName')}, "
              f"{_human_size(data['uncompressedSizeMod32'])} uncompressed")
    else:
        print(f"  Archive ({kind}): {data.get('entries')} entries, "
              f"{_human_size(int(data.get('uncompressedSize', 0)))} uncompressed, "
              f"ratio {data.get('compressionRatio')}:1")
        android = data.get("android")
        if android:
            print(f"    Android: dex {android['dexFiles']}, ABIs {android['abis']}, "
                  f"{len(android['nativeLibraries'])} native libraries")


def _print_inventory(result: dict[str, Any]) -> None:
    truncated = " (truncated)" if result["truncated"] else ""
    print(f"[ok] {result['root']}: {result['filesScanned']} files{truncated}, "
          f"{_human_size(result['totalSize'])}")
    print("  By format: " + ", ".join(f"{k} {v}" for k, v in result["byFormat"].items()))
    binaries = result["binaries"]
    if binaries:
        print(f"  Binaries / containers ({len(binaries)}):")
        for binary in binaries[:20]:
            libs = ", ".join(binary["libraries"][:5])
            more = f" +{len(binary['libraries']) - 5}" if len(binary["libraries"]) > 5 else ""
            print(f"    {binary['file']} [{binary['format']}] {libs}{more}")
        if len(binaries) > 20:
            print(f"    ...and {len(binaries) - 20} more")
    if result["mostLinkedLibraries"]:
        print("  Most linked libraries:")
        for item in result["mostLinkedLibraries"][:10]:
            print(f"    {item['library']} <- {item['dependents']}")
    _print_findings(result["findings"])


# --------------------------------------------------------------------------- hexdump / strings


def _parse_offset(text: str) -> int:
    return int(text, 0)


def run_hexdump(args: argparse.Namespace) -> int:
    from archmap.core.binary.hexdump import hexdump
    from archmap.core.binary.reader import open_binary

    with open_binary(args.file) as data:
        print(hexdump(data, offset=args.offset, length=args.length, width=args.width))
    return 0


def run_strings(args: argparse.Namespace) -> int:
    from archmap.core.binary.reader import open_binary
    from archmap.core.binary.strings import analyze_strings, extract_strings

    encodings = ("ascii", "utf16le") if args.encoding == "both" else (args.encoding,)
    with open_binary(args.file) as data:
        if args.interesting:
            summary = analyze_strings(data, min_length=args.min_length, max_interesting=args.limit)
            if args.json:
                print(json.dumps(summary, indent=2))
                return 0
            for item in summary["interesting"]:
                print(f"{item['offset']:#010x}  [{','.join(item['categories'])}] {item['value']}")
            return 0
        found = extract_strings(
            data, min_length=args.min_length, encodings=encodings, limit=args.limit
        )
    if args.json:
        print(json.dumps(found, indent=2))
        return 0
    for item in found:
        prefix = f"{item['offset']:#010x}  " if args.offsets else ""
        print(f"{prefix}{item['value']}")
    return 0


# --------------------------------------------------------------------------- audit


def run_audit(args: argparse.Namespace) -> int:
    from archmap.core.audit.project_audit import audit_project

    result = audit_project(args.path, include_code=not getattr(args, "no_code", False))
    _write_json(result, args)
    if getattr(args, "sarif", None):
        from archmap.exporters.sarif_exporter import export_findings_as_sarif

        written = export_findings_as_sarif(result["findings"], result["root"], args.sarif)
        print(f"[info] SARIF written to {written}", file=sys.stderr)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        git = "git-aware" if result["gitAware"] else "not a git repository"
        print(f"[ok] Audited {result['filesScanned']} text files in {result['root']} ({git})")
        print(f"  Secrets: {result['secretFindings']} | Code: {result.get('codeFindings', 0)} "
              f"| Agent config: {result['agentFindings']}")
        _print_findings(result["findings"])
        for note in result["limitations"]:
            print(f"  [note] {note}")
    return _gate(result["findings"], args.fail_on)


# --------------------------------------------------------------------------- context


def run_context(args: argparse.Namespace) -> int:
    from archmap.core import analyze_project
    from archmap.core.context.relevance import rank_relevant_files

    report = analyze_project(args.path, parallel=args.parallel)
    result = rank_relevant_files(
        report, args.task, budget_tokens=args.budget, max_files=args.max_files
    )
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    if not result["files"]:
        print("[info] No files matched; use code identifiers in the task description.")
        return 0
    print(f"[ok] {len(result['files'])} file(s), ~{result['usedTokens']} tokens "
          f"(budget {result['budgetTokens']}) for: {result['task']}")
    for index, item in enumerate(result["files"], start=1):
        print(f"  {index:>2}. {item['file']}  [{item['role']}, ~{item['estimatedTokens']} tokens, "
              f"{item['dependents']} dependents]")
        for reason in item["reasons"][:2]:
            print(f"        - {reason}")
        for snippet in item["snippets"][:2]:
            print(f"        L{snippet['line']}: {snippet['text'][:100]}")
    return 0


# --------------------------------------------------------------------------- command catalog


def build_command_catalog(parser: argparse.ArgumentParser) -> dict[str, Any]:
    """Describe every subcommand and its options from the live argparse tree."""
    from archmap import __version__

    commands: list[dict[str, Any]] = []
    for action in parser._actions:  # argparse has no public API for this
        if not isinstance(action, argparse._SubParsersAction):
            continue
        helps = {choice.dest: choice.help for choice in action._choices_actions}
        for name, subparser in action.choices.items():
            options = []
            for sub_action in subparser._actions:
                if isinstance(sub_action, argparse._HelpAction):
                    continue
                options.append({
                    "name": sub_action.option_strings or [sub_action.dest],
                    "positional": not sub_action.option_strings,
                    "help": sub_action.help,
                    "default": None if sub_action.default is argparse.SUPPRESS
                    else sub_action.default,
                    "choices": list(sub_action.choices) if sub_action.choices else None,
                    "takesValue": sub_action.nargs != 0,
                })
            commands.append({"name": name, "help": helps.get(name), "options": options})
    return {"tool": "archmap", "version": __version__, "commands": commands}


def run_commands(args: argparse.Namespace) -> int:
    from archmap.cli.args import build_parser

    catalog = build_command_catalog(build_parser())
    if args.json:
        print(json.dumps(catalog, indent=2, default=str))
        return 0
    for command in catalog["commands"]:
        print(f"  {command['name']:<10} {command['help'] or ''}")
    return 0
