from __future__ import annotations

from archmap.core.parser.go_parser import GoParser
from archmap.core.parser.js_parser import JSParser
from archmap.core.parser.plugins import register_generic_parsers
from archmap.core.parser.python_parser import PythonParser
from archmap.core.parser.registry import LanguageRegistry, registry
from archmap.core.parser.rust_parser import RustParser
from archmap.core.parser.ts_parser import TSParser

_DEFAULT_REGISTRY_BOOTSTRAPPED = False


def register_core_parsers(target_registry: LanguageRegistry | None = None) -> LanguageRegistry:
    active_registry = target_registry or registry
    for parser in (PythonParser(), JSParser(), TSParser(), RustParser(), GoParser()):
        active_registry.register(parser)
    return active_registry


def ensure_default_registry() -> LanguageRegistry:
    global _DEFAULT_REGISTRY_BOOTSTRAPPED

    if _DEFAULT_REGISTRY_BOOTSTRAPPED:
        return registry

    register_core_parsers(registry)
    register_generic_parsers(registry)
    _DEFAULT_REGISTRY_BOOTSTRAPPED = True
    return registry
