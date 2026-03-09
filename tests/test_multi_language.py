from __future__ import annotations

from archmap.core.parser import parse_project


def _virtual(files: dict[str, str]):
    return parse_project(".", virtual_files=files)

def test_go_imports() -> None:
    virtual = {
        "main.go": 'import "fmt"\nimport (\n\t"os"\n\t"net/http"\n)\n',
    }
    result = _virtual(virtual)
    main_file = result["parsedFiles"][0]
    dep_ids = {d["id"] for d in main_file["dependencies"]}
    assert "pkg:fmt" in dep_ids
    assert "pkg:os" in dep_ids
    assert "pkg:net/http" in dep_ids

def test_php_imports() -> None:
    virtual = {
        "index.php": '<?php\nuse App\\Models\\User;\nrequire_once "config.php";\n',
    }
    result = _virtual(virtual)
    main_file = result["parsedFiles"][0]
    dep_ids = {d["id"] for d in main_file["dependencies"]}
    assert "pkg:App\\Models\\User" in dep_ids
    assert "pkg:config.php" in dep_ids

def test_java_imports() -> None:
    virtual = {
        "Main.java": "import java.util.List;\nimport com.example.service.*;\n",
    }
    result = _virtual(virtual)
    main_file = result["parsedFiles"][0]
    dep_ids = {d["id"] for d in main_file["dependencies"]}
    assert "pkg:java.util.List" in dep_ids
    assert "pkg:com.example.service.*" in dep_ids

def test_cpp_imports() -> None:
    virtual = {
        "main.cpp": '#include <iostream>\n#include "myheader.h"\n',
    }
    result = _virtual(virtual)
    main_file = result["parsedFiles"][0]
    dep_ids = {d["id"] for d in main_file["dependencies"]}
    assert "pkg:iostream" in dep_ids
    assert "pkg:myheader.h" in dep_ids
