"""Lower Python source to the taint model with the standard ``ast`` module."""

from __future__ import annotations

import ast
import warnings

from archmap.core.audit.taint.model import LOCAL_PREFIX, Call, Expr, Function, Stmt

_REQUEST_ATTRS = {
    "args", "form", "values", "json", "data", "files", "cookies", "headers", "query_params",
    "path_params", "GET", "POST", "body", "COOKIES", "META", "FILES", "query_string", "url",
}
_REQUEST_CALLS = {"get_json", "get_data", "body", "form", "json"}
_ROUTE_DECORATORS = {
    "route", "get", "post", "put", "delete", "patch", "api_route", "websocket", "head", "options",
}
_INJECTED_PARAMS = {"self", "cls", "request", "db", "session", "background_tasks", "response"}
_INJECTED_TYPES = {
    "Request", "Response", "Session", "AsyncSession", "BackgroundTasks", "WebSocket",
    "HTTPConnection", "SecurityScopes",
}

_SANITIZERS = {
    "int", "float", "bool", "len", "abs", "round", "ord", "chr", "id", "hash", "isinstance",
    "quote", "quote_plus", "shlex.quote", "html.escape", "escape", "markupsafe.escape",
    "secure_filename", "os.path.basename", "basename", "bleach.clean", "re.escape",
    "uuid.UUID", "UUID", "urlencode",
}

# callee (dotted or bare) -> (sink kind, argument index)
_SINKS: dict[str, tuple[str, int]] = {
    "execute": ("sql", 0), "executemany": ("sql", 0), "executescript": ("sql", 0),
    "raw": ("sql", 0), "sqlalchemy.text": ("sql", 0), "text": ("sql", 0),
    "os.system": ("command", 0), "os.popen": ("command", 0),
    "subprocess.getoutput": ("command", 0), "subprocess.getstatusoutput": ("command", 0),
    "eval": ("code", 0), "exec": ("code", 0), "compile": ("code", 0),
    "render_template_string": ("template", 0), "jinja2.Template": ("template", 0),
    "from_string": ("template", 0),
    "pickle.loads": ("deserialization", 0), "pickle.load": ("deserialization", 0),
    "marshal.loads": ("deserialization", 0), "dill.loads": ("deserialization", 0),
    "jsonpickle.decode": ("deserialization", 0), "yaml.unsafe_load": ("deserialization", 0),
    "open": ("path", 0), "send_file": ("path", 0), "os.remove": ("path", 0),
    "os.unlink": ("path", 0), "shutil.rmtree": ("path", 0), "FileResponse": ("path", 0),
    "urlopen": ("ssrf", 0), "urllib.request.urlopen": ("ssrf", 0),
    "redirect": ("redirect", 0), "RedirectResponse": ("redirect", 0),
    "HttpResponseRedirect": ("redirect", 0),
    "Markup": ("xss", 0), "mark_safe": ("xss", 0), "HTMLResponse": ("xss", 0),
    "re.compile": ("regex", 0), "re.match": ("regex", 0), "re.search": ("regex", 0),
    "re.fullmatch": ("regex", 0), "re.findall": ("regex", 0),
}
_METHOD_SINKS = {"execute", "executemany", "executescript", "raw", "from_string"}
_HTTP_CLIENTS = {"requests", "httpx"}
_HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options", "request", "stream"}
_SUBPROCESS = {"run", "call", "Popen", "check_output", "check_call"}


