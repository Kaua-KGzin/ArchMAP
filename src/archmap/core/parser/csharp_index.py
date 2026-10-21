"""Project-wide C# type index for precise ``using`` resolution.

A C# ``using Company.App.Services;`` makes a whole namespace visible, it does
not import any particular file. Linking the directive to every file of the
namespace (the historical behaviour) turns each namespace into a clique: on a
real backend every service "depended on" every other service, producing
phantom cycles, inflated fan-in and a failing health grade.

This index records which types (and extension methods) each file declares per
namespace. A file then depends on another file only when it actually
references one of that file's types through a visible namespace: its
``using`` directives, project-wide ``global using`` directives, its own
namespace and that namespace's parents (C# scoping rules), or a fully
qualified name. Everything is regex based so it works without tree-sitter.
"""

from __future__ import annotations

import re
import threading
import weakref
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from archmap.core.parser._text import strip_comments

_NAMESPACE_RE = re.compile(r"^\s*namespace\s+([A-Za-z_][\w.]*)\s*[;{]?", re.MULTILINE)
_TYPE_RE = re.compile(
    r"\b(?:class|interface|struct|enum|record(?:\s+(?:class|struct))?)\s+@?([A-Za-z_]\w*)"
)
_DELEGATE_RE = re.compile(r"\bdelegate\s+[\w<>\[\],.?\s]+?\s([A-Za-z_]\w*)\s*[<(]")
_EXTENSION_RE = re.compile(
    r"\bstatic\s+[\w<>\[\],.?\s]+?\s([A-Za-z_]\w*)\s*(?:<[^>()]*>)?\s*\(\s*this\s"
)
_GLOBAL_USING_RE = re.compile(
    r"^\s*global\s+using\s+(?!static\b)(?:[A-Za-z_]\w*\s*=\s*)?([A-Za-z_][\w.]*)\s*;",
    re.MULTILINE,
)
_DIRECTIVE_LINE_RE = re.compile(
    r"^\s*(?:global\s+)?(?:using|namespace)\b[^;{\n]*[;{]?", re.MULTILINE
)
_STRING_RE = re.compile(
    r'@"(?:[^"]|"")*"|"""[\s\S]*?"""|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])\''
)
_ENUM_BODY_RE = re.compile(r"\benum\s+[A-Za-z_]\w*[^{;]*\{[^}]*\}")
_IDENT_RE = re.compile(r"\b[A-Za-z_]\w*\b")
_QUALIFIED_RE = re.compile(r"\b[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+\b")


@dataclass
class _FileFacts:
    namespaces: list[str]
    types: set[str]
    extension_methods: set[str]
    identifiers: set[str] = field(default_factory=set)
    qualified: set[str] = field(default_factory=set)


@dataclass
class CSharpIndex:
    files: dict[str, _FileFacts] = field(default_factory=dict)
    # namespace -> type name -> declaring files
    types: dict[str, dict[str, set[str]]] = field(default_factory=dict)
    # namespace -> extension method name -> declaring files
    extensions: dict[str, dict[str, set[str]]] = field(default_factory=dict)
    global_usings: set[str] = field(default_factory=set)

    def has_namespace(self, namespace: str) -> bool:
        return namespace in self.types or namespace in self.extensions

    def type_files(self, qualified: str) -> set[str]:
        """Files declaring ``Namespace.Type`` (empty when it isn't a project type)."""
        namespace, _, name = qualified.rpartition(".")
        return set(self.types.get(namespace, {}).get(name, ()))

    def is_known(self, specifier: str) -> bool:
        return self.has_namespace(specifier) or bool(self.type_files(specifier))

    def dependencies_of(self, file_id: str, usings: Iterable[str]) -> set[str]:
        facts = self.files.get(file_id)
        if facts is None:
            return set()
        targets: set[str] = set()
        visible = {""} | self.global_usings
        for namespace in facts.namespaces:
            parts = namespace.split(".")
            visible.update(".".join(parts[:i]) for i in range(1, len(parts) + 1))
        for using in usings:
            if self.has_namespace(using):
                visible.add(using)
            else:
                # `using static Ns.Type;` / `using Alias = Ns.Type;`
                targets |= self.type_files(using)

        for namespace in visible:
            declared = self.types.get(namespace)
            if declared:
                # Skip names the file declares itself: other `partial` parts of
                # the same type (EF migrations + .Designer.cs) are not a cycle.
                for name in facts.identifiers - facts.types:
                    files = declared.get(name) or declared.get(name + "Attribute")
                    if files:
                        targets |= files
            methods = self.extensions.get(namespace)
            if methods:
                for name in facts.identifiers & methods.keys():
                    targets |= methods[name]

        for dotted in facts.qualified:
            parts = dotted.split(".")
            for i in range(1, len(parts)):
                files = self.type_files(".".join(parts[: i + 1]))
                if files:
                    targets |= files
                    break

        targets.discard(file_id)
        return targets


