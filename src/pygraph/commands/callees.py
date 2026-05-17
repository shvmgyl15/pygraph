from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery, name: str) -> None:
    callees = query.get_callees(name)
    if not callees:
        print(f"No callees found for '{name}'")
        return
    for callee_sym, edge in callees:
        callee_name = callee_sym.name if callee_sym else edge.callee_raw
        print(f"{callee_name}  {edge.file}:{edge.line}  ({edge.callee_raw})")
