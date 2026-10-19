from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node not installed")
@pytest.mark.parametrize("script", ["web-ui/server.js", "web-ui/dev-server.js"])
def test_node_dev_server_parses(script: str) -> None:
    # server.js shipped with half of startWebUi pasted twice ("Unexpected token
    # 'export'"), so `npm run serve:web` died before serving anything.
    result = subprocess.run(
        [str(NODE), "--check", str(ROOT / script)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_dev_server_uses_the_shipped_static_dir() -> None:
    # The UI lives only in src/archmap/web-ui/static; web-ui/static never existed.
    dev_server = (ROOT / "web-ui" / "dev-server.js").read_text(encoding="utf-8")
    assert '"web-ui", "static"' not in dev_server
    assert (ROOT / "src" / "archmap" / "web-ui" / "static" / "index.html").is_file()
