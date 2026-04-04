from __future__ import annotations

import threading

from archmap.core.parser.cpp_parser import CParser, CppParser
from archmap.core.parser.csharp_parser import CSharpParser
from archmap.core.parser.go_parser import GoParser
from archmap.core.parser.java_parser import JavaParser
from archmap.core.parser.js_parser import JSParser
from archmap.core.parser.php_parser import PHPParser
from archmap.core.parser.python_parser import PythonParser
from archmap.core.parser.registry import LanguageRegistry, registry
from archmap.core.parser.rust_parser import RustParser
from archmap.core.parser.ts_parser import TSParser

_bootstrap_lock = threading.Lock()
_DEFAULT_REGISTRY_BOOTSTRAPPED = False


def register_core_parsers(target_registry: LanguageRegistry | None = None) -> LanguageRegistry:
    active_registry = target_registry or registry
    for parser in (
        PythonParser(),
        JSParser(),
        TSParser(),
        RustParser(),
        GoParser(),
        PHPParser(),
        JavaParser(),
        CParser(),
        CppParser(),
        CSharpParser(),
    ):
        active_registry.register(parser)
    return active_registry


def ensure_default_registry() -> LanguageRegistry:
    """
    Garante que o registro padrão de parsers foi inicializado.
    Esta função é thread-safe e idempotente.
    """
    global _DEFAULT_REGISTRY_BOOTSTRAPPED

    if not _DEFAULT_REGISTRY_BOOTSTRAPPED:
        with _bootstrap_lock:
            if not _DEFAULT_REGISTRY_BOOTSTRAPPED:
                register_core_parsers(registry)
                _DEFAULT_REGISTRY_BOOTSTRAPPED = True

    return registry
