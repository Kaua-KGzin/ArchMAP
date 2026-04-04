from __future__ import annotations

from archmap.utils.file_utils import normalize_file_id

DEFAULT_LAYER_ORDER = {
    "cli": 5,
    "web-ui": 5,
    "api": 5,
    "interface": 5,
    "app": 4,
    "application": 4,
    "core": 3,
    "domain": 3,
    "exporters": 2,
    "adapters": 2,
    "infra": 2,
    "utils": 1,
    "shared": 1,
}


def detect_layer(file_id: str, layer_order: dict[str, int]) -> str | None:
    parts = [part for part in normalize_file_id(file_id).split("/") if part and part != "."]
    for part in parts:
        normalized = part.casefold()
        if normalized in layer_order:
            return normalized
    return None


def build_layer_order(custom_layer_order: dict[str, int] | None) -> dict[str, int]:
    merged = dict(DEFAULT_LAYER_ORDER)
    if not custom_layer_order:
        return merged

    for key, value in custom_layer_order.items():
        merged[str(key).strip().casefold()] = int(value)

    return merged
