"""Regressions found by running ArchMAP against real NestJS / Next.js / C# repos."""

from __future__ import annotations

import json
from pathlib import Path

from archmap.cli.args import build_parser
from archmap.core.parser import parse_project


def _parsed(files: dict[str, str]) -> dict[str, dict]:
    return {f["id"]: f for f in parse_project(".", virtual_files=files)["parsedFiles"]}


def test_dotted_basenames_resolve() -> None:
    # NestJS/Angular naming: `.service`, `.controller`, `.module` are part of
    # the basename, not the extension. These used to be 100% unresolved.
    parsed = _parsed({
        "src/app.module.ts": (
            "import { UserService } from './users/user.service';\n"
            "import { UsersModule } from './users/users.module';\n"
        ),
        "src/users/user.service.ts": "export class UserService {}\n",
        "src/users/users.module.ts": "export class UsersModule {}\n",
    })
    app = parsed["src/app.module.ts"]
    assert {d["id"] for d in app["dependencies"]} == {
        "src/users/user.service.ts",
        "src/users/users.module.ts",
    }
    assert app["unresolvedImports"] == []


def test_esm_js_specifier_maps_to_ts_source() -> None:
    parsed = _parsed({
        "src/index.ts": "import { x } from './util.js';\n",
        "src/util.ts": "export const x = 1;\n",
    })
    assert {d["id"] for d in parsed["src/index.ts"]["dependencies"]} == {"src/util.ts"}


def test_asset_imports_are_not_unresolved() -> None:
    parsed = _parsed({
        "app/layout.tsx": "import './globals.css';\nimport logo from './logo.svg?url';\n",
    })
    assert parsed["app/layout.tsx"]["unresolvedImports"] == []


def test_build_output_import_maps_back_to_source() -> None:
    parsed = _parsed({
        "tsconfig.json": json.dumps({
            "compilerOptions": {"outDir": "./dist", "baseUrl": "./"},
            "include": ["src/**/*"],
        }),
        "api/index.js": "const { AppModule } = require('../dist/app.module');\n",
        "src/app.module.ts": "export class AppModule {}\n",
    })
    assert {d["id"] for d in parsed["api/index.js"]["dependencies"]} == {"src/app.module.ts"}


def test_show_unresolved_accepts_all() -> None:
    args = build_parser().parse_args(["analyze", ".", "--show-unresolved=all"])
    assert args.show_unresolved >= 1_000_000


def test_no_cache_flag_reaches_analysis(monkeypatch, tmp_path: Path) -> None:
    from archmap.cli import commands

    seen: dict[str, object] = {}

    def fake_analyze(path, parallel=None, use_cache=True):
        seen["use_cache"] = use_cache
        raise SystemExit(0)

    monkeypatch.setattr(commands, "analyze_project", fake_analyze)
    args = build_parser().parse_args(["analyze", str(tmp_path), "--no-cache"])
    try:
        commands.run_analyze(args)
    except SystemExit:
        pass
    assert seen["use_cache"] is False


def test_cache_fingerprint_changes_with_version(monkeypatch, tmp_path: Path) -> None:
    import archmap
    from archmap.cache import compute_fingerprint

    (tmp_path / "a.py").write_text("import os\n")
    before = compute_fingerprint(tmp_path, {})
    monkeypatch.setattr(archmap, "__version__", "999.0.0")
    assert compute_fingerprint(tmp_path, {}) != before
