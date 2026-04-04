from __future__ import annotations

from archmap.core.parser.java_parser import JavaParser
from archmap.core.parser.project_parser import parse_project


def test_java_parser_regex_extraction() -> None:
    source = """
    package com.example.app;

    import java.util.List;
    import java.util.stream.Collectors;
    import static org.junit.Assert.assertEquals;
    import com.example.service.UserService;
    import com.example.utils.*;

    public class App {
    }
    """
    parser = JavaParser()
    imports = parser.parse(source)

    assert imports == [
        "com.example.service.UserService",
        "com.example.utils.*",
        "java.util.List",
        "java.util.stream.Collectors",
        "org.junit.Assert.assertEquals",
    ]


def test_java_resolution_specific_class() -> None:
    virtual_files = {
        "src/main/java/com/example/app/App.java": "import com.example.service.UserService;\n",
        "src/main/java/com/example/service/UserService.java": "package com.example.service;\n",
    }

    result = parse_project(".", virtual_files=virtual_files)
    parsed = {f["id"]: f for f in result["parsedFiles"]}

    deps = parsed["src/main/java/com/example/app/App.java"]["dependencies"]

    assert len(deps) == 1
    assert deps[0]["id"] == "src/main/java/com/example/service/UserService.java"
    assert deps[0]["type"] == "file"


def test_java_resolution_wildcard_package() -> None:
    virtual_files = {
        "src/main/java/com/example/app/App.java": "import com.example.utils.*;\n",
        "src/main/java/com/example/utils/Helper.java": "package com.example.utils;\n",
        "src/main/java/com/example/utils/Constants.java": "package com.example.utils;\n",
        "src/main/java/com/example/other/Ignored.java": "package com.example.other;\n",
    }

    result = parse_project(".", virtual_files=virtual_files)
    parsed = {f["id"]: f for f in result["parsedFiles"]}

    deps = parsed["src/main/java/com/example/app/App.java"]["dependencies"]
    dep_ids = {d["id"] for d in deps}

    # It should map to all .java files inside com/example/utils
    assert len(deps) == 2
    assert "src/main/java/com/example/utils/Helper.java" in dep_ids
    assert "src/main/java/com/example/utils/Constants.java" in dep_ids
    assert "src/main/java/com/example/other/Ignored.java" not in dep_ids


def test_java_resolution_stdlib_and_fallback() -> None:
    virtual_files = {
        "App.java": (
            "import java.util.List;\n"
            "import javax.servlet.http.*;\n"
            "import sun.misc.Unsafe;\n"
            "import org.springframework.boot.SpringApplication;\n"
        ),
    }

    result = parse_project(".", virtual_files=virtual_files)
    parsed = {f["id"]: f for f in result["parsedFiles"]}

    deps = parsed["App.java"]["dependencies"]
    dep_ids = {d["id"] for d in deps}

    assert len(deps) == 4
    # Standard libraries and external packages should fallback to pkg:
    assert "pkg:java.util.List" in dep_ids
    assert "pkg:javax.servlet.http.*" in dep_ids
    assert "pkg:sun.misc.Unsafe" in dep_ids
    assert "pkg:org.springframework.boot.SpringApplication" in dep_ids
