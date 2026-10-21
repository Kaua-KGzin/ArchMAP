"""Lower JS/TS, C# and Java to the taint model without a parser dependency.

The source is comment-stripped and string-masked (literal text blanked,
template/interpolation holes kept), split into function units by brace
matching, then into statements. Each statement becomes assignments, returns
and sink hits over expressions that know their variables, direct sources and
calls. It is deliberately conservative: anything it cannot read becomes "no
flow", so imprecision costs recall, not false alarms.

Nested lambdas are inlined into the enclosing function (closures see the
outer variables); module-level callbacks (``app.get('/x', (req, res) => {})``)
are their own units.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from archmap.core.audit.taint.model import (
    BROWSER_PREFIX,
    LOCAL_PREFIX,
    Call,
    Expr,
    Function,
    Stmt,
)
from archmap.core.parser._text import strip_comments

LANGUAGE_BY_EXT = {
    ".js": "js", ".jsx": "js", ".mjs": "js", ".cjs": "js",
    ".ts": "js", ".tsx": "js", ".mts": "js", ".cts": "js",
    ".cs": "csharp",
    ".java": "java",
}

_IDENT = r"[A-Za-z_$][\w$]*"
_CONTROL = {
    "if", "for", "foreach", "while", "switch", "catch", "using", "lock", "fixed", "return",
    "else", "do", "try", "finally", "when", "synchronized", "with", "await", "typeof", "sizeof",
    "nameof", "new", "throw", "case", "in", "of",
}
_KEYWORDS = _CONTROL | {
    "const", "let", "var", "function", "async", "this", "super", "null", "undefined", "true",
    "false", "void", "public", "private", "protected", "internal", "static", "readonly",
    "final", "string", "int", "long", "bool", "boolean", "double", "float", "decimal",
    "object", "dynamic", "as", "is", "instanceof", "out", "ref", "params", "default", "yield",
    "base", "class", "interface", "struct", "record", "enum", "extends", "implements", "where",
    "get", "set", "init", "value", "type", "keyof", "any", "unknown", "never", "number",
    "String", "Integer", "Long", "Boolean", "Object", "char", "byte", "short", "Task",
}
# `)` + optional TS return type / Java throws / C# generic constraints, at the end.
_HEADER_TAIL = re.compile(
    r"\)\s*(?::\s*[^(){};=]+?)?\s*(?:throws\s+[\w.,\s]+)?(?:where\s+[^{]+)?$"
)
_EXPR_BODIED = re.compile(r"^(?P<head>[^=]*?\)(?:\s*:\s*[^=(){};]+?)?)\s*=>\s*(?P<body>.+)$",
                          re.S)
_TS_TYPE_LITERAL = re.compile(r"(<\s*|\)\s*:\s*)\{([^{}]*)\}")
_TYPE_KEYWORDS = re.compile(
    r"\b(?:class|interface|struct|enum|record|namespace|module|type)\b"
)

# --------------------------------------------------------------------------- sources

_EXPR_SOURCES: dict[str, list[tuple[re.Pattern[str], str]]] = {
    "js": [
        (re.compile(r"\b(?:req|request|ctx\.request)\.(?:query|body|params|headers|cookies|"
                    r"signedCookies|files?)\b"), "HTTP input"),
        (re.compile(r"\b(?:window\.|document\.)?location\.(?:search|hash|href|pathname)\b"),
         BROWSER_PREFIX + "URL"),
        (re.compile(r"\bdocument\.(?:URL|documentURI|referrer|cookie)\b"), BROWSER_PREFIX + "DOM"),
        (re.compile(r"\bwindow\.name\b"), BROWSER_PREFIX + "window.name"),
        (re.compile(r"\bprocess\.argv\b"), LOCAL_PREFIX + "process.argv"),
    ],
    "csharp": [
        (re.compile(r"\b(?:HttpContext\.)?Request\.(?:Query|Form|Headers|Cookies|RouteValues|"
                    r"Body|QueryString|Path)\b"), "HTTP input"),
        (re.compile(r"\bConsole\.ReadLine\s*\(\s*\)"), LOCAL_PREFIX + "Console.ReadLine()"),
        (re.compile(r"\bEnvironment\.GetCommandLineArgs\s*\(\s*\)"),
         LOCAL_PREFIX + "command line"),
    ],
    "java": [
        (re.compile(r"\.\s*(?:getParameter|getParameterValues|getParameterMap|getHeader|"
                    r"getHeaders|getQueryString|getCookies|getPathInfo|getRequestURI|"
                    r"getInputStream|getReader)\s*\("), "HTTP input"),
        (re.compile(r"\bnew\s+Scanner\s*\(\s*System\.in\s*\)|\bSystem\.in\b"),
         LOCAL_PREFIX + "System.in"),
    ],
}

_PARAM_SOURCES: dict[str, re.Pattern[str]] = {
    "js": re.compile(r"@(?:Body|Query|Param|Headers|Req|Request|UploadedFiles?|Ip|HostParam)\s*\("),
    "csharp": re.compile(r"\[\s*From(?:Query|Body|Route|Form|Header)\b"),
    "java": re.compile(
        r"@(?:RequestParam|PathVariable|RequestBody|RequestHeader|CookieValue|ModelAttribute|"
        r"RequestPart|MatrixVariable)\b"
    ),
}
# ASP.NET minimal-API endpoint lambdas / controller actions: string and DTO
# parameters carry request data; injected services do not.
_DTO_TYPE = re.compile(r"^(?:string\??|[\w.]*(?:Request|Dto|DTO|Input|Command|Body|Form|"
                       r"Query|Model|Payload)\??)$")
_MINIMAL_API = re.compile(r"\.Map(?:Get|Post|Put|Delete|Patch|Methods)?\s*\(")
_ENDPOINT_LAMBDA = {
    "csharp": _MINIMAL_API,
    "js": re.compile(r"\b(?:app|router|server|api|route)\.(?:get|post|put|delete|patch|all)\s*\("),
    "java": re.compile(r"(?!x)x"),
}
# Next.js App Router: `export async function POST(request: Request)` in route.ts.
_NEXT_ROUTE_FILE = re.compile(r"(?:^|/)route\.(?:[cm]?[jt]sx?)$")
_NEXT_HANDLERS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})
_ASPNET_CONTROLLER = re.compile(r":\s*(?:ControllerBase|Controller)\b|\[ApiController\]")

# --------------------------------------------------------------------------- sinks


@dataclass(frozen=True)
class _Sink:
    pattern: re.Pattern[str]
    kind: str
    arg: int  # index, -1 = last, -2 = any argument
    bare_only: bool = False  # only when the argument is a plain reference


def _s(pattern: str, kind: str, arg: int = 0, bare_only: bool = False) -> _Sink:
    return _Sink(re.compile(pattern), kind, arg, bare_only)


_CALL_SINKS: dict[str, list[_Sink]] = {
    "js": [
        _s(r"\.(?:query|execute|raw|\$queryRawUnsafe|\$executeRawUnsafe)\s*\(", "sql"),
        _s(r"(?:(?<![\w$.])|\b(?:child_process|cp|childProcess)\.)(?:exec|execSync)\s*\(",
           "command"),
        _s(r"(?<![\w$.])eval\s*\(|\bvm\.(?:runInNewContext|runInThisContext|runInContext)\s*\(",
           "code"),
        _s(r"\bnew\s+Function\s*\(", "code", -1),
        _s(r"\bdocument\.write(?:ln)?\s*\(", "xss"),
        _s(r"\.insertAdjacentHTML\s*\(", "xss", 1),
        _s(r"\bfs(?:\.promises)?\.(?:readFile|readFileSync|writeFile|writeFileSync|appendFile|"
           r"appendFileSync|createReadStream|createWriteStream|unlink|unlinkSync|rm|rmSync|"
           r"readdir|readdirSync|open|openSync)\s*\(|(?<![\w$.])(?:readFile|writeFile|"
           r"createReadStream|createWriteStream|unlink)\s*\(", "path"),
        _s(r"\bres\.(?:sendFile|download)\s*\(", "path"),
        _s(r"(?<![\w$.])fetch\s*\(|\baxios(?:\.(?:get|post|put|delete|patch|head|request))?\s*\(|"
           r"\bgot(?:\.(?:get|post|put|delete|patch))?\s*\(|\bhttps?\.(?:get|request)\s*\(|"
           r"\bhttpService\.(?:get|post|put|delete|patch|request)\s*\(", "ssrf"),
        _s(r"\bres\.redirect\s*\(|\blocation\.(?:assign|replace)\s*\(", "redirect", -1),
        _s(r"\bNextResponse\.redirect\s*\(|(?<![\w$.])(?:redirect|permanentRedirect)\s*\(",
           "redirect"),
        _s(r"\.(?:find|findOne|findOneAndUpdate|findOneAndDelete|updateOne|updateMany|"
           r"deleteOne|deleteMany|countDocuments)\s*\(", "nosql", 0, bare_only=True),
        _s(r"\bnew\s+RegExp\s*\(|(?<![\w$.])RegExp\s*\(", "regex"),
    ],
    "csharp": [
        _s(r"\.(?:FromSqlRaw|ExecuteSqlRaw|ExecuteSqlRawAsync|SqlQueryRaw)\s*\(", "sql"),
        _s(r"\bnew\s+(?:Sql|Npgsql|MySql|Sqlite|SQLite|Oracle)Command\s*\(", "sql"),
        _s(r"\.(?:Query|QueryAsync|QueryFirst\w*|QuerySingle\w*|QueryMultiple\w*|"
           r"ExecuteScalar\w*|ExecuteReader\w*)(?:<[^>()]*>)?\s*\(", "sql"),
        _s(r"\bProcess\.Start\s*\(|\bnew\s+ProcessStartInfo\s*\(", "command", -2),
        _s(r"\bCSharpScript\.(?:EvaluateAsync|RunAsync|Create)\s*\(", "code"),
        _s(r"\bFile\.(?:ReadAllText|ReadAllBytes|ReadAllLines|ReadLines|OpenRead|OpenWrite|Open|"
           r"OpenText|Delete|WriteAllText|WriteAllBytes|WriteAllLines|AppendAllText|Copy|Move|"
           r"Create)(?:Async)?\s*\(|\bDirectory\.(?:Delete|GetFiles|EnumerateFiles|"
           r"GetDirectories)\s*\(|\bnew\s+(?:FileStream|StreamReader|StreamWriter)\s*\(|"
           r"\bPhysicalFile\s*\(|\bResults\.File\s*\(", "path"),
        _s(r"\.(?:GetAsync|GetStringAsync|GetByteArrayAsync|GetStreamAsync|PostAsync|PutAsync|"
           r"DeleteAsync|PatchAsync|GetFromJsonAsync|PostAsJsonAsync|PutAsJsonAsync)\s*\(|"
           r"\bWebRequest\.Create\s*\(", "ssrf"),
        _s(r"(?<![\w.])Redirect(?:Permanent)?\s*\(|\bResults\.Redirect\s*\(", "redirect"),
        _s(r"\bHtml\.Raw\s*\(|\bnew\s+HtmlString\s*\(", "xss"),
        _s(r"\.Deserialize\s*\(", "deserialization"),
        _s(r"\bnew\s+Regex\s*\(", "regex"),
        _s(r"\bRegex\.(?:IsMatch|Match|Matches|Replace|Split)\s*\(", "regex", 1),
    ],
    "java": [
        _s(r"\.(?:executeQuery|executeUpdate|executeLargeUpdate|execute|addBatch|"
           r"prepareStatement|prepareCall|createQuery|createNativeQuery|createSQLQuery|"
           r"queryForObject|queryForList|queryForMap|queryForRowSet|query|update|"
           r"batchUpdate)\s*\(", "sql"),
        _s(r"\bRuntime\.getRuntime\s*\(\s*\)\s*\.exec\s*\(", "command"),
        _s(r"\bnew\s+ProcessBuilder\s*\(|\.command\s*\(", "command", -2),
        _s(r"\bnew\s+(?:File|FileInputStream|FileOutputStream|FileReader|FileWriter|"
           r"RandomAccessFile)\s*\(|\b(?:Paths\.get|Path\.of)\s*\(", "path", -2),
        _s(r"\bFiles\.(?:readAllBytes|readAllLines|readString|lines|newInputStream|"
           r"newOutputStream|newBufferedReader|delete|deleteIfExists|write|writeString|copy|"
           r"move)\s*\(", "path"),
        _s(r"\bnew\s+URL\s*\(|\brestTemplate\.(?:getForObject|getForEntity|postForObject|"
           r"postForEntity|exchange|put|delete)\s*\(|\bWebClient\b[^;]*\.uri\s*\(|"
           r"\bURI\.create\s*\(", "ssrf"),
        _s(r"\.sendRedirect\s*\(", "redirect"),
        _s(r"\.getWriter\s*\(\s*\)\s*\.(?:write|print|println|printf)\s*\(", "xss"),
        _s(r"\bnew\s+(?:ObjectInputStream|XMLDecoder)\s*\(", "deserialization"),
        _s(r"\b(?:engine|scriptEngine|ScriptEngine)\w*\.eval\s*\(", "code"),
        _s(r"\bPattern\.compile\s*\(|\.matches\s*\(", "regex"),
    ],
}

_ASSIGN_SINKS: dict[str, list[tuple[re.Pattern[str], str]]] = {
    "js": [
        (re.compile(r"\.(?:innerHTML|outerHTML)$"), "xss"),
        (re.compile(r"^(?:window\.|document\.)?location(?:\.href)?$"), "redirect"),
        (re.compile(r"\.src$"), "xss"),
    ],
    "csharp": [
        (re.compile(r"\.CommandText$"), "sql"),
        (re.compile(r"\.(?:FileName|Arguments)$"), "command"),
    ],
    "java": [],
}
_JSX_HTML = re.compile(r"dangerouslySetInnerHTML\s*=\s*\{\{\s*__html\s*:")

_SANITIZERS: dict[str, re.Pattern[str]] = {
    "js": re.compile(
        r"^(?:parseInt|parseFloat|Number|Boolean|Math\.\w+|encodeURIComponent|encodeURI|"
        r"escape\w*|\w*[Ee]scape\w*|sanitize\w*|\w*[Ss]anitize\w*|DOMPurify\.sanitize|"
        r"validator\.\w+|path\.basename|basename|xss|he\.encode|crypto\.\w+|bcrypt\.\w+|"
        r"String\(\s*Number|isNaN|Array\.isArray|z\.\w+|\w+Schema\.parse|uuidv4|randomUUID)$"
    ),
    "csharp": re.compile(
        r"^(?:(?:int|long|short|decimal|double|float|bool|Guid|DateTime|DateOnly|Enum)\."
        r"(?:Parse|TryParse)|Convert\.To(?!String)\w+|\w*Html\w*Encode|HtmlEncoder\.\w+\.Encode|"
        r"Uri\.EscapeDataString|Uri\.EscapeUriString|Path\.GetFileName|Regex\.Escape|"
        r"\w*[Ss]anitize\w*|\w*Hash\w*|BCrypt\.\w+)$"
    ),
    "java": re.compile(
        r"^(?:Integer\.(?:parseInt|valueOf)|Long\.(?:parseLong|valueOf)|Double\.parseDouble|"
        r"Boolean\.parseBoolean|UUID\.fromString|ESAPI\.encoder\(\)\.\w+|"
        r"StringEscapeUtils\.escape\w*|HtmlUtils\.htmlEscape\w*|Encode\.for\w+|"
        r"FilenameUtils\.getName|\w*[Ss]anitize\w*|Pattern\.quote|URLEncoder\.encode)$"
    ),
}

_FOREACH = re.compile(
    r"^(?:for|foreach)\s*\(\s*(?:const|let|var|final)?\s*(?:[\w<>\[\],.?]+\s+)?"
    r"(?P<target>\{[^}]*\}|\[[^\]]*\]|" + _IDENT + r")\s*(?:of|in|:)\s*(?P<value>.+)\)\s*$",
    re.S,
)


# --------------------------------------------------------------------------- text helpers


def _mask(code: str, language: str) -> str:
    """Blank string-literal text (keeping quotes, newlines and interpolations)."""
    out = list(code)
    i, n = 0, len(code)
    while i < n:
        ch = code[i]
        interpolated = False
        verbatim = False
        if language == "csharp" and ch in "$@" and i + 1 < n and code[i + 1] in '"$@':
            j = i
            while j < n and code[j] in "$@":
                interpolated |= code[j] == "$"
                verbatim |= code[j] == "@"
                j += 1
            if j < n and code[j] == '"':
                i = j
                ch = '"'
            else:
                i += 1
                continue
        if ch == "`" and language == "js":
            i = _mask_template(code, out, i)
            continue
        if ch in "\"'":
            quote = ch
            j = i + 1
            depth = 0
            while j < n:
                c = code[j]
                if interpolated and c == "{":
                    if j + 1 < n and code[j + 1] == "{":
                        out[j] = out[j + 1] = " "
                        j += 2
                        continue
                    depth += 1
                    j += 1
                    continue
                if interpolated and c == "}" and depth:
                    depth -= 1
                    j += 1
                    continue
                if depth:
                    j += 1
                    continue
                if c == "\\" and not verbatim:
                    out[j] = " "
                    if j + 1 < n and code[j + 1] != "\n":
                        out[j + 1] = " "
                    j += 2
                    continue
                if c == quote:
                    if verbatim and j + 1 < n and code[j + 1] == quote:
                        out[j] = out[j + 1] = " "
                        j += 2
                        continue
                    break
                if c == "\n" and not verbatim:
                    break
                out[j] = " " if c != "\n" else "\n"
                j += 1
            i = j + 1
            continue
        i += 1
    return "".join(out)


def _mask_template(code: str, out: list[str], start: int) -> int:
    j, n = start + 1, len(code)
    while j < n:
        c = code[j]
        if c == "\\":
            out[j] = " "
            if j + 1 < n:
                out[j + 1] = " " if code[j + 1] != "\n" else "\n"
            j += 2
            continue
        if c == "`":
            return j + 1
        if c == "$" and j + 1 < n and code[j + 1] == "{":
            depth = 1
            j += 2
            while j < n and depth:
                if code[j] == "{":
                    depth += 1
                elif code[j] == "}":
                    depth -= 1
                elif code[j] == "`":
                    j = _mask_template(code, out, j)
                    continue
                j += 1
            continue
        if c != "\n":
            out[j] = " "
        j += 1
    return n


_URL_SINKS = frozenset({"redirect", "ssrf"})


def _url_head(arg: str) -> str | None:
    r"""The part of a URL expression that decides scheme and host.

    ``\`${base}/repos/${name}\``` -> ``base``; ``"https://x/" + id`` -> None
    (fixed host); a plain variable is its own head.
    """
    text = arg.strip()
    if text[:1] == "`":
        if text[1:3] == "${":
            close = _match_close(text, 2)
            return text[3:close]
        return None if text[1:2].isspace() or text[1:2] == "/" else text
    if text[:2] in ('$"', '@"') or text[:1] in "\"'":
        start = text.find('"') if text[:1] in "$@" else 0
        body = text[start + 1:]
        if text[:1] == "$" and body[:1] == "{":
            close = _match_close(body, 0)
            return body[1:close]
        return None if body[:1].isspace() or body[:1] == "/" else text
    parts = _split_top(text, "+")
    if len(parts) > 1:
        return _url_head(parts[0])
    return text


