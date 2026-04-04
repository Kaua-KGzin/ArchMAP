from __future__ import annotations

from archmap.core.parser.project_parser import parse_project


def test_go_resolution_with_gomod() -> None:
    virtual_files = {
        "go.mod": "module github.com/user/project\n\ngo 1.20",
        "main.go": 'package main\nimport "github.com/user/project/core/config"\n',
        "core/config/config.go": "package config\n",
        "core/config/utils.go": "package config\n",
    }

    result = parse_project(".", virtual_files=virtual_files)
    parsed = {f["id"]: f for f in result["parsedFiles"]}

    main_deps = parsed["main.go"]["dependencies"]
    # It should resolve to the two local files instead of a generic package
    dep_ids = {d["id"] for d in main_deps}
    assert "core/config/config.go" in dep_ids
    assert "core/config/utils.go" in dep_ids
    assert "pkg:github.com/user/project/core/config" not in dep_ids


def test_go_resolution_without_gomod() -> None:
    virtual_files = {
        "main.go": 'package main\nimport "github.com/user/project/core/config"\n',
        "core/config/config.go": "package config\n",
        "core/config/utils.go": "package config\n",
    }

    result = parse_project(".", virtual_files=virtual_files)
    parsed = {f["id"]: f for f in result["parsedFiles"]}

    main_deps = parsed["main.go"]["dependencies"]
    # Without go.mod, it doesn't know the module name, so it falls back to pkg:
    dep_ids = {d["id"] for d in main_deps}
    assert "pkg:github.com/user/project/core/config" in dep_ids
    assert "core/config/config.go" not in dep_ids


def test_go_resolution_external() -> None:
    virtual_files = {
        "go.mod": "module github.com/user/project\n",
        "main.go": 'package main\nimport "github.com/gin-gonic/gin"\n',
    }

    result = parse_project(".", virtual_files=virtual_files)
    parsed = {f["id"]: f for f in result["parsedFiles"]}

    main_deps = parsed["main.go"]["dependencies"]
    dep_ids = {d["id"] for d in main_deps}
    # External package remains a pkg: dependency
    assert "pkg:github.com/gin-gonic/gin" in dep_ids


def test_go_resolution_root_package() -> None:
    virtual_files = {
        "go.mod": "module myapp\n",
        "main.go": 'package main\nimport "myapp"\n',
        "root.go": "package myapp\n",
    }

    result = parse_project(".", virtual_files=virtual_files)
    parsed = {f["id"]: f for f in result["parsedFiles"]}

    main_deps = parsed["main.go"]["dependencies"]
    dep_ids = {d["id"] for d in main_deps}
    assert "root.go" in dep_ids
    assert "pkg:myapp" not in dep_ids
