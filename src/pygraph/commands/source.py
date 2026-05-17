from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery, file_path: str) -> None:
    source = query.get_source(file_path)
    if source is None:
        print(f"File not found: {file_path}")
        return
    print(source)
