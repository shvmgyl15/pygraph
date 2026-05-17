from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery, pattern: str) -> None:
    symbols = query.find_symbols(pattern)
    if not symbols:
        print(f"No symbols matching '{pattern}'")
        return
    for s in symbols:
        exported = "+" if s.is_exported else " "
        print(f"{exported} {s.kind:12s} {s.name:30s} {s.file}")
