"""Interprocedural taint analysis (TAINT-*) for `archmap audit`.

Every negative case here is a false positive the engine produced on a real
repository before it was fixed; every positive is a pattern from a real
framework (Flask, FastAPI, Express, NestJS, Next.js, ASP.NET, Spring).
"""

from __future__ import annotations

from pathlib import Path

from archmap.core.audit.project_audit import audit_project
from archmap.core.audit.taint import analyze_sources


def _hits(
    files: dict[str, str], graph: dict[str, set[str]] | None = None
) -> set[tuple[str, int, str]]:
    edges = graph or {}
    return {(h.file, h.line, h.sink) for h in analyze_sources(files, lambda f: edges.get(f, set()))}


# --------------------------------------------------------------------------- Python


FLASK = '''\
from flask import request, redirect
import os, subprocess

@app.route("/u")
def user():
    name = request.args.get("name")
    cur.execute(f"SELECT * FROM users WHERE name = '{name}'")
    cur.execute("SELECT * FROM t WHERE name = %s", (name,))
    uid = int(request.args["id"])
    cur.execute(f"SELECT * FROM t WHERE id = {uid}")
    subprocess.run(["ping", name])
    subprocess.run("ping " + name, shell=True)
    os.system("ping " + shlex.quote(name))
    return redirect(request.args["next"])
'''


def test_python_flask_flows_and_sanitizers() -> None:
    assert _hits({"app.py": FLASK}) == {
        ("app.py", 7, "sql"),
        ("app.py", 12, "command"),
        ("app.py", 14, "redirect"),
    }


def test_python_fastapi_route_params_are_sources() -> None:
    source = '''\
@router.get("/files/{name}")
async def read(name: str, db: Session = Depends(get_db), request: Request = None):
    return FileResponse(os.path.join(BASE, name))

def helper(name: str):
    return open(name).read()
'''
    hits = _hits({"api.py": source})
    assert hits == {("api.py", 3, "path")}


def test_python_cross_file_flow_follows_the_dependency_graph() -> None:
    files = {
        "views.py": (
            "from repo import find_user\n"
            "@app.post('/u')\n"
            "def view():\n"
            "    return find_user(request.form['name'])\n"
        ),
        "repo.py": (
            "def find_user(name):\n"
            "    sql = \"SELECT * FROM u WHERE n = '\" + name + \"'\"\n"
            "    return db.execute(sql)\n"
        ),
    }
    assert _hits(files, {"views.py": {"repo.py"}}) == {("repo.py", 3, "sql")}
    # Without a graph edge the callee is not resolved: no invented flow.
    assert _hits(files) == set()
    hit = analyze_sources(files, lambda f: {"repo.py"} if f == "views.py" else set())[0]
    assert hit.via == ("views.py:4 find_user(...)",)
    assert any("repo.py:2" in step for step in hit.trace)


def test_python_helper_that_sanitizes_stops_the_flow() -> None:
    source = '''\
def clean(value):
    return html.escape(value)

@app.get("/x")
def view():
    return Markup("<b>" + clean(request.args["q"]) + "</b>")
'''
    assert _hits({"a.py": source}) == set()


def test_local_sources_only_reach_injection_sinks() -> None:
    # A CLI opening the path its own user typed is not path traversal...
    source = '''\
import sys
path = sys.argv[1]
data = open(path).read()
os.system("cat " + sys.argv[2])
'''
    # ...but building a shell command from argv is still command injection.
    assert _hits({"cli.py": source}) == {("cli.py", 4, "command")}


def test_redirect_with_fixed_host_is_not_open_redirect() -> None:
    source = '''\
@app.get("/cb")
def cb():
    token = request.args["code"]
    redirect(f"{FRONTEND}/done?token={token}")
    redirect("https://example.com/next/" + token)
    return redirect(request.args["next"])
'''
    assert _hits({"a.py": source}) == {("a.py", 6, "redirect")}


def test_bom_prefixed_python_is_parsed() -> None:
    source = "﻿@app.get('/x')\ndef v():\n    eval(request.args['c'])\n"
    assert _hits({"a.py": source}) == {("a.py", 3, "code")}


# --------------------------------------------------------------------------- JS / TS


NEST_CONTROLLER = '''\
@Controller('users')
export class UsersController {
  constructor(private readonly usersService: UsersService) {}

  @Get()
  async search(@Query('name') name: string, @Query('id') id: string): Promise<{ items: User[] }> {
    await this.usersService.byId(parseInt(id, 10));
    return this.usersService.findByName(name);
  }

  @Post('import')
  importFile(@Body() dto: ImportDto) {
    const { path: filePath } = dto;
    return fs.readFileSync(filePath, 'utf8');
  }
}
'''
NEST_SERVICE = '''\
export class UsersService {
  async findByName(name: string) {
    const sql = `SELECT * FROM users WHERE name = '${name}'`;
    return this.prisma.$queryRawUnsafe(sql);
  }
  async byId(id: number) {
    return this.prisma.$queryRawUnsafe(`SELECT * FROM users WHERE id = ${id}`);
  }
  safe(name: string) {
    return this.prisma.user.findMany({ where: { name } });
  }
}
'''


def test_nestjs_controller_to_service_across_files() -> None:
    files = {"users.controller.ts": NEST_CONTROLLER, "users.service.ts": NEST_SERVICE}
    graph = {"users.controller.ts": {"users.service.ts"}}
    assert _hits(files, graph) == {
        ("users.controller.ts", 14, "path"),  # destructured @Body() field
        ("users.service.ts", 4, "sql"),  # parseInt() keeps byId() clean
    }