def _split_assignment(text: str) -> tuple[str, str, str] | None:
    """Split ``lhs op rhs`` at the first top-level assignment operator."""
    depth = 0
    for i, c in enumerate(text):
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "=" and depth == 0:
            nxt = text[i + 1] if i + 1 < len(text) else ""
            prev = text[i - 1] if i else ""
            if nxt in "=>" or prev in "=!<>":
                continue
            start = i
            op = "="
            if prev in "+-*/%|&^":
                op, start = prev + "=", i - 1
            elif prev == "?" and i >= 2 and text[i - 2] == "?":
                op, start = "??=", i - 2
            return text[:start], op, text[i + 1:]
    return None


def _match_close(text: str, start: int, open_ch: str = "(", close_ch: str = ")") -> int:
    """Index of the bracket closing ``text[start]`` (or len(text) if unbalanced)."""
    depth = 0
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack: list[str] = []
    for i in range(start, len(text)):
        c = text[i]
        if c in pairs:
            stack.append(pairs[c])
            depth += 1
        elif c in ")]}":
            if stack and stack[-1] == c:
                stack.pop()
            depth -= 1
            if depth == 0:
                return i
    return len(text)


def _split_top(text: str, sep: str = ",") -> list[str]:
    parts: list[str] = []
    depth = 0
    angle = 0
    current: list[str] = []
    for c in text:
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "<":
            angle += 1
        elif c == ">" and angle:
            angle -= 1
        if c == sep and depth == 0 and angle == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(c)
    if "".join(current).strip():
        parts.append("".join(current))
    return parts


