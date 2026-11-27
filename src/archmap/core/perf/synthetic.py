"""Deterministic synthetic projects for benchmarking and calibration."""
from __future__ import annotations

import random
from pathlib import Path
from typing import Literal

Language = Literal["python", "typescript"]
Shape = Literal["layered", "hub", "cycle"]

_LAYERS = 10
_HUBS = 20
_CYCLE_FANOUT = 5


def _module_name(idx: int) -> str:
    return f"module_{idx:05d}"


def _dependencies(n_files: int, shape: str, seed: int) -> list[list[int]]:
    """Indices each file imports, per shape."""
    rng = random.Random(seed)
    deps: list[list[int]] = [[] for _ in range(n_files)]
    if shape == "cycle":
        for i in range(n_files):
            targets = {(i + j) % n_files for j in range(1, _CYCLE_FANOUT + 1)}
            deps[i] = sorted(targets - {i})
    elif shape == "layered":
        layer_size = max(1, -(-n_files // _LAYERS))
        for i in range(n_files):
            lower = (i // layer_size) * layer_size
            if lower == 0:
                continue
            k = min(rng.randint(3, 5), lower)
            deps[i] = sorted(rng.sample(range(lower), k))
    elif shape == "hub":
        hubs = min(_HUBS, n_files)
        for i in range(hubs, n_files):
            targets = set(rng.sample(range(hubs), min(3, hubs)))
            if i - 1 >= hubs:
                targets.add(i - 1)
            deps[i] = sorted(targets)
    else:
        raise ValueError(f"unknown shape: {shape}")
    return deps


def generate_sources(
    n_files: int,
    *,
    language: Language = "python",
    shape: Shape = "layered",
    seed: int = 0,
) -> dict[str, str]:
    """Relative POSIX path -> file content for a synthetic project."""
    if language not in ("python", "typescript"):
        raise ValueError(f"unknown language: {language}")
    ext = "py" if language == "python" else "ts"
    deps = _dependencies(n_files, shape, seed)
    sources: dict[str, str] = {}
    for idx in range(n_files):
        if language == "python":
            lines = [f"import {_module_name(t)}" for t in deps[idx]]
            tail = f"def func_{idx}(): pass\n"
        else:
            lines = [
                f'import {{ func_{t} }} from "./{_module_name(t)}";' for t in deps[idx]
            ]
            tail = f"export function func_{idx}(): void {{}}\n"
        header = "\n".join(lines) + "\n\n" if lines else ""
        sources[f"{_module_name(idx)}.{ext}"] = header + tail
    return sources


def generate_project(
    root: Path,
    n_files: int,
    *,
    language: Language = "python",
    shape: Shape = "layered",
    seed: int = 0,
) -> None:
    """Write the ``generate_sources`` mapping under ``root``."""
    root.mkdir(parents=True, exist_ok=True)
    sources = generate_sources(n_files, language=language, shape=shape, seed=seed)
    for rel, content in sources.items():
        (root / rel).write_text(content, encoding="utf-8")
