from __future__ import annotations

from .js_parser import parse_js_imports


def parse_ts_imports(source_code: str) -> list[str]:
    return parse_js_imports(source_code)
