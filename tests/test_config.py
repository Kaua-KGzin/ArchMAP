from __future__ import annotations

from archmap.config import load_project_config
from archmap.core import analyze_project
from archmap.core.parser import parse_project


def test_load_project_config_reads_ignore_dirs_and_layer_order(tmp_path) -> None:
    (tmp_path / ".archmap.toml").write_text(
        """
[analysis]
ignore_dirs = ["generated", "vendor/cache"]
max_file_size_bytes = 2048

[architecture.rules]
forbid = ["ui -> database", "controller -> repository"]
allow = ["controller -> service", "service -> repository"]

[risks.layer_order]
platform = 6
core = 3

[network.rules]
forbid = ["frontend -> postgresql"]
allow = ["backend -> postgresql"]
""".strip(),
        encoding="utf-8",
    )

    config = load_project_config(tmp_path)

    assert config["analysis"]["ignore_dirs"] == ["generated", "vendor/cache"]
    assert config["analysis"]["max_file_size_bytes"] == 2048
    assert config["architecture"]["rules"]["forbid"] == [
        "ui -> database",
        "controller -> repository",
    ]
    assert config["architecture"]["rules"]["allow"] == [
        "controller -> service",
        "service -> repository",
    ]
    assert config["risks"]["layer_order"] == {"platform": 6, "core": 3}
    assert config["network"]["rules"]["forbid"] == ["frontend -> postgresql"]
    assert config["network"]["rules"]["allow"] == ["backend -> postgresql"]


def test_load_project_config_defaults_network_rules_when_absent(tmp_path) -> None:
    config = load_project_config(tmp_path)

    assert config["network"]["rules"] == {"forbid": [], "allow": []}


def test_parse_project_honors_archmap_toml_ignore_dirs(tmp_path) -> None:
    (tmp_path / ".archmap.toml").write_text(
        """
[analysis]
ignore_dirs = ["generated"]
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "generated").mkdir()
    (tmp_path / "src" / "main.py").write_text("import os\n", encoding="utf-8")
    (tmp_path / "generated" / "skip.py").write_text("import sys\n", encoding="utf-8")

    parsed = parse_project(tmp_path)

    assert [entry["id"] for entry in parsed["parsedFiles"]] == ["src/main.py"]


def test_parse_project_honors_archmap_toml_max_file_size(write_project_files) -> None:
    project_root = write_project_files(
        {
            ".archmap.toml": """
[analysis]
max_file_size_bytes = 16
""".strip(),
            "src/small.py": "import os\n",
            "src/large.py": "very_large_literal = '01234567890123456789'\n",
        }
    )

    parsed = parse_project(project_root)

    assert [entry["id"] for entry in parsed["parsedFiles"]] == ["src/small.py"]


def test_analyze_project_honors_custom_layer_order_from_archmap_toml(tmp_path) -> None:
    (tmp_path / ".archmap.toml").write_text(
        """
[risks.layer_order]
platform = 6
core = 3
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "core").mkdir(parents=True)
    (tmp_path / "src" / "platform").mkdir(parents=True)
    (tmp_path / "src" / "core" / "service.py").write_text(
        "from platform.http import call\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "platform" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "platform" / "http.py").write_text(
        "def call():\n    return 1\n",
        encoding="utf-8",
    )

    report = analyze_project(tmp_path)

    assert report["risks"]["layer_violations"] == [
        {
            "source": "src/core/service.py",
            "target": "src/platform/http.py",
            "sourceLayer": "core",
            "targetLayer": "platform",
            "rule": "lower-level module should not depend on higher-level module",
        }
    ]


def test_analyze_project_honors_custom_architecture_rules_from_archmap_toml(tmp_path) -> None:
    (tmp_path / ".archmap.toml").write_text(
        """
[architecture.rules]
forbid = ["controller -> repository"]
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "src" / "controller").mkdir(parents=True)
    (tmp_path / "src" / "repository").mkdir(parents=True)
    (tmp_path / "src" / "controller" / "users.py").write_text(
        "from repository.users import get_user\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "repository" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "repository" / "users.py").write_text(
        "def get_user():\n    return 1\n",
        encoding="utf-8",
    )

    report = analyze_project(tmp_path)

    assert report["architecture"]["ruleViolations"] == [
        {
            "source": "src/controller/users.py",
            "target": "src/repository/users.py",
            "sourceTag": "controller",
            "targetTag": "repository",
            "rule": "controller -> repository",
            "message": (
                "controller -> repository is forbidden but src/controller/users.py "
                "depends on src/repository/users.py"
            ),
            "kind": "forbid",
        }
    ]


def test_analyze_project_honors_allow_only_architecture_rules_from_archmap_toml(tmp_path) -> None:
    (tmp_path / ".archmap.toml").write_text(
        """
[architecture.rules]
allow = ["controller -> service"]
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "src" / "controller").mkdir(parents=True)
    (tmp_path / "src" / "repository").mkdir(parents=True)
    (tmp_path / "src" / "controller" / "users.py").write_text(
        "from repository.users import get_user\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "repository" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "repository" / "users.py").write_text(
        "def get_user():\n    return 1\n",
        encoding="utf-8",
    )

    report = analyze_project(tmp_path)

    assert report["architecture"]["activeRules"] == {
        "forbid": [],
        "allow": ["controller -> service"],
    }
    violation = report["architecture"]["ruleViolations"][0]
    assert violation["source"] == "src/controller/users.py"
    assert violation["target"] == "src/repository/users.py"
    assert violation["kind"] == "allow"
    assert violation["sourceTag"] == "controller"
    assert violation["rule"] == "controller -> service"
    assert violation["allowedTargets"] == ["service"]
    assert violation["message"] == (
        "src/controller/users.py should only depend on service "
        "but currently depends on src/repository/users.py"
    )
