from __future__ import annotations

from pathlib import Path


def test_packaged_web_ui_assets_match_dev_copy() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    for asset_name in ["app.js", "index.html", "styles.css"]:
        packaged = repo_root / "src" / "archmap" / "web-ui" / "static" / asset_name
        dev_copy = repo_root / "web-ui" / "static" / asset_name
        assert packaged.read_text(encoding="utf-8") == dev_copy.read_text(encoding="utf-8")
