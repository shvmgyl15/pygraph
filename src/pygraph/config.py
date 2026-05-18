from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


def load_pyproject_config(root: str) -> dict[str, Any]:
    pyproject = Path(root) / "pyproject.toml"
    if not pyproject.exists():
        return {}
    try:
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError):
        return {}
    tool_pygraph: dict[str, Any] = data.get("tool", {}).get("pygraph", {})
    return tool_pygraph


def get_plugins(root: str) -> list[str]:
    config = load_pyproject_config(root)
    raw = config.get("plugins", [])
    if isinstance(raw, list):
        return [str(p) for p in raw]
    return []