def _dotted(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    elif isinstance(node, ast.Call):
        parts.append(_dotted(node.func) + "()")
    else:
        return ""
    return ".".join(reversed(parts))


def _source_label(node: ast.AST) -> str | None:
    dotted = _dotted(node)
    if not dotted:
        return None
    parts = dotted.split(".")
    if parts[0] == "request" and len(parts) > 1 and parts[1] in _REQUEST_ATTRS:
        return f"{'.'.join(parts[:2])} (HTTP input)"
    if dotted in ("sys.argv", "sys.stdin"):
        return f"{LOCAL_PREFIX}{dotted} (command line)"
    return None


class _Lowerer:
    def __init__(self, file: str, lines: list[str]) -> None:
        self.file = file
        self.lines = lines
        self.functions: list[Function] = []

    def text(self, node: ast.AST) -> str:
        line = getattr(node, "lineno", 1)
        return self.lines[line - 1].strip()[:160] if 0 < line <= len(self.lines) else ""

    # ----------------------------------------------------------- expressions
    def expr(self, node: ast.AST | None, out: list[Stmt]) -> Expr:
        result = Expr()
        if node is None:
            return result
        label = _source_label(node)
        if label:
            result.sources.append(label)
            return result
        if isinstance(node, ast.Name):
            result.names.add(node.id)
        elif isinstance(node, ast.Attribute):
            return self.expr(node.value, out)
        elif isinstance(node, ast.Call):
            return self.call(node, out)
        elif isinstance(node, ast.Compare):
            # A comparison yields a bool; only its calls matter.
            inner = [self.expr(n, out) for n in (node.left, *node.comparators)]
            result.calls = [c for e in inner for c in e.calls]
            result.sanitized = True
        elif isinstance(node, (ast.Lambda, ast.Constant)):
            pass
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            parts = [node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]
            for generator in node.generators:
                parts.append(generator.iter)
            self._merge_into(result, [self.expr(p, out) for p in parts])
        else:
            self._merge_into(
                result, [self.expr(child, out) for child in ast.iter_child_nodes(node)
                         if isinstance(child, ast.expr)]
            )
        return result

    @staticmethod
    def _merge_into(target: Expr, parts: list[Expr]) -> None:
        for part in parts:
            if part.sanitized:
                target.calls.extend(part.calls)
                continue
            target.names |= part.names
            target.sources.extend(part.sources)
            target.calls.extend(part.calls)

    def call(self, node: ast.Call, out: list[Stmt]) -> Expr:
        dotted = _dotted(node.func)
        last = dotted.rsplit(".", 1)[-1] if dotted else ""
        args = [self.expr(a, out) for a in node.args]
        keywords = {k.arg: k.value for k in node.keywords if k.arg}
        receiver = (
            self.expr(node.func.value, out) if isinstance(node.func, ast.Attribute) else None
        )

        # Direct sources: request.get_json(), input().
        if dotted.startswith("request.") and last in _REQUEST_CALLS:
            return Expr(sources=[f"{dotted}() (HTTP input)"])
        if dotted == "input":
            return Expr(sources=[f"{LOCAL_PREFIX}input() (stdin)"])

        sink = self._sink(dotted, last, node, keywords)
        if sink is not None:
            kind, index = sink
            arg_node: ast.expr | None = node.args[index] if index < len(node.args) else None
            if arg_node is None and kind == "ssrf":
                arg_node = keywords.get("url")
            if arg_node is not None and kind in ("ssrf", "redirect"):
                arg_node = _url_head(arg_node)  # None: fixed scheme/host
            if arg_node is not None:
                out.append(Stmt(node.lineno, self.text(node), self.expr(arg_node, out), sink=kind))

        hashing = last in ("hexdigest", "digest") or dotted.startswith("hashlib.")
        if dotted in _SANITIZERS or hashing:
            calls = [c for a in args for c in a.calls]
            return Expr(calls=calls, sanitized=True)
        return Expr(calls=[Call(last or dotted, args, node.lineno, receiver)])

    @staticmethod
    def _sink(
        dotted: str, last: str, node: ast.Call, keywords: dict[str, ast.expr]
    ) -> tuple[str, int] | None:
        root = dotted.split(".", 1)[0]
        if root in _HTTP_CLIENTS and last in _HTTP_METHODS:
            return ("ssrf", 1 if last == "request" else 0)
        if root == "subprocess" and last in _SUBPROCESS:
            shell = keywords.get("shell")
            if isinstance(shell, ast.Constant) and shell.value is True:
                return ("command", 0)
            return None
        if dotted == "yaml.load" or last == "load" and root == "yaml":
            loader = _dotted(keywords["Loader"]) if "Loader" in keywords else ""
            return None if "Safe" in loader else ("deserialization", 0)
        if dotted in _SINKS:
            return _SINKS[dotted]
        if last in _METHOD_SINKS and "." in dotted:
            return _SINKS[last]  # cursor.execute(...), Model.objects.raw(...)
        if dotted == last and last in _SINKS:
            return _SINKS[last]  # eval(...), open(...), redirect(...)
        return None

    # ------------------------------------------------------------ statements
    def body(self, nodes: list[ast.stmt], out: list[Stmt]) -> None:
        for node in nodes:
            self.stmt(node, out)

    def stmt(self, node: ast.stmt, out: list[Stmt]) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self.function(node)
            return
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    self.stmt(child, out)
            return
        text = self.text(node)
        line = getattr(node, "lineno", 1)
        if isinstance(node, ast.Assign):
            value = self.expr(node.value, out)
            targets = [t for target in node.targets for t in _targets(target)]
            out.append(Stmt(line, text, value, targets=targets))
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            out.append(Stmt(line, text, self.expr(node.value, out), targets=_targets(node.target)))
        elif isinstance(node, ast.AugAssign):
            value = self.expr(node.value, out)
            targets = _targets(node.target)
            value.names |= set(targets)
            out.append(Stmt(line, text, value, targets=targets))
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            out.append(Stmt(line, text, self.expr(node.iter, out), targets=_targets(node.target)))
            self.body(node.body + node.orelse, out)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                value = self.expr(item.context_expr, out)
                targets = _targets(item.optional_vars) if item.optional_vars else []
                out.append(Stmt(line, text, value, targets=targets))
            self.body(node.body, out)
        elif isinstance(node, ast.Return):
            out.append(Stmt(line, text, self.expr(node.value, out), is_return=True))
        elif isinstance(node, ast.Expr):
            out.append(Stmt(line, text, self.expr(node.value, out)))
        elif isinstance(node, (ast.If, ast.While)):
            out.append(Stmt(line, text, self.expr(node.test, out)))
            self.body(node.body + node.orelse, out)
        elif isinstance(node, ast.Try) or type(node).__name__ == "TryStar":
            handlers = [s for h in node.handlers for s in h.body]  # type: ignore[attr-defined]
            self.body(node.body + handlers + node.orelse + node.finalbody,  # type: ignore[attr-defined]
                      out)
        elif isinstance(node, ast.Match):
            out.append(Stmt(line, text, self.expr(node.subject, out)))
            for case in node.cases:
                self.body(case.body, out)

    def function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        args = node.args
        params = [a for a in (*args.posonlyargs, *args.args)]
        if params and params[0].arg in ("self", "cls"):
            params = params[1:]
        all_params = [*params, *args.kwonlyargs]
        names = [a.arg for a in all_params]
        if args.vararg:
            names.append(args.vararg.arg)
        if args.kwarg:
            names.append(args.kwarg.arg)
        tainted: dict[int, str] = {}
        if _is_route(node):
            defaults = _defaults_by_name(node)
            for index, param in enumerate(all_params):
                annotation = _dotted(param.annotation) if param.annotation is not None else ""
                default = defaults.get(param.arg)
                if (
                    param.arg in _INJECTED_PARAMS
                    or annotation.rsplit(".", 1)[-1] in _INJECTED_TYPES
                    or (isinstance(default, ast.Call) and _dotted(default.func).endswith("Depends"))
                ):
                    continue
                tainted[index] = f"route parameter `{param.arg}` of {node.name}() (HTTP input)"
        body: list[Stmt] = []
        self.body(node.body, body)
        self.functions.append(Function(self.file, node.name, names, body, node.lineno, tainted))


def _url_head(node: ast.expr) -> ast.expr | None:
    """The sub-expression deciding a URL's scheme and host (None when fixed)."""
    if isinstance(node, ast.JoinedStr) and node.values:
        first = node.values[0]
        if isinstance(first, ast.FormattedValue):
            return first.value
        return None if isinstance(first, ast.Constant) and str(first.value) else node
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        return _url_head(node.left)
    if isinstance(node, ast.Constant):
        return None
    if (
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "format" and isinstance(node.func.value, ast.Constant)
    ):
        template = str(node.func.value.value)
        return node if template.startswith("{") else None
    return node


def _targets(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        return [t for elt in node.elts for t in _targets(elt)]
    if isinstance(node, ast.Starred):
        return _targets(node.value)
    if isinstance(node, ast.Subscript):
        return _targets(node.value)  # `d[k] = tainted` taints the container
    return []


def _is_route(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if _dotted(target).rsplit(".", 1)[-1] in _ROUTE_DECORATORS and isinstance(
            target, ast.Attribute
        ):
            return True
    return False


def _defaults_by_name(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, ast.expr]:
    args = node.args
    positional = [*args.posonlyargs, *args.args]
    mapping = {
        a.arg: d for a, d in zip(positional[len(positional) - len(args.defaults):], args.defaults,
                                 strict=False)
    }
    for a, d in zip(args.kwonlyargs, args.kw_defaults, strict=False):
        if d is not None:
            mapping[a.arg] = d
    return mapping


def lower_python(file: str, source: str) -> list[Function]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)  # e.g. invalid escapes
            tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    lowerer = _Lowerer(file, source.splitlines())
    module: list[Stmt] = []
    lowerer.body(tree.body, module)
    lowerer.functions.append(Function(file, "<module>", [], module, 1))
    return lowerer.functions
