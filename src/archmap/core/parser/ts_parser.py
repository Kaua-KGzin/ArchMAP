from __future__ import annotations

from archmap.core.parser.js_parser import JSParser


class TSParser(JSParser):
    language = "typescript"
    extensions = [".ts", ".tsx", ".mts", ".cts"]


__all__ = ["TSParser"]
