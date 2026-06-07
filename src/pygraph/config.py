from __future__ import annotations

import json
import logging
import os
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


def load_event_config(root: str) -> list[dict[str, Any]]:
    raw = os.environ.get("CODEGRAPH_EVENT_CONFIG")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError as e:
            logging.warning("CODEGRAPH_EVENT_CONFIG present but invalid: %s", e)
    config = load_pyproject_config(root)
    raw2 = config.get("event_boundaries", [])
    return raw2 if isinstance(raw2, list) else []
