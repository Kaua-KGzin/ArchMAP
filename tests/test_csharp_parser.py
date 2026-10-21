from __future__ import annotations

from archmap.core.parser import parse_project as parse_project_main
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

    # `static` is consumed as a directive prefix; the namespace itself is kept.
    assert imports == [
        "MyApp.Core.Services",
        "MyApp.Models",
        "System",
        "System.Collections.Generic",
        "System.Math",
    ]


def test_csharp_resolution_links_only_referenced_types() -> None:
    # A `using` makes the namespace visible; only types actually used become
    # edges. Linking every file of the namespace produced phantom cliques.
    virtual_files = {
        "src/MyApp.App/Program.cs": (
            "using MyApp.Core.Services;\n"
            "var svc = new UserService();\n"
        ),
        "src/MyApp.Core/Services/UserService.cs": (
            "namespace MyApp.Core.Services;\npublic class UserService {}\n"
        ),
        "src/MyApp.Core/Services/AuthService.cs": (
            "namespace MyApp.Core.Services;\npublic class AuthService {}\n"
        ),
        "src/MyApp.Models/User.cs": "namespace MyApp.Models {}\n",
    }

    result = parse_project_main(".", virtual_files=virtual_files)
    parsed = {f["id"]: f for f in result["parsedFiles"]}

    program = parsed["src/MyApp.App/Program.cs"]
    assert {d["id"] for d in program["dependencies"]} == {
        "src/MyApp.Core/Services/UserService.cs"
    }
    assert program["unresolvedImports"] == []


def test_csharp_unused_project_using_is_resolved_without_edges() -> None:
    virtual_files = {
        "App/Program.cs": "using MyApp.Core.Services;\nclass Program {}\n",
        "Core/UserService.cs": "namespace MyApp.Core.Services { public class UserService {} }\n",
    }
    result = parse_project_main(".", virtual_files=virtual_files)
    parsed = {f["id"]: f for f in result["parsedFiles"]}
    assert parsed["App/Program.cs"]["dependencies"] == []
    assert parsed["App/Program.cs"]["unresolvedImports"] == []


def test_csharp_same_namespace_needs_no_using() -> None:
    virtual_files = {
        "Domain/Sale.cs": (
            "namespace Shop.Domain;\n"
            "public class Sale { public List<SaleItem> Items { get; set; } }\n"
        ),
        "Domain/SaleItem.cs": "namespace Shop.Domain;\npublic class SaleItem {}\n",
        "Domain/Unrelated.cs": "namespace Shop.Domain;\npublic class Unrelated {}\n",
        # Parent namespaces are visible from child namespaces.
        "Domain/Pricing/Calc.cs": (
            "namespace Shop.Domain.Pricing;\n"
            "public class Calc { decimal Total(Sale s) => 0; }\n"
        ),
    }
    parsed = {f["id"]: f for f in parse_project(".", virtual_files=virtual_files)["parsedFiles"]}
    assert {d["id"] for d in parsed["Domain/Sale.cs"]["dependencies"]} == {"Domain/SaleItem.cs"}
    assert {d["id"] for d in parsed["Domain/Pricing/Calc.cs"]["dependencies"]} == {
        "Domain/Sale.cs"
    }


def test_csharp_ignores_partials_nested_types_and_enum_members() -> None:
    virtual_files = {
        # EF migration split across two partial files: not a cycle.
        "Migrations/Init.cs": "namespace Db.Migrations;\npublic partial class Init {}\n",
        "Migrations/Init.Designer.cs": (
            "namespace Db.Migrations;\npublic partial class Init { }\n"
        ),
        # A private nested type is invisible to other files.
        "Tests/AuthTests.cs": (
            "namespace Db.Tests;\npublic class AuthTests {\n"
            "  private sealed record LoginBody(string Token);\n}\n"
        ),
        "Tests/Factory.cs": (
            "namespace Db.Tests;\npublic class Factory { object LoginBody; }\n"
        ),
        # Enum members that share an entity's name are not references.
        "Domain/Enums.cs": "namespace Db.Domain;\npublic enum Kind { Sale, Refund }\n",
        "Domain/Sale.cs": "namespace Db.Domain;\npublic class Sale { Kind K; }\n",
    }
    parsed = {f["id"]: f for f in parse_project(".", virtual_files=virtual_files)["parsedFiles"]}
    assert parsed["Migrations/Init.cs"]["dependencies"] == []
    assert parsed["Migrations/Init.Designer.cs"]["dependencies"] == []
    assert parsed["Tests/Factory.cs"]["dependencies"] == []
    assert parsed["Domain/Enums.cs"]["dependencies"] == []
    assert {d["id"] for d in parsed["Domain/Sale.cs"]["dependencies"]} == {"Domain/Enums.cs"}


def test_csharp_extension_methods_static_and_global_usings() -> None:
    virtual_files = {
        "Api/Program.cs": "app.MapAuthEndpoints();\nvar x = Archlab.Util.Clock.Now;\n",
        "Api/Endpoints.cs": (
            "namespace Archlab.Endpoints;\n"
            "public static class AuthEndpoints {\n"
            "  public static void MapAuthEndpoints(this WebApplication app) {}\n}\n"
        ),
        "Api/GlobalUsings.cs": "global using Archlab.Endpoints;\n",
        "Util/Clock.cs": "namespace Archlab.Util;\npublic static class Clock {}\n",
        "Util/Math.cs": "using static Archlab.Util.Clock;\nclass M {}\n",
    }
    parsed = {f["id"]: f for f in parse_project(".", virtual_files=virtual_files)["parsedFiles"]}
    # Extension method through a global using + a fully qualified type name.
    assert {d["id"] for d in parsed["Api/Program.cs"]["dependencies"]} == {
        "Api/Endpoints.cs",
        "Util/Clock.cs",
    }
    # `using static Ns.Type;` links the type's file.
    assert {d["id"] for d in parsed["Util/Math.cs"]["dependencies"]} == {"Util/Clock.cs"}


def test_csharp_attribute_suffix_is_resolved() -> None:
    virtual_files = {
        "Auth/RequireRoleAttribute.cs": (
            "namespace App.Auth;\npublic class RequireRoleAttribute : Attribute {}\n"
        ),
        "Web/Controller.cs": "using App.Auth;\n[RequireRole]\npublic class C {}\n",
    }
    parsed = {f["id"]: f for f in parse_project(".", virtual_files=virtual_files)["parsedFiles"]}
    assert {d["id"] for d in parsed["Web/Controller.cs"]["dependencies"]} == {
        "Auth/RequireRoleAttribute.cs"
    }


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
