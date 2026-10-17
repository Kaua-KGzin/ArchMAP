# archmap inspect / hexdump / strings

Static reverse engineering for any file or folder: identify it, parse it,
measure it, and report what matters — without executing anything and
without external tools. Pure Python standard library, so it runs the same
on Linux, macOS, Windows, and Termux.

## archmap inspect

```bash
archmap inspect <file-or-directory> [--json] [--out PATH] [--no-strings]
                [--max-strings N] [--max-files N] [--fail-on SEVERITY]
```

### What a file report contains

| Section | Content |
|---|---|
| `format` | Identified by magic bytes: ELF, PE, Mach-O (thin/universal), WebAssembly, DEX, Java class, `.pyc`, APK/JAR/DOCX/XLSX/PPTX, ZIP, tar, gzip/bzip2/xz/zstd, 7z, RAR, SQLite, PDF, images, pcap/pcapng, LLVM bitcode, Lua bytecode, scripts, JSON/CSV/XML/text |
| `hashes` | MD5, SHA-1, SHA-256 (the identifiers threat-intel databases use) |
| `details` | Format-specific parse — see below |
| `entropy` | Overall bits/byte, classification, and a per-block profile (spot appended or encrypted payloads) |
| `strings` | ASCII + UTF-16LE strings, classified (URL, IPv4, e-mail, Windows/Unix path, registry key, shell command, crypto, library, build toolchain, format string, secret). Secrets are redacted |
| `data` | Schema/content summary for JSON, JSONL, CSV/TSV, SQLite, archives |
| `findings` | `BIN-*` findings in the unified findings model |
| `limitations` / `errors` | What the static view cannot tell you, and any parse problems (a malformed file degrades the report; it never crashes the tool) |

### Executable formats

| Format | Parsed |
|---|---|
| **ELF** | class, endianness, OS ABI, type, machine, entry point, interpreter, segments, sections (with entropy), `DT_NEEDED` libraries, SONAME, RPATH/RUNPATH, imported/exported symbols, language hint (Go, Rust, C++) |
| **PE** | PE32/PE32+, machine, EXE/DLL, subsystem, compile timestamp, image base, sections (with entropy), imports and delay imports per DLL (names and ordinals), exports, .NET marker, Authenticode presence, packer hints (UPX, ASPack, MPRESS, Themida, VMProtect, ...) |
| **Mach-O** | thin and universal binaries, CPU per slice, file type, linked dylibs (load/weak/reexport/lazy), install name, rpaths, segments (with entropy), code signature and encryption flags |
| **WebAssembly** | sections, imports per module, exports, function count, custom sections, `producers` metadata (language and compiler versions), toolchain guess (WASI, wasm-bindgen, Go, Emscripten) |

### Mitigation checks (`BIN-*` findings)

| Format | Checks |
|---|---|
| ELF | executable stack (NX), PIE, RELRO (none/partial/full), stack canary, FORTIFY_SOURCE, relative/empty RPATH entries |
| PE | DEP, ASLR, high-entropy ASLR, Control Flow Guard, Authenticode signature, packers, high-entropy code sections, writable+executable sections |
| Mach-O | PIE, executable stack, FairPlay encryption |
| Any | embedded secrets in strings, high-entropy unidentified data, unsafe archives (zip-slip paths, links escaping the archive, setuid files, device nodes, decompression bombs) |

Mitigation flags describe what the binary *requests*; the target kernel or
loader decides what is enforced. Each finding carries a `confidence` (for
example, a missing `__stack_chk_fail` import is only a hint, so it scores
0.6).

### Directories

Pointing `inspect` at a directory (an unpacked firmware image, an APK's
`lib/`, a Docker layer, a `dist/` folder) classifies every file and builds a
**binary linkage graph**: each executable's library imports become edges,
and libraries found inside the directory (by file name or SONAME/install
name) resolve to real files.

```bash
archmap inspect ./rootfs --json | jq '.mostLinkedLibraries'
```

The result has `byFormat`, `byCategory`, `binaries` (with hardening per
binary), `graph` (`nodes`/`edges`), `mostLinkedLibraries`, and all
`BIN-*` findings renumbered across the tree.

### CI gate

```bash
# Fail the build if any shipped binary lacks NX/DEP or is packed
archmap inspect dist/ --fail-on high
```

Exit code `2` means a finding at or above the given severity was reported.

## archmap hexdump

```bash
archmap hexdump <file> [-s OFFSET] [-n LENGTH] [-w WIDTH]
```

Canonical `hexdump -C` layout. Offsets and lengths accept `0x` hex; a
negative offset counts from the end of the file (`-s -64` dumps the last 64
bytes — trailers, overlays, appended payloads). Output is capped at 64 KiB.

```text
$ archmap hexdump /bin/ls -n 32
00000000  7f 45 4c 46 02 01 01 00  00 00 00 00 00 00 00 00  |.ELF............|
00000010  03 00 3e 00 01 00 00 00  30 6d 00 00 00 00 00 00  |..>.....0m......|
00000020
```

## archmap strings

```bash
archmap strings <file> [-n MIN] [--encoding ascii|utf16le|both]
                [--interesting] [--offsets] [--limit N] [--json]
```

Like `strings(1)`, extracting both ASCII and UTF-16LE (how Windows binaries
store text). Unlike `strings -el`, a UTF-16 run that starts inside an ASCII
string (the last ASCII character plus its NUL terminator) is trimmed.

`--interesting` keeps only classified strings — the 30 that matter instead
of 30,000:

```text
$ archmap strings jansi.dll --interesting
0x00005350  [build-toolchain] GCC: (GNU) 11.2.0
0x00006800  [library,build-toolchain] msvcrt.dll
0x00007854  [unix-path,build-toolchain] /usr/src/mxe/tmp-gcc-i686-w64-mingw32.static/...
```

## Performance

Entropy is sampled (at most 64 KiB per block, profile and overall derived
from the same histograms) because byte counting dominates the cost. On a
typical Linux machine, inventorying 400 shared libraries takes about 6
seconds.
