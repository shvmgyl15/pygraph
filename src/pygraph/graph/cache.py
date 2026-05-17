from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CACHE_VERSION = 1


class BuildCache:
    def __init__(self, files: dict[str, dict[str, Any]] | None = None) -> None:
        self.files: dict[str, dict[str, Any]] = files or {}

    def is_changed(self, file_path: str, mtime: float, size: int) -> bool:
        cached = self.files.get(file_path)
        if cached is None:
            return True
        return bool(cached["mtime"] != mtime or cached["size"] != size)

    def set(self, file_path: str, mtime: float, size: int) -> None:
        self.files[file_path] = {"mtime": mtime, "size": size}

    def remove(self, file_path: str) -> None:
        self.files.pop(file_path, None)

    def to_dict(self) -> dict[str, Any]:
        return {"version": CACHE_VERSION, "files": self.files}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BuildCache:
        return cls(data.get("files", {}))

    @classmethod
    def load(cls, path: Path) -> BuildCache:
        try:
            data = json.loads(path.read_text())
            return cls.from_dict(data)
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            return cls({})

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2))
