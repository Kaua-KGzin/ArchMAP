from __future__ import annotations

from typing import Any, Callable, Protocol, TypedDict


class Dependency(TypedDict):
    id: str
    label: str
    type: str


class ParserPlugin(Protocol):
    extensions: list[str]
    language: str

    def parse(self, source_code: str) -> list[Any]:
        ...

    def resolve(
        self,
        import_entries: list[Any],
        file_id: str,
        file_ids: set[str],
    ) -> list[Dependency]:
        ...


class LanguageRegistry:
    def __init__(self):
        self._parsers: dict[str, ParserPlugin] = {}
        self._ext_map: dict[str, str] = {}

    def register(self, parser: ParserPlugin):
        self._parsers[parser.language] = parser
        for ext in parser.extensions:
            self._ext_map[ext] = parser.language

    def get_parser(self, language: str) -> ParserPlugin | None:
        return self._parsers.get(language)

    def get_language_by_ext(self, ext: str) -> str | None:
        return self._ext_map.get(ext)

    def get_all_languages(self) -> list[str]:
        return list(self._parsers.keys())

    def get_all_extensions(self) -> set[str]:
        return set(self._ext_map.keys())


registry = LanguageRegistry()
