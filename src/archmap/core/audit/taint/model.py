"""Language-neutral taint model and solver.

Frontends (``python_frontend``, ``clike_frontend``) lower each function to a
flat list of statements over abstract expressions: which variables an
expression reads, which untrusted sources it touches directly, which calls it
makes, and whether a sanitizer wraps it. The solver then:

1. runs each function to a local fixpoint (two passes cover loops), tracking
   for every variable the *origins* of its taint — a concrete source
   (``request.args``) or one of the function's own parameters — together
   with a human-readable trace;
2. turns parameter-origin hits into *summaries* ("argument 0 of
   ``find_user`` reaches a SQL sink", "``clean`` returns argument 1");
3. iterates summaries across the whole project until they stop changing, so
   a controller passing ``req.body.name`` to a service that builds SQL from
   it is one finding with the full cross-file path.

Calls are matched by name, and only when the callee is unambiguous among the
caller's own file and the files it depends on in the dependency graph — the
graph is what keeps name-based interprocedural analysis from inventing paths.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

MAX_TRACE = 8
MAX_ROUNDS = 5
# Sources the local user controls (argv, stdin). They matter for injection
# sinks, not for paths/URLs/HTML, which a CLI user legitimately chooses.
LOCAL_PREFIX = "[local] "
WEB_ONLY_SINKS = frozenset({"path", "ssrf", "xss", "redirect", "regex", "nosql"})
# Browser-side sources (location, document.cookie) attack the user's own page:
# DOM XSS, open redirect, eval — not server-side SQL/shell/SSRF.
BROWSER_PREFIX = "[browser] "
BROWSER_SINKS = frozenset({"xss", "redirect", "code", "regex"})


@dataclass(frozen=True)
class SinkKind:
    id: str
    title: str
    cwe: str
    severity: str
    remediation: str


SINKS: dict[str, SinkKind] = {
    kind.id: kind
    for kind in (
        SinkKind("sql", "SQL injection", "CWE-89", "high",
                 "Pass user input as bound parameters, never inside the SQL text."),
        SinkKind("command", "OS command injection", "CWE-78", "critical",
                 "Run the program with an argument list and no shell; allow-list inputs."),
        SinkKind("code", "Code injection", "CWE-95", "critical",
                 "Never evaluate user input; map it to an explicit set of operations."),
        SinkKind("template", "Server-side template injection", "CWE-1336", "critical",
                 "Render fixed templates and pass user input as context variables."),
        SinkKind("deserialization", "Unsafe deserialization of user input", "CWE-502", "high",
                 "Parse untrusted data with a data-only format (JSON) and validate it."),
        SinkKind("path", "Path traversal", "CWE-22", "high",
                 "Resolve the path, then verify it stays under an allowed base directory."),
        SinkKind("ssrf", "Server-side request forgery", "CWE-918", "high",
                 "Allow-list hosts and paths; never build request URLs from raw input."),
        SinkKind("xss", "Cross-site scripting", "CWE-79", "medium",
                 "Encode output for its context or sanitize HTML (DOMPurify) first."),
        SinkKind("redirect", "Open redirect", "CWE-601", "medium",
                 "Redirect only to relative paths or an allow-listed set of URLs."),
        SinkKind("nosql", "NoSQL query injection", "CWE-943", "high",
                 "Validate the query shape; never pass a request object as the filter."),
        SinkKind("regex", "Regular expression built from user input (ReDoS)", "CWE-1333",
                 "medium", "Escape the input or use a fixed pattern with a timeout."),
    )
}


@dataclass(frozen=True)
class Origin:
    """``kind`` is ``"source"`` (untrusted input) or ``"param"`` (index)."""

    kind: str
    param: int = -1
    label: str = ""


@dataclass
class Call:
    callee: str
    args: list[Expr]
    line: int
    # `user.strip()`: the object a method is called on. Unknown calls
    # propagate receiver and arguments; project calls use their summary.
    receiver: Expr | None = None


@dataclass
class Expr:
    names: set[str] = field(default_factory=set)
    sources: list[str] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)
    sanitized: bool = False


@dataclass
class Stmt:
    """One effect: assign ``value`` to ``targets``, hit a ``sink``, or ``ret``urn."""

    line: int
    text: str
    value: Expr
    targets: list[str] = field(default_factory=list)
    sink: str | None = None
    is_return: bool = False


@dataclass
class Function:
    file: str
    name: str
    params: list[str]
    body: list[Stmt]
    line: int = 1
    # Parameters that carry untrusted input on entry (route handler arguments).
    tainted_params: dict[int, str] = field(default_factory=dict)


@dataclass
class Taint:
    origins: frozenset[Origin]
    trace: tuple[str, ...]


@dataclass
class SinkHit:
    file: str
    line: int
    sink: str
    text: str
    trace: tuple[str, ...]
    via: tuple[str, ...] = ()
    source: str = ""


@dataclass
class Summary:
    # param index -> sink hits reachable from it (with the callee-side trace)
    sinks: dict[int, list[SinkHit]] = field(default_factory=dict)
    returns_params: set[int] = field(default_factory=set)
    returns_source: Taint | None = None

    def signature(self) -> tuple[object, ...]:
        return (
            tuple(sorted((i, len(h)) for i, h in self.sinks.items())),
            tuple(sorted(self.returns_params)),
            self.returns_source is not None,
        )


Resolver = Callable[[Function, str], "Function | None"]


def _has_source(taint: Taint) -> bool:
    return any(origin.kind == "source" for origin in taint.origins)


def _merge(a: Taint | None, b: Taint | None) -> Taint | None:
    if a is None:
        return b
    if b is None:
        return a
    # Show the path from real input when there is one; otherwise the longer path.
    if _has_source(a) != _has_source(b):
        trace = a.trace if _has_source(a) else b.trace
    else:
        trace = a.trace if len(a.trace) >= len(b.trace) else b.trace
    return Taint(a.origins | b.origins, trace)


def _clip(trace: tuple[str, ...]) -> tuple[str, ...]:
    """Keep the first step (where the input enters) and the most recent ones."""
    if len(trace) <= MAX_TRACE:
        return trace
    return (trace[0], "...", *trace[-(MAX_TRACE - 2):])


def _step(taint: Taint, step: str) -> Taint:
    trace = taint.trace if taint.trace and taint.trace[-1] == step else taint.trace + (step,)
    return Taint(taint.origins, _clip(trace))


class Solver:
    def __init__(self, functions: list[Function], resolve: Resolver) -> None:
        self.functions = functions
        self.resolve = resolve
        self.summaries: dict[int, Summary] = {id(f): Summary() for f in functions}
        self.findings: dict[tuple[str, int, str], SinkHit] = {}

    # ------------------------------------------------------------------ public
    def run(self) -> list[SinkHit]:
        for _ in range(MAX_ROUNDS):
            before = [self.summaries[id(f)].signature() for f in self.functions]
            self.findings.clear()
            for function in self.functions:
                self._analyze(function)
            if before == [self.summaries[id(f)].signature() for f in self.functions]:
                break
        return sorted(self.findings.values(), key=lambda h: (h.file, h.line, h.sink))

    # ------------------------------------------------------------- per function
    def _analyze(self, function: Function) -> None:
        env: dict[str, Taint] = {}
        for index, name in enumerate(function.params):
            label = function.tainted_params.get(index)
            origin = Origin("source", label=label) if label else Origin("param", index)
            step = (
                f"{function.file}:{function.line} {label.removeprefix(LOCAL_PREFIX)}" if label
                else f"{function.file}:{function.line} parameter `{name}` of {function.name}()"
            )
            env[name] = Taint(frozenset({origin}), (step,))
        summary = Summary()
        for _ in range(2):  # second pass lets loop-carried taint reach earlier lines
            for stmt in function.body:
                self._statement(function, stmt, env, summary)
        self.summaries[id(function)] = summary

    def _statement(
        self, function: Function, stmt: Stmt, env: dict[str, Taint], summary: Summary
    ) -> None:
        where = f"{function.file}:{stmt.line}"
        value = self._eval(function, stmt.value, env, where, summary)
        if value is not None:
            for target in stmt.targets:
                env[target] = _merge(env.get(target), _step(value, f"{where} {stmt.text}")) or value
        if stmt.sink and value is not None:
            self._record(stmt.sink, function.file, stmt.line, stmt.text, value, (), summary)
        if stmt.is_return and value is not None:
            for origin in value.origins:
                if origin.kind == "param":
                    summary.returns_params.add(origin.param)
                else:
                    summary.returns_source = _merge(summary.returns_source, value)

    def _eval(
        self,
        function: Function,
        expr: Expr,
        env: dict[str, Taint],
        where: str,
        summary: Summary,
    ) -> Taint | None:
        if expr.sanitized:
            # Calls inside a sanitizer still run (and may hit sinks).
            for call in expr.calls:
                self._call(function, call, env, where, summary)
            return None
        result: Taint | None = None
        for name in expr.names:
            result = _merge(result, env.get(name))
        for label in expr.sources:
            shown = label.removeprefix(LOCAL_PREFIX).removeprefix(BROWSER_PREFIX)
            result = _merge(result, Taint(frozenset({Origin("source", label=label)}),
                                          (f"{where} {shown}",)))
        for call in expr.calls:
            result = _merge(result, self._call(function, call, env, where, summary))
        return result

    def _call(
        self,
        function: Function,
        call: Call,
        env: dict[str, Taint],
        where: str,
        summary: Summary,
    ) -> Taint | None:
        callee = self.resolve(function, call.callee)
        args = [self._eval(function, arg, env, where, summary) for arg in call.args]
        if callee is None or callee is function:
            # Library call (`strip`, `format`, `join`): assume it propagates.
            result: Taint | None = None
            if call.receiver is not None:
                result = self._eval(function, call.receiver, env, where, summary)
            for arg in args:
                result = _merge(result, arg)
            return result
        callee_summary = self.summaries[id(callee)]
        for index, hits in callee_summary.sinks.items():
            arg = args[index] if index < len(args) else None
            if arg is None:
                continue
            for hit in hits:
                # The callee's trace opens with "parameter `x` of f()"; the
                # caller's argument trace replaces that prologue.
                tail = tuple(step for step in hit.trace if "parameter `" not in step)
                step = f"{where} -> {callee.name}() in {callee.file}"
                combined = Taint(arg.origins, _clip(arg.trace + (step,) + tail))
                via = (f"{where} {call.callee}(...)", *hit.via)
                self._record(hit.sink, hit.file, hit.line, hit.text, combined, via, summary)
        result = None
        for index in callee_summary.returns_params:
            arg = args[index] if index < len(args) else None
            if arg is not None:
                result = _merge(result, _step(arg, f"{where} through {callee.name}()"))
        if callee_summary.returns_source is not None:
            result = _merge(result, callee_summary.returns_source)
        return result

    def _record(
        self,
        sink: str,
        file: str,
        line: int,
        text: str,
        value: Taint,
        via: tuple[str, ...],
        summary: Summary,
    ) -> None:
        for origin in value.origins:
            if origin.label.startswith(LOCAL_PREFIX) and sink in WEB_ONLY_SINKS:
                continue  # a CLI user opening their own path is not traversal
            if origin.label.startswith(BROWSER_PREFIX) and sink not in BROWSER_SINKS:
                continue
            hit = SinkHit(file, line, sink, text, value.trace, via, origin.label)
            if origin.kind == "source":
                key = (file, line, sink)
                existing = self.findings.get(key)
                if existing is None or len(hit.trace) < len(existing.trace):
                    self.findings[key] = hit
            else:
                hits = summary.sinks.setdefault(origin.param, [])
                if all((h.file, h.line, h.sink) != (file, line, sink) for h in hits):
                    hits.append(hit)


def build_resolver(
    functions: Iterable[Function], neighbours: Callable[[str], set[str]]
) -> Resolver:
    """Resolve ``callee`` by name within the caller's file, then its graph neighbours.

    A name that matches several functions in that scope is left unresolved:
    guessing would invent flows between unrelated ``get``/``find`` methods.
    """
    by_name: dict[str, list[Function]] = {}
    for function in functions:
        by_name.setdefault(function.name, []).append(function)

    def resolve(caller: Function, callee: str) -> Function | None:
        candidates = by_name.get(callee)
        if not candidates:
            return None
        local = [f for f in candidates if f.file == caller.file]
        if len(local) == 1:
            return local[0]
        if local:
            return None
        scope = neighbours(caller.file)
        remote = [f for f in candidates if f.file in scope]
        return remote[0] if len(remote) == 1 else None

    return resolve
