from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery) -> None:
    symbols = query.get_public()
    if not symbols:
        print("No public symbols found")
        return
    for s in symbols:
        print(f"{s.kind:12s} {s.name:30s} {s.file}:{s.line}")
