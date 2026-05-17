from __future__ import annotations

import json
from pathlib import Path


class BoundaryLayer:
    def __init__(self, name: str, pattern: str, allowed: list[str]) -> None:
        self.name = name
        self.pattern = pattern
        self.allowed: set[str] = set(allowed)

    def matches(self, file_path: str) -> bool:
        return self.pattern in file_path


class BoundaryConfig:
    def __init__(self, layers: list[BoundaryLayer]) -> None:
        self.layers = layers

    def layer_for(self, file_path: str) -> str | None:
        for layer in self.layers:
            if layer.matches(file_path):
                return layer.name
        return None

    def is_allowed(self, caller_layer: str, callee_layer: str) -> bool:
        for layer in self.layers:
            if layer.name == caller_layer:
                return callee_layer in layer.allowed
        return True


def load_boundary_config(config_path: str) -> BoundaryConfig:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Boundary config not found: {config_path}")
    data = json.loads(path.read_text())
    layers = [BoundaryLayer(**item) for item in data["layers"]]
    return BoundaryConfig(layers)
