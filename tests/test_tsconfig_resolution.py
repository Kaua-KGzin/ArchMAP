"""tsconfig/jsconfig module resolution: `extends`, per-package configs, caching."""

from __future__ import annotations

import json

from archmap.core.parser import parse_project


def _deps(files: dict[str, str], importer: str) -> set[str]:
    parsed = {f["id"]: f for f in parse_project(".", virtual_files=files)["parsedFiles"]}
    return {d["id"] for d in parsed[importer]["dependencies"]}


def test_paths_inherited_through_extends() -> None:
    files = {
        "tsconfig.json": json.dumps({"extends": "./tsconfig.base.json"}),
        "tsconfig.base.json": json.dumps({
            "compilerOptions": {"baseUrl": ".", "paths": {"@app/*": ["src/*"]}}
        }),
        "src/main.ts": "import { util } from '@app/util';\n",
        "src/util.ts": "export const util = 1;\n",
    }
    assert _deps(files, "src/main.ts") == {"src/util.ts"}


def test_extended_base_url_is_relative_to_the_file_that_sets_it() -> None:
    # TypeScript resolves baseUrl against the config that declares it, not
    # against the config that extends it.
    files = {
        "tsconfig.json": json.dumps({"extends": "./config/tsconfig.base.json"}),
        "config/tsconfig.base.json": json.dumps({"compilerOptions": {"baseUrl": "../src"}}),
        "src/main.ts": "import { util } from 'lib/util';\n",
        "src/lib/util.ts": "export const util = 1;\n",
    }
    assert _deps(files, "src/main.ts") == {"src/lib/util.ts"}


def test_child_paths_replace_parent_paths() -> None:
    files = {
        "tsconfig.json": json.dumps({
            "extends": "./tsconfig.base.json",
            "compilerOptions": {"paths": {"@x/*": ["b/*"]}},
        }),
        "tsconfig.base.json": json.dumps({"compilerOptions": {"paths": {"@x/*": ["a/*"]}}}),
        "main.ts": "import { m } from '@x/mod';\n",
        "a/mod.ts": "export const m = 'a';\n",
        "b/mod.ts": "export const m = 'b';\n",
    }
    assert _deps(files, "main.ts") == {"b/mod.ts"}


def test_monorepo_package_uses_its_own_tsconfig() -> None:
    # Without baseUrl, `paths` targets are relative to the tsconfig that
    # holds them (TypeScript 4.1+). The nearest config to the importer wins.
    files = {
        "tsconfig.json": json.dumps({"compilerOptions": {"paths": {"@/*": ["shared/*"]}}}),
        "packages/web/tsconfig.json": json.dumps({
            "compilerOptions": {"paths": {"@/*": ["./src/*"]}}
        }),
        "packages/web/src/app.ts": "import { x } from '@/lib/x';\n",
        "packages/web/src/lib/x.ts": "export const x = 1;\n",
        "shared/lib/x.ts": "export const x = 2;\n",
        "tool.ts": "import { x } from '@/lib/x';\n",
    }
    assert _deps(files, "packages/web/src/app.ts") == {"packages/web/src/lib/x.ts"}
    assert _deps(files, "tool.ts") == {"shared/lib/x.ts"}


def test_extends_cycle_does_not_hang() -> None:
    files = {
        "tsconfig.json": json.dumps({
            "extends": "./b.json",
            "compilerOptions": {"paths": {"@a/*": ["src/*"]}},
        }),
        "b.json": json.dumps({"extends": "./tsconfig.json"}),
        "src/main.ts": "import { u } from '@a/u';\n",
        "src/u.ts": "export const u = 1;\n",
    }
    assert _deps(files, "src/main.ts") == {"src/u.ts"}


class _CountingFiles(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reads: dict[str, int] = {}

    def get(self, key, default=None):
        self.reads[key] = self.reads.get(key, 0) + 1
        return super().get(key, default)


def test_tsconfig_is_read_once_per_project_not_once_per_file() -> None:
    files = _CountingFiles({
        "tsconfig.json": json.dumps({"compilerOptions": {"baseUrl": "."}}),
        **{f"src/m{i}.ts": f"import {{ x }} from './m{i + 1}';\n" for i in range(20)},
    })
    parse_project(".", virtual_files=files)
    assert files.reads.get("tsconfig.json", 0) == 1
