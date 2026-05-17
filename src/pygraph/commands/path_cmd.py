from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery, from_name: str, to_name: str) -> None:
    path = query.get_path(from_name, to_name)
    if path is None:
        print(f"No path from '{from_name}' to '{to_name}'")
        return
    for step in path:
        file_line = f"  {step['file']}:{step['line']}" if "file" in step else ""
        print(f"{step['from']} -> {step['to']}{file_line}")
