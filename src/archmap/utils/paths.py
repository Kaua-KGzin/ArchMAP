"""Path confinement shared by every surface that reads files on a caller's behalf."""

from __future__ import annotations

from pathlib import Path


def resolve_inside(root: str | Path, user_path: str) -> Path:
    """Resolve ``user_path`` against ``root`` and refuse anything outside it.

    The MCP server and the web UI read files named by a model or a browser,
    and a prompt-injected model could ask for ``~/.ssh/id_rsa``. Symlinks are
    resolved first, so a link inside the project can't point outside it.
    Raises ``ValueError`` for paths outside ``root`` or that don't exist.
    """
    base = Path(root).resolve()
    candidate = Path(user_path).expanduser() if user_path else Path(".")
    resolved = (candidate if candidate.is_absolute() else base / candidate).resolve()
    if resolved != base and base not in resolved.parents:
        raise ValueError(
            f"'{user_path}' is outside the project root {base}; open a project "
            "that contains it"
        )
    if not resolved.exists():
        raise ValueError(f"'{user_path}' does not exist")
    return resolved
