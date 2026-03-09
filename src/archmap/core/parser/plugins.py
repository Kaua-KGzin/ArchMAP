from __future__ import annotations

import re

from archmap.core.parser.generic_parser import GenericParser
from archmap.core.parser.registry import registry

# Go
registry.register(
    GenericParser(
        language="go",
        extensions=[".go"],
        patterns=[
            re.compile(r'^\s*import\s+"([^"]+)"', re.MULTILINE),
            re.compile(r'^\s*import\s+\((?:[^"]*"([^"]+)")+[^)]*\)', re.MULTILINE | re.DOTALL), # This might be complex
            # Simpler: just match any quoted string in lines that look like parts of an import block
            re.compile(r'^\s*"([^"]+)"', re.MULTILINE), # Rough but effective for multi-line imports
        ],
    )
)

# PHP
registry.register(
    GenericParser(
        language="php",
        extensions=[".php"],
        patterns=[
            re.compile(r"^\s*use\s+([^;]+);", re.MULTILINE),
            re.compile(r"^\s*require(?:_once)?\s*\(?\s*['\"]([^'\"]+)['\"]", re.MULTILINE),
            re.compile(r"^\s*include(?:_once)?\s*\(?\s*['\"]([^'\"]+)['\"]", re.MULTILINE),
        ],
    )
)

# Java / C#
registry.register(
    GenericParser(
        language="java",
        extensions=[".java"],
        patterns=[re.compile(r"^\s*import\s+([^;]+);", re.MULTILINE)],
    )
)

registry.register(
    GenericParser(
        language="csharp",
        extensions=[".cs"],
        patterns=[re.compile(r"^\s*using\s+([^;]+);", re.MULTILINE)],
    )
)

# C / C++
cpp_patterns = [
    re.compile(r'^\s*#include\s+["<]([^">]+)[">]', re.MULTILINE),
]
registry.register(
    GenericParser(
        language="c",
        extensions=[".c", ".h"],
        patterns=cpp_patterns,
    )
)
registry.register(
    GenericParser(
        language="cpp",
        extensions=[".cpp", ".hpp", ".cc", ".cxx"],
        patterns=cpp_patterns,
    )
)
