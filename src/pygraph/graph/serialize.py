from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pygraph.graph.types import Edge, FileNode, Graph, PackageNode, Position, SymbolNode


def graph_to_dict(graph: Graph) -> dict[str, Any]:
    packages = {
        k: {"name": v.name, "path": v.path, "files": v.files}
        for k, v in graph.packages.items()
    }
    files = {
        k: {"path": v.path, "package": v.package, "symbols": v.symbols}
        for k, v in graph.files.items()
    }
    symbols = {
        k: {
            "name": v.name,
            "kind": v.kind,
            "file": v.file,
            "pos": {"line": v.pos.line, "column": v.pos.column},
            "end_pos": {"line": v.end_pos.line, "column": v.end_pos.column}
            if v.end_pos
            else None,
            "docstring": v.docstring,
            "is_exported": v.is_exported,
            "decorators": v.decorators,
            "extra": v.extra,
        }
        for k, v in graph.symbols.items()
    }
    edges = [
        {"source": e.source, "target": e.target, "kind": e.kind}
        for e in graph.edges
    ]
    return {
        "schema_version": graph.schema_version,
        "project_root": graph.project_root,
        "packages": packages,
        "files": files,
        "symbols": symbols,
        "edges": edges,
    }


def dict_to_graph(data: dict[str, Any]) -> Graph:
    packages: dict[str, PackageNode] = {}
    for k, v in data.get("packages", {}).items():
        packages[k] = PackageNode(name=v["name"], path=v["path"], files=v["files"])

    files: dict[str, FileNode] = {}
    for k, v in data.get("files", {}).items():
        files[k] = FileNode(path=v["path"], package=v["package"], symbols=v["symbols"])

    symbols: dict[str, SymbolNode] = {}
    for k, v in data.get("symbols", {}).items():
        pos = Position(**v["pos"])
        end_pos = Position(**v["end_pos"]) if v.get("end_pos") else None
        symbols[k] = SymbolNode(
            name=v["name"],
            kind=v["kind"],
            file=v["file"],
            pos=pos,
            end_pos=end_pos,
            docstring=v.get("docstring"),
            is_exported=v.get("is_exported", True),
            decorators=v.get("decorators", []),
            extra=v.get("extra", {}),
        )

    edges = [Edge(**e) for e in data.get("edges", [])]

    return Graph(
        schema_version=data.get("schema_version", "1"),
        project_root=data.get("project_root", ""),
        packages=packages,
        files=files,
        symbols=symbols,
        edges=edges,
    )


def write_graph(graph: Graph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(graph_to_dict(graph), f, indent=2)


def read_graph(path: Path) -> Graph:
    with open(path) as f:
        return dict_to_graph(json.load(f))
