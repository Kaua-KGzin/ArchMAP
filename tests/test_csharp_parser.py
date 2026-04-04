from __future__ import annotations

from archmap.core.parser.csharp_parser import CSharpParser
from archmap.core.parser.project_parser import parse_project


def test_csharp_parser_regex_extraction() -> None:
    source = """
    using System;
    using System.Collections.Generic;
    using static System.Math;
    using MyApp.Core.Services;
    using MyApp.Models;

    namespace MyApp.App {
        public class Program {
        }
    }
    """

    parser = CSharpParser()
    imports = parser.parse(source)

    assert imports == [
        "MyApp.Core.Services",
        "MyApp.Models",
        "System",
        "System.Collections.Generic",
        "static System.Math",
    ]


def test_csharp_resolution_namespace_directory() -> None:
    virtual_files = {
        "src/MyApp.App/Program.cs": "using MyApp.Core.Services;\n",
        "src/MyApp.Core/Services/UserService.cs": "namespace MyApp.Core.Services {}\n",
        "src/MyApp.Core/Services/AuthService.cs": "namespace MyApp.Core.Services {}\n",
        "src/MyApp.Models/User.cs": "namespace MyApp.Models {}\n",
    }

    result = parse_project(".", virtual_files=virtual_files)
    parsed = {f["id"]: f for f in result["parsedFiles"]}

    deps = parsed["src/MyApp.App/Program.cs"]["dependencies"]
    dep_ids = {d["id"] for d in deps}

    assert len(deps) == 2
    assert "src/MyApp.Core/Services/UserService.cs" in dep_ids
    assert "src/MyApp.Core/Services/AuthService.cs" in dep_ids


def test_csharp_resolution_stdlib_and_fallback() -> None:
    virtual_files = {
        "App.cs": (
            "using System.Collections.Generic;\n"
            "using Microsoft.AspNetCore.Mvc;\n"
            "using Newtonsoft.Json;\n"
        ),
    }

    result = parse_project(".", virtual_files=virtual_files)
    parsed = {f["id"]: f for f in result["parsedFiles"]}

    deps = parsed["App.cs"]["dependencies"]
    dep_ids = {d["id"] for d in deps}

    assert len(deps) == 3
    # Standard libraries and external packages should fallback to pkg:
    assert "pkg:System.Collections.Generic" in dep_ids
    assert "pkg:Microsoft.AspNetCore.Mvc" in dep_ids
    assert "pkg:Newtonsoft.Json" in dep_ids