# --------------------------------------------------------------------------- frontend


@dataclass
class _Region:
    start: int  # index of "{"
    end: int  # index of matching "}"
    header: str
    header_start: int


class _Lowerer:
    def __init__(self, file: str, source: str, language: str) -> None:
        self.file = file
        self.language = language
        delims = ('"', "'", "`") if language == "js" else ('"', "'")
        cleaned = strip_comments(source, string_delims=delims)
        self.code = _mask(cleaned, language)
        if language == "js":
            # `Promise<{ id: string }>` / `(): { a: T }`: type literals, not blocks.
            for _ in range(3):
                self.code = _TS_TYPE_LITERAL.sub(
                    lambda m: m.group(1) + " " + m.group(2) + " ", self.code
                )
        self.raw_lines = source.splitlines()
        self.line_starts = [0]
        for index, ch in enumerate(self.code):
            if ch == "\n":
                self.line_starts.append(index + 1)
        self.sources = _EXPR_SOURCES[language]
        self.sanitizer = _SANITIZERS[language]
        self.extra_functions: list[Function] = []
        self.controller = bool(_ASPNET_CONTROLLER.search(self.code)) and language == "csharp"

    def line_of(self, offset: int) -> int:
        lo, hi = 0, len(self.line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    def text_at(self, line: int) -> str:
        return self.raw_lines[line - 1].strip()[:160] if 0 < line <= len(self.raw_lines) else ""

    # ------------------------------------------------------------ functions
    def regions(self) -> list[_Region]:
        code = self.code
        found: list[_Region] = []
        stack: list[tuple[int, bool]] = []  # (offset, is_function)
        boundary = -1  # last `;`, `{` or `}`: a header never spans one
        for i, ch in enumerate(code):
            if ch == ";":
                boundary = i
            elif ch == "{":
                header_start = boundary + 1
                boundary = i
                header = code[header_start:i]
                is_function = self._is_function_header(header)
                inside_function = any(f for _, f in stack)
                stack.append((i, is_function))
                # Endpoint lambdas registered inside a setup method
                # (`group.MapPost("/login", async (LoginRequest r) => {...})`)
                # are units of their own: their parameters are request data.
                endpoint = is_function and bool(_ENDPOINT_LAMBDA[self.language].search(header))
                if is_function and (not inside_function or endpoint):
                    end = _match_close(code, i, "{", "}")
                    found.append(_Region(i, end, header, header_start))
            elif ch == "}":
                boundary = i
                if stack:
                    stack.pop()
        return found

    @staticmethod
    def _is_function_header(header: str) -> bool:
        stripped = header.strip()
        if not stripped or _TYPE_KEYWORDS.search(stripped.split("(", 1)[0]):
            return False
        if re.search(r"=>\s*$", stripped):
            return True
        match = _HEADER_TAIL.search(stripped)
        if not match:
            return False
        close = match.start()
        depth = 0
        for k in range(close, -1, -1):
            if stripped[k] == ")":
                depth += 1
            elif stripped[k] == "(":
                depth -= 1
                if depth == 0:
                    before = re.search(r"(" + _IDENT + r")\s*(?:<[^()]*>)?\s*$", stripped[:k])
                    if before is None:
                        return False
                    return before.group(1) not in _CONTROL
        return False

    def function_for(self, region: _Region) -> Function:
        body = self.statements(region.start + 1, region.end)
        line = self.line_of(region.header_start + len(region.header) - len(region.header.lstrip()))
        return self._build_function(region.header.strip(), body, line)

    def _build_function(self, header: str, body: list[Stmt], line: int) -> Function:
        params_text, name = self._params_and_name(header)
        params: list[str] = []
        tainted: dict[int, str] = {}
        param_source = _PARAM_SOURCES[self.language]
        minimal_api = self.language == "csharp" and bool(_MINIMAL_API.search(header))
        if minimal_api:
            name = "<endpoint>"
        for raw in _split_top(params_text):
            param, type_name = self._param_name(raw)
            if not param:
                continue
            params.append(param)
            position = len(params) - 1
            if param_source.search(raw):
                tainted[position] = f"request parameter `{param}` of {name}() (HTTP input)"
            elif (minimal_api or (self.controller and "public" in header)) and type_name and \
                    _DTO_TYPE.match(type_name):
                tainted[position] = f"endpoint parameter `{param}` of {name}() (HTTP input)"
        if (
            self.language == "js" and name in _NEXT_HANDLERS and params
            and _NEXT_ROUTE_FILE.search(self.file)
        ):
            tainted.setdefault(0, f"Next.js route handler `{params[0]}` of {name}() (HTTP input)")
        return Function(self.file, name, params, body, line, tainted)

    def _params_and_name(self, header: str) -> tuple[str, str]:
        arrow = re.search(r"=>\s*$", header)
        work = header[: arrow.start()].rstrip() if arrow else header
        if arrow and not work.endswith(")"):
            ident = re.search(r"(" + _IDENT + r")\s*$", work)
            name = self._name_before(work[: ident.start()] if ident else work) or "<lambda>"
            return (ident.group(1) if ident else ""), name
        # Skip a return type / throws / where clause to reach the parameter list.
        tail = _HEADER_TAIL.search(work)
        if tail is None:
            return "", "<anonymous>"
        close = tail.start()
        depth = 0
        open_index = 0
        for k in range(close, -1, -1):
            if work[k] == ")":
                depth += 1
            elif work[k] == "(":
                depth -= 1
                if depth == 0:
                    open_index = k
                    break
        params_text = work[open_index + 1: close]
        before = work[:open_index]
        ident = re.search(r"(" + _IDENT + r")\s*(?:<[^()]*>)?\s*$", before)
        name = ident.group(1) if ident else ""
        if not name or name in ("function", "async"):
            name = self._name_before(before) or "<anonymous>"
        return params_text, name

    @staticmethod
    def _name_before(text: str) -> str:
        assign = re.search(r"(" + _IDENT + r")\s*(?::[^=]*)?=\s*(?:async\s*)?(?:function\s*)?$",
                           text.strip())
        if assign:
            return assign.group(1)
        prop = re.search(r"(" + _IDENT + r")\s*:\s*(?:async\s*)?(?:function\s*)?$", text.strip())
        return prop.group(1) if prop else ""

    def _param_name(self, raw: str) -> tuple[str, str]:
        text = re.sub(r"@\w+(?:\.\w+)*\s*(?:\([^()]*\))?", " ", raw)  # TS/Java decorators
        text = re.sub(r"\[[^\]]*\]", " ", text) if self.language == "csharp" else text
        text = text.split("=", 1)[0].strip()
        text = re.sub(r"^(?:public|private|protected|readonly|final|this|params|ref|out|in|"
                      r"override)\s+", "", text)
        if not text or text.startswith(("{", "[")):
            return "", ""
        if self.language == "js":
            name = text.split(":", 1)[0].strip().lstrip(".").rstrip("?")
            type_name = text.split(":", 1)[1].strip() if ":" in text else ""
            return (name if re.fullmatch(_IDENT, name) else ""), type_name
        parts = text.split()
        name = parts[-1] if parts else ""
        type_name = " ".join(parts[:-1])
        return (name if re.fullmatch(_IDENT, name) else ""), type_name

    # ------------------------------------------------------------ statements
    def statements(self, start: int, end: int) -> list[Stmt]:
        code = self.code
        out: list[Stmt] = []
        depth = 0
        braces: list[bool] = []  # True for a block brace, False for a literal
        seg_start = start
        for i in range(start, end):
            c = code[i]
            if c in "([":
                depth += 1
            elif c in ")]":
                depth = max(0, depth - 1)
            elif depth == 0 and c == "{":
                block = self._is_block_brace(code, i)
                braces.append(block)
                if block:
                    self._statement(seg_start, i, out)
                    seg_start = i + 1
            elif depth == 0 and c == "}":
                block = braces.pop() if braces else True
                if block:
                    self._statement(seg_start, i, out)
                    seg_start = i + 1
            elif depth == 0 and c == ";" and not any(not b for b in braces):
                self._statement(seg_start, i, out)
                seg_start = i + 1
        self._statement(seg_start, end, out)
        return out

    @staticmethod
    def _is_block_brace(code: str, i: int) -> bool:
        head_start = max(code.rfind(c, max(0, i - 400), i) for c in ";{}") + 1
        if _TYPE_KEYWORDS.search(code[head_start:i].split("(", 1)[0]):
            return True  # class/namespace/interface body
        k = i - 1
        while k >= 0 and code[k] in " \t\r\n":
            k -= 1
        if k < 0:
            return True
        prev = code[k]
        if prev in ")>;{}":
            return prev != ">" or code[k - 1] == "="  # `=> {` is a body
        word = re.search(r"(\w+)$", code[max(0, k - 12): k + 1])
        return bool(word and word.group(1) in ("else", "try", "finally", "do", "get", "set",
                                               "init", "checked", "unchecked", "unsafe"))

    def _statement(self, start: int, end: int, out: list[Stmt]) -> None:
        text = self.code[start:end]
        stripped = text.strip()
        if not stripped:
            return
        offset = start + (len(text) - len(text.lstrip()))
        line = self.line_of(offset)
        shown = self.text_at(line)
        # Drop a leading `else` / `case x:` / labels.
        stripped = re.sub(r"^(?:else|case\s+[^:]+:|default\s*:)\s*", "", stripped)

        sinks: list[Stmt] = []
        self._call_sinks(stripped, line, shown, sinks)
        jsx = _JSX_HTML.search(stripped) if self.language == "js" else None
        if jsx:
            value_start = jsx.end()
            value_end = stripped.find("}}", value_start)
            sinks.append(Stmt(line, shown, self.expr(stripped[value_start:value_end]),
                              sink="xss"))

        if stripped.startswith("return ") or stripped == "return":
            out.extend(sinks)
            out.append(Stmt(line, shown, self.expr(stripped[6:]), is_return=True))
            return
        foreach = _FOREACH.match(stripped)
        if foreach:
            out.extend(sinks)
            out.append(Stmt(line, shown, self.expr(foreach.group("value")),
                            targets=self._targets(foreach.group("target"))))
            return
        if re.match(r"^(?:if|while|switch|for|foreach|catch|using|lock)\b", stripped):
            out.extend(sinks)
            out.append(Stmt(line, shown, self.expr(stripped)))
            return
        if self.language == "csharp" and _MINIMAL_API.search(stripped):
            self.extra_functions.extend(self._endpoint_lambdas(stripped, line))
        expr_body = self._expression_bodied(stripped, line)
        if expr_body is not None:
            self.extra_functions.append(expr_body)
            return
        assignment = _split_assignment(stripped)
        if assignment and not re.match(r"^(?:return|throw|yield)\b", stripped):
            lhs, op, rhs = assignment
            value = self.expr(rhs)
            declared = self._declared(lhs)
            if declared is not None:
                targets = self._targets(declared)
                if op != "=":
                    value.names |= set(targets)
                out.extend(sinks)
                out.append(Stmt(line, shown, value, targets=targets))
                return
            for pattern, kind in _ASSIGN_SINKS[self.language]:
                if pattern.search(lhs.strip()):
                    sinks.append(Stmt(line, shown, value, sink=kind))
            out.extend(sinks)
            out.append(Stmt(line, shown, value))
            return
        out.extend(sinks)
        out.append(Stmt(line, shown, self.expr(stripped)))

    def _declared(self, lhs: str) -> str | None:
        """The declared/assigned variable (or destructuring pattern) in ``lhs``."""
        text = re.sub(r"^(?:export\s+)?(?:(?:const|let|var|final|readonly|static|using|await)\s+)+",
                      "", lhs.strip())
        if text.startswith(("{", "[")):
            return text
        if self.language == "js" and ":" in text:
            text = _split_top(text, ":")[0].strip()
        text = re.sub(r"<[^<>]*(?:<[^<>]*>[^<>]*)*>", "", text).strip()  # generics
        index = re.fullmatch(r"(" + _IDENT + r")\s*\[.*\]", text, re.S)
        if index:
            return index.group(1)  # `items[i] = x` taints the container
        if re.fullmatch(_IDENT, text):
            return text
        typed = re.fullmatch(r"(?:[\w$.\[\]?]+\s+)+(" + _IDENT + r")", text)
        if typed and typed.group(1) not in _KEYWORDS:
            return typed.group(1)
        return None

    def _expression_bodied(self, text: str, line: int) -> Function | None:
        """`Get(string q) => Redirect(q)` / `const h = (req, res) => res.send(x)`."""
        found = _EXPR_BODIED.match(text)
        if not found or found.group("body").lstrip().startswith("{"):
            return None
        head = found.group("head")
        if head.count("(") != head.count(")") or not self._is_function_header(head + " =>"):
            return None  # `exec(cmd, (err, out) => ...)` is a call, not a method
        # Report on the line holding `=>`, not on a leading attribute/decorator.
        line += head.count("\n")
        sinks: list[Stmt] = []
        shown = self.text_at(line)
        body_text = found.group("body")
        self._call_sinks(body_text, line, shown, sinks)
        body = [*sinks, Stmt(line, shown, self.expr(body_text), is_return=True)]
        return self._build_function(head + " =>", body, line)

    @staticmethod
    def _targets(text: str) -> list[str]:
        text = text.strip()
        if text.startswith(("{", "[")):
            names: list[str] = []
            for part in _split_top(text[1:-1]):
                part = part.strip().lstrip(".")
                if not part:
                    continue
                if ":" in part:  # `{ a: renamed = default }`
                    part = part.split(":", 1)[1]
                part = part.split("=", 1)[0].strip()
                if re.fullmatch(_IDENT, part):
                    names.append(part)
            return names
        return [text] if re.fullmatch(_IDENT, text) else []

    def _call_sinks(self, text: str, line: int, shown: str, out: list[Stmt]) -> None:
        for sink in _CALL_SINKS[self.language]:
            for found in sink.pattern.finditer(text):
                sink_line = line + text.count("\n", 0, found.start())
                sink_shown = self.text_at(sink_line) if sink_line != line else shown
                open_index = found.end() - 1
                if text[open_index] != "(":
                    continue
                close = _match_close(text, open_index)
                args = _split_top(text[open_index + 1: close])
                if not args:
                    continue
                if sink.kind == "command" and self.language == "js" and "spawn" in found.group(0):
                    continue
                if sink.arg == -2:
                    chosen = args
                elif sink.arg == -1:
                    chosen = [args[-1]]
                elif sink.arg < len(args):
                    chosen = [args[sink.arg]]
                else:
                    continue
                for arg in chosen:
                    if sink.bare_only and not re.fullmatch(r"\s*[\w$.]+\s*", arg):
                        continue
                    head = arg
                    if sink.kind in _URL_SINKS:
                        url_head = _url_head(arg)
                        if url_head is None:
                            continue  # fixed scheme/host: input only reaches path/query
                        head = url_head
                    out.append(Stmt(sink_line, sink_shown, self.expr(head), sink=sink.kind))

    # ----------------------------------------------------------- expressions
    def expr(self, text: str, depth: int = 0) -> Expr:
        result = Expr()
        text = text.strip()
        if not text or depth > 6:
            return result
        for pattern, label in self.sources:
            for found in pattern.finditer(text):
                matched = " ".join(found.group(0).split()).rstrip("(")
                prefix = next(
                    (p for p in (LOCAL_PREFIX, BROWSER_PREFIX) if label.startswith(p)), ""
                )
                result.sources.append(f"{prefix}{matched} ({label.removeprefix(prefix)})")
            text = pattern.sub(" ", text)
        whole = re.match(r"(?:await\s+)?(?:new\s+)?([\w$.]+?)\s*(?:<[^()]*>)?\s*\(", text)
        if whole and self.sanitizer.match(whole.group(1)):
            close = _match_close(text, whole.end() - 1)
            rest = text[close + 1:].strip()
            if not rest or rest == "!" or re.fullmatch(r"(?:\.\w+)+", rest):
                inner = self.expr(text[whole.end(): close], depth + 1)
                return Expr(calls=inner.calls, sanitized=True)
        if re.search(r"\.(?:length|Length|Count|size\(\))\s*$", text) or re.match(
            r"^(?:!|typeof\b)", text
        ):
            return Expr(sanitized=True)
        i = 0
        n = len(text)
        while i < n:
            match = re.compile(_IDENT).match(text, i)
            if not match:
                i += 1
                continue
            ident = match.group(0)
            j = match.end()
            preceded_by_dot = i > 0 and text[i - 1] == "." and not text[max(0, i - 3):i] == "..."
            k = j
            if k < n and text[k] == "<":  # generic call `Query<T>(`
                close = text.find(">", k)
                if close != -1 and re.fullmatch(r"<[\w.,\s\[\]?<>]*", text[k:close]):
                    k = close + 1
            while k < n and text[k] in " \t":
                k += 1
            if k < n and text[k] == "(" and ident not in _CONTROL:
                close = _match_close(text, k)
                args = [self.expr(a, depth + 1) for a in _split_top(text[k + 1: close])]
                receiver_text = self._receiver(text, i - 1) if preceded_by_dot else ""
                dotted = f"{receiver_text}.{ident}" if receiver_text else ident
                if self.sanitizer.match(dotted) or self.sanitizer.match(ident):
                    # `${escapeHtml(q)}`: clean value; keep inner calls for sinks.
                    for arg in args:
                        result.calls.extend(arg.calls)
                else:
                    receiver = self.expr(receiver_text, depth + 1) if receiver_text else None
                    result.calls.append(Call(ident, args, 0, receiver))
                i = close + 1
                continue
            if not preceded_by_dot and ident not in _KEYWORDS and ident != "$":
                result.names.add(ident)
            i = j
        return result

    @staticmethod
    def _receiver(text: str, dot: int) -> str:
        """The expression before ``.method(`` (identifiers, member access, calls)."""
        k = dot - 1
        while k >= 0:
            c = text[k]
            if c in ")]":
                depth = 0
                while k >= 0:
                    if text[k] in ")]":
                        depth += 1
                    elif text[k] in "([":
                        depth -= 1
                        if depth == 0:
                            break
                    k -= 1
                k -= 1
                continue
            if c.isalnum() or c in "_$.?!":
                k -= 1
                continue
            break
        return text[k + 1: dot]

    def module_function(self, regions: list[_Region]) -> list[Function]:
        """Code outside every function: C# top-level statements, module setup.

        Expression-bodied endpoint lambdas there (``app.MapGet("/u", (string q)
        => db.Query(q))``) become their own functions with tainted params.
        """
        chars = list(self.code)
        for region in regions:
            for k in range(region.start + 1, region.end):
                if chars[k] != "\n":
                    chars[k] = " "
        saved = self.code
        self.code = "".join(chars)
        try:
            body = self.statements(0, len(self.code))
            functions = [Function(self.file, "<module>", [], body, 1)]
        finally:
            self.code = saved
        return functions

    def _endpoint_lambdas(self, text: str, line: int) -> list[Function]:
        """Expression-bodied endpoint lambdas: ``MapGet("/u", (string q) => Use(q))``."""
        functions: list[Function] = []
        for found in _MINIMAL_API.finditer(text):
            open_index = found.end() - 1
            close = _match_close(text, open_index)
            args = _split_top(text[open_index + 1: close])
            if len(args) < 2:
                continue
            handler = args[-1].strip()
            lam = re.match(r"^(?:async\s+)?\(([^()]*)\)\s*=>\s*(.+)$", handler, re.S)
            if not lam or lam.group(2).lstrip().startswith("{"):
                continue
            body_text = lam.group(2)
            body_line = line + text.count("\n", 0, text.find(body_text, open_index))
            sinks: list[Stmt] = []
            self._call_sinks(body_text, body_line, self.text_at(body_line), sinks)
            body = [*sinks, Stmt(body_line, self.text_at(body_line), self.expr(body_text),
                                 is_return=True)]
            header = f"{text[:open_index + 1]}{', '.join(args[:-1])}, ({lam.group(1)}) =>"
            functions.append(self._build_function(header, body, line))
        return functions

    def lower(self) -> list[Function]:
        regions = self.regions()
        functions = [self.function_for(region) for region in regions]
        functions.extend(self.module_function(regions))
        functions.extend(self.extra_functions)
        for function in functions:
            for stmt in function.body:
                for call in _iter_calls(stmt.value):
                    call.line = stmt.line
        return functions


def _iter_calls(expr: Expr) -> list[Call]:
    calls: list[Call] = []
    for call in expr.calls:
        calls.append(call)
        for arg in call.args:
            calls.extend(_iter_calls(arg))
        if call.receiver is not None:
            calls.extend(_iter_calls(call.receiver))
    return calls


def lower_clike(file: str, source: str) -> list[Function]:
    suffix = file[file.rfind("."):].lower() if "." in file else ""
    language = LANGUAGE_BY_EXT.get(suffix)
    if language is None:
        return []
    return _Lowerer(file, source, language).lower()
