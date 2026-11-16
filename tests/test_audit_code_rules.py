"""`archmap audit` code checks (CODE-*), secret context and vendored code.

Cases come from running the audit on real repositories: placeholder database
URLs, test fixtures, `system("pause")`, sanitized innerHTML templates and
suppression comments were all false positives before.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from archmap.core.audit.code_rules import scan_code
from archmap.core.audit.project_audit import audit_project, secret_context
from archmap.core.audit.secrets import scan_text
from archmap.utils.file_utils import is_vendored_path

AWS_KEY = "AKIA" + "Q" * 12 + "WXYZ"


def _rules(path: str, source: str) -> set[str]:
    return {m["rule"] for m in scan_code(path, source)}


@pytest.mark.parametrize(
    ("path", "source", "rule"),
    [
        ("a.py", "subprocess.run(cmd, shell=True)\n", "py-shell-true"),
        ("a.py", 'cur.execute(f"SELECT * FROM t WHERE id={uid}")\n', "py-sql-format"),
        ("a.py", "data = pickle.loads(blob)\n", "py-unsafe-deserialize"),
        ("a.py", "cfg = yaml.load(fh)\n", "py-yaml-load"),
        ("a.py", "requests.get(url, verify=False)\n", "py-tls-disabled"),
        ("a.ts", "exec(`git log ${branch}`)\n", "js-child-process"),
        ("a.ts", "db.query(`SELECT * FROM u WHERE id = ${id}`)\n", "js-sql-concat"),
        ("a.ts", "new https.Agent({ rejectUnauthorized: false })\n", "js-tls-disabled"),
        ("a.tsx", "<div dangerouslySetInnerHTML={{ __html: html }} />\n", "js-dangerous-html"),
        ("a.cs", 'db.Database.ExecuteSqlRaw($"DELETE FROM T WHERE Id={id}");\n', "cs-sql-concat"),
        ("a.cs", "var f = new BinaryFormatter();\n", "cs-binaryformatter"),
        ("a.cs", "h.ServerCertificateCustomValidationCallback = (a, b, c, d) => true;\n",
         "cs-tls-disabled"),
        ("A.java", 'st.executeQuery("SELECT * FROM u WHERE n=\'" + name);\n', "java-sql-concat"),
        ("a.go", 'db.Query(fmt.Sprintf("SELECT * FROM t WHERE id=%s", id))\n', "go-sql-sprintf"),
        ("a.go", "tls.Config{InsecureSkipVerify: true}\n", "go-tls-disabled"),
        ("a.c", "gets(buf);\n", "c-gets"),
        ("a.c", "strcpy(dst, src);\n", "c-unbounded-copy"),
        ("a.c", "printf(user_input);\n", "c-format-string"),
        ("a.c", "system(cmd);\n", "c-system"),
    ],
)
def test_rule_detects_sink(path: str, source: str, rule: str) -> None:
    assert rule in _rules(path, source)


@pytest.mark.parametrize(
    ("path", "source"),
    [
        # Constant command: no injection vector.
        ("main.cpp", 'system("pause");\n'),
        # Parameterized queries.
        ("a.py", 'cur.execute("SELECT * FROM t WHERE id = %s", (uid,))\n'),
        ("a.py", "cfg = yaml.load(fh, Loader=yaml.SafeLoader)\n"),
        # Mentioned in a comment / docstring, not called.
        ("a.py", '"""Never call pickle.loads on untrusted data."""\n# eval(x)\n'),
        ("a.ts", "// el.innerHTML = x\n"),
        # Every interpolation sanitized.
        ("a.js", "el.innerHTML = `<p>${escHtml(msg)}</p>`;\n"),
        # Suppressed after review.
        ("a.js", "// nosemgrep: eval\nconst fn = new Function('a', src);\n"),
        ("a.py", "os.system(cmd)  # archmap-ignore: reviewed\n"),
        # Method named like a sink.
        ("a.py", "self.model.eval()\nre.compile(p).exec\n"),
    ],
)
def test_rule_ignores_safe_code(path: str, source: str) -> None:
    assert _rules(path, source) == set()


def test_numeric_sprintf_is_downgraded() -> None:
    matches = {m["rule"]: m for m in scan_code("gui.h", 'sprintf(buf, "%.1f", x);\n')}
    assert set(matches) == {"c-sprintf-numeric"}
    assert matches["c-sprintf-numeric"]["severity"] == "low"
    assert "c-unbounded-copy" in _rules("gui.h", 'sprintf(buf, "%s", name);\n')


def test_occurrences_are_grouped_per_rule_and_file() -> None:
    matches = scan_code("a.c", "strcpy(a, b);\nint x;\nstrcat(a, c);\n")
    assert len(matches) == 1
    assert matches[0]["lines"] == [1, 3]


def test_placeholder_url_credentials_are_not_secrets() -> None:
    assert scan_text('DATABASE_URL="postgresql://user:password@localhost:5432/db"') == []
    assert scan_text("redis://default:${REDIS_PASSWORD}@cache:6379") == []
    real = scan_text("postgres://svc:Zq8v2LmX9vTw4Kp@db.internal:5432/prod")
    assert real and real[0]["rule"] == "url-credentials"


@pytest.mark.parametrize(
    ("path", "label"),
    [
        ("src/webhooks/github-webhook.service.spec.ts", "test fixture"),
        ("Archlab.Backend.Tests/AuthServiceTests.cs", "test fixture"),
        ("tests/test_auth.py", "test fixture"),
        (".env.example", "example/template/docs"),
        ("docs/setup.md", "example/template/docs"),
        (".github/workflows/ci.yml", "CI configuration"),
    ],
)
def test_secret_context(path: str, label: str) -> None:
    context = secret_context(path)
    assert context is not None and context[0] == label


def test_secret_context_ignores_production_code() -> None:
    assert secret_context("src/config/settings.py") is None
    assert secret_context("src/latest/client.ts") is None


def test_vendored_paths() -> None:
    assert is_vendored_path("External/ext/imgui/imgui.cpp")
    assert is_vendored_path("third_party/zlib/inflate.c")
    assert is_vendored_path("src/vendor/lib.js")
    assert not is_vendored_path("External/main.cpp")
    assert not is_vendored_path("src/extensions/foo.ts")


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def test_audit_scans_tests_and_tracked_build_output(tmp_path: Path) -> None:
    # The analyzer ignores tests/ and dist/; the audit must not: a secret
    # committed there is just as leaked.
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "conftest.py").write_text(f"KEY = '{AWS_KEY}'\n")
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "bundle.js").write_text(f"const k = '{AWS_KEY}';\n")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "local.js").write_text(f"const k = '{AWS_KEY}';\n")
    try:
        _git(tmp_path, "init", "-q")
        _git(tmp_path, "add", "tests/conftest.py", "dist/bundle.js")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git not available")

    files = {f["file"]: f for f in audit_project(tmp_path)["findings"]}
    assert "dist/bundle.js" in files
    assert files["dist/bundle.js"]["severity"] == "high"
    assert "tests/conftest.py" in files  # reported, but ranked as a fixture
    assert files["tests/conftest.py"]["severity"] == "low"
    assert "build/local.js" not in files  # untracked build output


def test_audit_reports_code_findings_with_cwe(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("import pickle\nobj = pickle.loads(data)\n")
    (tmp_path / "ext").mkdir()
    (tmp_path / "ext" / "lib.c").write_text("void f(char*s){char b[8]; strcpy(b, s);}\n")
    result = audit_project(tmp_path)
    code = {f["file"]: f for f in result["findings"] if f["id"].startswith("CODE-")}
    assert result["codeFindings"] == 2
    assert code["app.py"]["cwe"] == "CWE-502"
    assert code["app.py"]["line"] == 2
    assert code["app.py"]["severity"] == "high"
    # Vendored code is reported but ranked below the project's own code.
    assert code["ext/lib.c"]["severity"] == "info"
    assert any("vendored" in e for e in code["ext/lib.c"]["evidence"])

    assert audit_project(tmp_path, include_code=False)["codeFindings"] == 0


def test_audit_sarif_export(tmp_path: Path) -> None:
    from archmap.exporters.sarif_exporter import export_findings_as_sarif

    (tmp_path / "app.py").write_text("requests.get(u, verify=False)\n")
    result = audit_project(tmp_path)
    out = export_findings_as_sarif(result["findings"], result["root"], tmp_path / "a.sarif")
    sarif = json.loads(out.read_text())
    run = sarif["runs"][0]
    assert run["results"][0]["ruleId"] == "archmap/security/py-tls-disabled"
    assert run["results"][0]["locations"][0]["physicalLocation"]["region"]["startLine"] == 1
    rule = run["tool"]["driver"]["rules"][0]
    assert "external/cwe/cwe-295" in rule["properties"]["tags"]
    assert rule["properties"]["security-severity"] == "8.0"