def test_express_handlers() -> None:
    source = '''\
const { exec } = require('child_process');
app.get('/ping', (req, res) => {
  const host = req.query.host;
  exec('ping -c 1 ' + host, (err, out) => res.send(out));
  res.redirect(req.query.next);
  res.redirect(`${FRONTEND}/done?u=${req.query.u}`);
  const re = /x/.exec(host);
});
app.get('/go', (req, res) => res.redirect(req.body.url));
'''
    assert _hits({"server.js": source}) == {
        ("server.js", 4, "command"),
        ("server.js", 5, "redirect"),
        ("server.js", 9, "redirect"),
    }


def test_browser_sources_reach_dom_sinks_only() -> None:
    source = '''\
function render() {
  const q = new URLSearchParams(location.search).get('q');
  document.getElementById('out').innerHTML = `<b>${q}</b>`;
  document.getElementById('o2').innerHTML = `<b>${escapeHtml(q)}</b>`;
  fetch(location.href);
}
'''
    assert _hits({"page.js": source}) == {("page.js", 3, "xss")}


def test_service_worker_fetch_is_not_ssrf() -> None:
    source = "self.addEventListener('fetch', (event) => {\n  fetch(event.request.url);\n});\n"
    assert _hits({"sw.js": source}) == set()


def test_nextjs_route_handler_request_is_a_source() -> None:
    source = '''\
export async function POST(request: Request) {
  const body = await request.json();
  return NextResponse.redirect(body.next);
}
export async function GET(request: Request) {
  return NextResponse.redirect(`${origin}/home`);
}
'''
    assert _hits({"app/api/x/route.ts": source}) == {("app/api/x/route.ts", 3, "redirect")}


# --------------------------------------------------------------------------- C# / Java


def test_aspnet_minimal_api_nested_in_setup_method() -> None:
    source = '''\
public static class FileEndpoints {
    public static void MapFiles(this WebApplication app) {
        var group = app.MapGroup("/files");
        group.MapGet("/{name}", async (string name, FileService files) => {
            var full = Path.Combine(Root, name);
            return Results.File(full);
        });
        group.MapGet("/n/{id}", (int id, FileService files) => files.Get(id));
        group.MapPost("/q", (SearchRequest req, AppDb db) =>
            db.Database.ExecuteSqlRaw($"DELETE FROM T WHERE N = '{req.Name}'"));
    }
}
'''
    assert _hits({"FileEndpoints.cs": source}) == {
        ("FileEndpoints.cs", 6, "path"),
        ("FileEndpoints.cs", 10, "sql"),
    }


def test_aspnet_controller_actions() -> None:
    source = '''\
[ApiController]
public class FilesController : ControllerBase {
    [HttpGet("go")]
    public IActionResult Go([FromQuery] string url) => Redirect(url);

    public IActionResult Count([FromQuery] string q) {
        var n = int.Parse(q);
        return Ok(_db.Items.FromSqlRaw("SELECT * FROM I WHERE Id = " + n));
    }

    public async Task<IActionResult> Lock() {
        await _db.Database.ExecuteSqlRawAsync("SELECT pg_advisory_lock({0})", [LockKey]);
        return Ok();
    }
}
'''
    assert _hits({"FilesController.cs": source}) == {("FilesController.cs", 4, "redirect")}


def test_spring_controller() -> None:
    source = '''\
@RestController
public class App {
    @GetMapping("/u")
    public List<User> users(@RequestParam("name") String name) throws SQLException {
        String sql = "SELECT * FROM users WHERE name = '" + name + "'";
        return jdbcTemplate.query(sql, mapper);
    }
    @GetMapping("/ok")
    public List<User> ok(@RequestParam String name) {
        return jdbcTemplate.query("SELECT * FROM users WHERE name = ?", mapper, name);
    }
    @GetMapping("/f")
    public String f(HttpServletRequest request) throws IOException {
        String p = request.getParameter("p");
        return new String(Files.readAllBytes(Paths.get("/srv", p)));
    }
}
'''
    assert _hits({"App.java": source}) == {("App.java", 6, "sql"), ("App.java", 15, "path")}


# --------------------------------------------------------------------------- audit


def test_audit_reports_taint_with_trace_and_dedupes_pattern_findings(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "@app.get('/x')\n"
        "def view():\n"
        "    q = request.args['q']\n"
        "    cur.execute(f\"SELECT * FROM t WHERE c = '{q}'\")\n"
        "    cur.execute(f\"SELECT * FROM t WHERE c = '{CONST}'\")\n"
        "    # archmap-ignore: reviewed\n"
        "    cur.execute(f\"SELECT {q}\")\n"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text(
        "@app.get('/t')\ndef t():\n    eval(request.args['c'])\n"
    )
    result = audit_project(tmp_path)
    taint = [f for f in result["findings"] if f["id"].startswith("TAINT-")]
    assert result["taintFindings"] == 1
    finding = taint[0]
    assert (finding["file"], finding["line"], finding["cwe"]) == ("app.py", 4, "CWE-89")
    assert finding["message"].startswith("SQL injection: request.args (HTTP input) reaches")
    assert any(e.startswith("Flow: app.py:3") for e in finding["evidence"])
    # The CODE pattern finding for line 4 alone would be redundant, but line 5
    # (a constant, no flow) keeps the CODE finding alive as a review hint.
    code = [f for f in result["findings"] if f["category"] == "py-sql-format"]
    assert len(code) == 1

    assert audit_project(tmp_path, include_taint=False)["taintFindings"] == 0


def test_audit_drops_pattern_finding_explained_by_taint(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "@app.get('/x')\ndef view():\n    return pickle.loads(request.data)\n"
    )
    result = audit_project(tmp_path)
    categories = [f["category"] for f in result["findings"]]
    assert categories == ["taint-deserialization"]