def _code_only(source: str) -> str:
    return _STRING_RE.sub('""', strip_comments(source))


_NAMESPACE_OPEN_RE = re.compile(r"\bnamespace\s+[A-Za-z_][\w.]*\s*$")


def _top_level_mask(code: str) -> Callable[[int], bool]:
    """``is_top_level(offset)``: True when only namespace blocks enclose ``offset``.

    Nested types (``private record LoginBody`` inside a test class) are not
    visible by their bare name elsewhere, so indexing them would invent edges.
    """
    boundaries: list[int] = []  # offsets where top-level-ness flips
    stack: list[bool] = []  # True for a namespace block
    top = True
    for i, ch in enumerate(code):
        if ch == "{":
            stack.append(bool(_NAMESPACE_OPEN_RE.search(code[max(0, i - 200):i])))
        elif ch == "}" and stack:
            stack.pop()
        else:
            continue
        now_top = all(stack)
        if now_top != top:
            boundaries.append(i)
            top = now_top

    def is_top_level(offset: int) -> bool:
        flips = sum(1 for b in boundaries if b < offset)
        return flips % 2 == 0

    return is_top_level


def _facts(source: str) -> tuple[_FileFacts, set[str]]:
    code = _code_only(source)
    namespaces = _NAMESPACE_RE.findall(code) or [""]
    top_level = _top_level_mask(code)
    types = {
        m.group(1)
        for regex in (_TYPE_RE, _DELEGATE_RE)
        for m in regex.finditer(code)
        if top_level(m.start())
    }
    extensions = set(_EXTENSION_RE.findall(code))
    global_usings = set(_GLOBAL_USING_RE.findall(code))
    # Enum members (`InventoryMovementType { Sale, PurchaseEntry }`) are not
    # type references even when they share a name with an entity class.
    body = _ENUM_BODY_RE.sub(" ", _DIRECTIVE_LINE_RE.sub(" ", code))
    facts = _FileFacts(
        namespaces=namespaces,
        types=types,
        extension_methods=extensions,
        identifiers=set(_IDENT_RE.findall(body)),
        qualified=set(_QUALIFIED_RE.findall(body)),
    )
    return facts, global_usings


def build_index(
    file_ids: Iterable[str], get_file_content: Callable[[str], str | None]
) -> CSharpIndex:
    index = CSharpIndex()
    for file_id in sorted(file_ids):
        if not file_id.endswith(".cs"):
            continue
        source = get_file_content(file_id)
        if source is None:
            continue
        facts, global_usings = _facts(source)
        index.files[file_id] = facts
        index.global_usings |= global_usings
        for namespace in facts.namespaces:
            for name in facts.types:
                index.types.setdefault(namespace, {}).setdefault(name, set()).add(file_id)
            for name in facts.extension_methods:
                index.extensions.setdefault(namespace, {}).setdefault(name, set()).add(file_id)
            # Register the namespace itself even when it declares nothing.
            index.types.setdefault(namespace, {})
    return index


# One index per parse run: parse_project creates a fresh ``get_file_content``
# closure for every run, so keying on it scopes the cache to that run and lets
# the index be collected with it.
_INDEXES: weakref.WeakKeyDictionary[Callable[[str], str | None], CSharpIndex] = (
    weakref.WeakKeyDictionary()
)
_LOCK = threading.Lock()


def index_for(
    file_ids: set[str], get_file_content: Callable[[str], str | None] | None
) -> CSharpIndex | None:
    if get_file_content is None:
        return None
    with _LOCK:
        try:
            index = _INDEXES.get(get_file_content)
        except TypeError:
            return None
        if index is None:
            index = build_index(file_ids, get_file_content)
            try:
                _INDEXES[get_file_content] = index
            except TypeError:
                pass
        return index
