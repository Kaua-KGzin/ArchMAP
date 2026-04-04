from __future__ import annotations

from archmap.core.parser.php_parser import PHPParser
from archmap.core.parser.project_parser import parse_project


def test_php_parser_regex_extraction() -> None:
    source = """
    <?php
    use App\\Models\\User;
    use Illuminate\\Support\\Facades\\DB;

    require_once 'vendor/autoload.php';
    include "config/app.php";

    class MyClass {
        public function __construct() {
            require 'utils/helper.php';
            include_once('utils/logger.php');
        }
    }
    """
    parser = PHPParser()
    imports = parser.parse(source)

    assert imports == [
        {"type": "use", "value": "App\\Models\\User"},
        {"type": "use", "value": "Illuminate\\Support\\Facades\\DB"},
        {"type": "require", "value": "vendor/autoload.php"},
        {"type": "require", "value": "utils/helper.php"},
        {"type": "include", "value": "config/app.php"},
        {"type": "include", "value": "utils/logger.php"},
    ]


def test_php_resolution_relative_requires() -> None:
    virtual_files = {
        "src/main.php": "<?php\nrequire '../utils/helper.php';\n?>",
        "utils/helper.php": "<?php // helper ?>",
        "src/other.php": "<?php\ninclude_once 'local.php';\n?>",
        "src/local.php": "<?php // local ?>",
    }

    result = parse_project(".", virtual_files=virtual_files)
    parsed = {f["id"]: f for f in result["parsedFiles"]}

    main_deps = parsed["src/main.php"]["dependencies"]
    assert len(main_deps) == 1
    assert main_deps[0]["id"] == "utils/helper.php"
    assert main_deps[0]["type"] == "file"

    other_deps = parsed["src/other.php"]["dependencies"]
    assert len(other_deps) == 1
    assert other_deps[0]["id"] == "src/local.php"
    assert other_deps[0]["type"] == "file"


def test_php_resolution_namespace_use() -> None:
    virtual_files = {
        "src/Controller/UserController.php": "<?php\nuse App\\Models\\User;\n?>",
        "src/Models/User.php": "<?php\nnamespace App\\Models;\nclass User {}\n?>",
    }

    result = parse_project(".", virtual_files=virtual_files)
    parsed = {f["id"]: f for f in result["parsedFiles"]}

    deps = parsed["src/Controller/UserController.php"]["dependencies"]

    assert len(deps) == 1
    # It should map App\Models\User to src/Models/User.php because the
    # resolver ignores case and matches the namespace suffix.
    assert deps[0]["id"] == "src/Models/User.php"
    assert deps[0]["type"] == "file"


def test_php_resolution_external_fallback() -> None:
    virtual_files = {
        "index.php": "<?php\nuse GuzzleHttp\\Client;\nrequire 'vendor/autoload.php';\n?>",
    }

    result = parse_project(".", virtual_files=virtual_files)
    parsed = {f["id"]: f for f in result["parsedFiles"]}

    deps = parsed["index.php"]["dependencies"]
    dep_ids = {d["id"] for d in deps}

    # Neither exists locally, so they should fallback to pkg:
    assert "pkg:GuzzleHttp\\Client" in dep_ids
    assert "pkg:vendor/autoload.php" in dep_ids
