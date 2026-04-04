from __future__ import annotations

from archmap.core.parser.cpp_parser import CppParser
from archmap.core.parser.project_parser import parse_project


def test_cpp_parser_regex_extraction() -> None:
    source = """
    #include <iostream>
    #include <vector>
    #include "utils/helper.h"
    #include "local.hpp"

    int main() {
        return 0;
    }
    """

    # C and Cpp parser share the same extraction logic
    parser = CppParser()
    imports = parser.parse(source)

    assert imports == [
        {"type": "system", "value": "iostream"},
        {"type": "system", "value": "vector"},
        {"type": "local", "value": "utils/helper.h"},
        {"type": "local", "value": "local.hpp"},
    ]


def test_cpp_resolution_system_includes() -> None:
    virtual_files = {
        "src/main.cpp": "#include <stdio.h>\n#include <string>\n",
    }

    result = parse_project(".", virtual_files=virtual_files)
    parsed = {f["id"]: f for f in result["parsedFiles"]}

    deps = parsed["src/main.cpp"]["dependencies"]
    dep_ids = {d["id"] for d in deps}

    assert len(deps) == 2
    assert "pkg:stdio.h" in dep_ids
    assert "pkg:string" in dep_ids


def test_cpp_resolution_local_includes() -> None:
    virtual_files = {
        "src/main.cpp": '#include "local.h"\n#include "../include/sys.h"\n#include "global.h"\n',
        "src/local.h": "// local header\n",
        "include/sys.h": "// sys header\n",
        "global.h": "// root global header\n",
    }

    result = parse_project(".", virtual_files=virtual_files)
    parsed = {f["id"]: f for f in result["parsedFiles"]}

    deps = parsed["src/main.cpp"]["dependencies"]
    dep_ids = {d["id"] for d in deps}

    # 1. "local.h" is relative to "src", so -> "src/local.h"
    # 2. "../include/sys.h" is relative to "src", so -> "include/sys.h"
    # 3. "global.h" is not in "src", so it falls back to root check -> "global.h"
    assert len(deps) == 3
    assert "src/local.h" in dep_ids
    assert "include/sys.h" in dep_ids
    assert "global.h" in dep_ids


def test_cpp_resolution_fallback() -> None:
    virtual_files = {
        "src/main.cpp": '#include "missing.h"\n',
    }

    result = parse_project(".", virtual_files=virtual_files)
    parsed = {f["id"]: f for f in result["parsedFiles"]}

    deps = parsed["src/main.cpp"]["dependencies"]

    assert len(deps) == 1
    # Local string include that doesn't map to any file defaults to pkg:
    assert deps[0]["id"] == "pkg:missing.h"
    assert deps[0]["type"] == "package"
