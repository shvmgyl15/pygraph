from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Position:
    line: int
    column: int


@dataclass
class SymbolNode:
    name: str
    kind: str  # "function", "class", "method", "variable", "route", etc.
    file: str
    pos: Position
    end_pos: Position | None = None
    docstring: str | None = None
    is_exported: bool = True
    decorators: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    source: str
    target: str
    kind: str  # "calls", "imports", "decorates", "inherits", "implements", "route"


@dataclass
class FileNode:
    path: str
    package: str
    symbols: list[str] = field(default_factory=list)


@dataclass
class PackageNode:
    name: str
    path: str
    files: list[str] = field(default_factory=list)


@dataclass
class Graph:
    schema_version: str = "1"
    project_root: str = ""
    packages: dict[str, PackageNode] = field(default_factory=dict)
    files: dict[str, FileNode] = field(default_factory=dict)
    symbols: dict[str, SymbolNode] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
