from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery, name: str) -> None:
    edges = query.get_impact(name)
    if not edges:
        print(f"No downstream impact from '{name}'")
        return
    for e in edges:
        print(f"{e['caller']} -> {e['callee']}  {e['file']}:{e['line']}")
