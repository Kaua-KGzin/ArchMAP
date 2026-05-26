"""Temporal coupling analysis via git log.

Detects pairs of files that tend to change together in commits —
a strong signal of hidden coupling not visible in static imports.
"""

from __future__ import annotations

import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any


def analyze_temporal_coupling(
    project_path: str | Path,
    min_commits: int = 2,
    top: int = 20,
) -> dict:
    """Return co-change pairs sorted by co-change frequency.

    Args:
        project_path: Root directory of the git repository.
        min_commits: Minimum co-change count for a pair to be included.
        top: Maximum number of pairs to return.

    Returns:
        Dict with ``pairs`` list and ``totalCommitsScanned``.
    """
    root = Path(project_path).resolve()

    try:
        raw = subprocess.check_output(
            ["git", "log", "--name-only", "--format=%H", "--diff-filter=ACDMR"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return {"error": str(exc), "pairs": [], "totalCommitsScanned": 0}

    commits = _parse_git_log(raw)
    co_changes: dict[tuple[str, str], int] = defaultdict(int)
    file_commits: dict[str, int] = defaultdict(int)

    for files in commits:
        unique = sorted(set(files))
        for f in unique:
            file_commits[f] += 1
        for i, a in enumerate(unique):
            for b in unique[i + 1 :]:
                co_changes[(a, b)] += 1

    pairs: list[dict[str, Any]] = [
        {
            "fileA": a,
            "fileB": b,
            "coChanges": count,
            "commitsA": file_commits[a],
            "commitsB": file_commits[b],
            "couplingStrength": round(count / max(min(file_commits[a], file_commits[b]), 1), 3),
        }
        for (a, b), count in co_changes.items()
        if count >= min_commits
    ]
    pairs.sort(key=lambda x: (-x["coChanges"], -x["couplingStrength"]))

    return {
        "pairs": pairs[:top],
        "totalPairs": len(pairs),
        "totalCommitsScanned": len(commits),
        "minCommits": min_commits,
    }


def _parse_git_log(raw: str) -> list[list[str]]:
    """Split raw git log output into per-commit file lists."""
    commits: list[list[str]] = []
    current: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            if current:
                commits.append(current)
                current = []
        elif len(line) == 40 and all(c in "0123456789abcdef" for c in line):
            if current:
                commits.append(current)
            current = []
        else:
            current.append(line)
    if current:
        commits.append(current)
    return [c for c in commits if len(c) > 1]
