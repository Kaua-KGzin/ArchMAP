"""Static consistency checks for the web UI assets (no browser needed).

They catch the regressions a browser test would only find by clicking
through every view: a missing translation in one of the six languages, an
i18n key used in the HTML that no table defines, or JavaScript looking up an
element id that no longer exists.
"""

from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "src" / "archmap" / "web-ui" / "static"
LANGS = ("en", "pt", "es", "fr", "de", "zh")


def _blocks(source: str, start_marker: str) -> dict[str, set[str]]:
    """Map language -> keys for a `{ en: {...}, pt: {...} }` translation table."""
    table = source[source.index(start_marker):]
    keys: dict[str, set[str]] = {}
    for lang in LANGS:
        match = re.search(rf"\n  {lang}: \{{\n(.*?)\n  \}},", table, re.DOTALL)
        assert match, f"language block '{lang}' not found"
        keys[lang] = set(re.findall(r"([A-Za-z_][A-Za-z0-9_]*):\"", match.group(1)))
    return keys


def test_toolkit_translations_cover_every_language() -> None:
    source = (STATIC / "toolkit.js").read_text(encoding="utf-8")
    keys = _blocks(source, "export const TOOLKIT_TRANSLATIONS")
    for lang in LANGS[1:]:
        assert keys[lang] == keys["en"], (
            f"{lang}: missing {sorted(keys['en'] - keys[lang])}, "
            f"extra {sorted(keys[lang] - keys['en'])}"
        )


def test_toolkit_static_keys_are_defined() -> None:
    source = (STATIC / "toolkit.js").read_text(encoding="utf-8")
    english = _blocks(source, "export const TOOLKIT_TRANSLATIONS")["en"]
    used = set(re.findall(r"\bt\(\"([A-Za-z_][A-Za-z0-9_]*)\"", source))
    assert used <= english, f"undefined toolkit keys: {sorted(used - english)}"
    # Dynamic keys built from severities, domains and confidence levels.
    for severity in ("critical", "high", "medium", "low", "info"):
        assert f"sev_{severity}" in english
    for domain in ("code", "quality", "security", "agent", "binary", "network"):
        assert f"dom_{domain}" in english
    for level in ("high", "medium", "low"):
        assert f"qualLevel_{level}" in english


def test_html_i18n_keys_exist() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    toolkit = (STATIC / "toolkit.js").read_text(encoding="utf-8")
    english = _blocks(toolkit, "export const TOOLKIT_TRANSLATIONS")["en"]
    app_en = re.search(r"const _TRANSLATIONS = \{\n  en: \{\n(.*?)\n  \},", app, re.DOTALL)
    assert app_en
    english |= set(re.findall(r"([A-Za-z_][A-Za-z0-9_]*):[\"']", app_en.group(1)))
    used = set(re.findall(r'data-i18n(?:-title|-placeholder|-html)?="([^"]+)"', html))
    assert used <= english, f"HTML uses undefined i18n keys: {sorted(used - english)}"


def test_toolkit_element_ids_exist() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    toolkit = (STATIC / "toolkit.js").read_text(encoding="utf-8")
    available = set(re.findall(r'id="([^"$]+)"', html)) | set(re.findall(r'id="([^"$]+)"', toolkit))
    referenced = set(re.findall(r'getElementById\("([^"]+)"\)', toolkit))
    assert referenced <= available, f"missing element ids: {sorted(referenced - available)}"


def test_app_wires_every_toolkit_view() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert 'import * as toolkit from "./toolkit.js";' in app
    for view, button in (
        ("lpFindings", "navBtnFindings"),
        ("lpContext", "navBtnContext"),
        ("lpInspect", "navBtnInspect"),
        ("lpAudit", "navBtnAudit"),
    ):
        assert f'id="{view}"' in html and f'id="{button}"' in html
        assert f'"{view}"' in app and f'"{button}"' in app
    assert 'id="inspectorView"' in html and 'id="canvasTabInspector"' in html


def test_arch_line_mark_is_shipped_and_translated() -> None:
    # The Arch line signature in the nav rail: asset present, tooltip in all six languages.
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert (STATIC / "arch-mark.svg").read_text(encoding="utf-8").lstrip().startswith("<svg")
    assert 'src="/arch-mark.svg"' in html and 'data-i18n="navArchLine"' in html
    table = app[app.index("const _TRANSLATIONS = {"):]
    for lang in LANGS:
        block = re.search(rf"\n  {lang}: \{{\n(.*?)\n  \}},", table, re.DOTALL)
        assert block and 'navArchLine:"' in block.group(1), f"navArchLine missing in {lang}"
