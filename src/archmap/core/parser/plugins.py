from __future__ import annotations

import re

from archmap.core.parser.generic_parser import GenericParser
from archmap.core.parser.registry import LanguageRegistry, registry

_CPP_PATTERNS = [
    re.compile(r'^\s*#include\s+["<]([^">]+)[">]', re.MULTILINE),
]

_GENERIC_PARSER_SPECS = (
    {
        "language": "php",
        "extensions": [".php"],
        "patterns": [
            re.compile(r"^\s*use\s+([^;]+);", re.MULTILINE),
            re.compile(r"^\s*require(?:_once)?\s*\(?\s*['\"]([^'\"]+)['\"]", re.MULTILINE),
            re.compile(r"^\s*include(?:_once)?\s*\(?\s*['\"]([^'\"]+)['\"]", re.MULTILINE),
        ],
    },
    {
        "language": "java",
        "extensions": [".java"],
        "patterns": [re.compile(r"^\s*import\s+([^;]+);", re.MULTILINE)],
    },
    {
        "language": "csharp",
        "extensions": [".cs"],
        "patterns": [re.compile(r"^\s*using\s+([^;]+);", re.MULTILINE)],
    },
    {
        "language": "c",
        "extensions": [".c", ".h"],
        "patterns": _CPP_PATTERNS,
    },
    {
        "language": "cpp",
        "extensions": [".cpp", ".hpp", ".cc", ".cxx"],
        "patterns": _CPP_PATTERNS,
    },
)


def register_generic_parsers(target_registry: LanguageRegistry | None = None) -> LanguageRegistry:
    active_registry = target_registry or registry

    for spec in _GENERIC_PARSER_SPECS:
        active_registry.register(GenericParser(**spec))

    return active_registry
