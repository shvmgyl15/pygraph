from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery, name: str) -> None:
    callers = query.get_callers(name)
    if not callers:
        print(f"No callers found for '{name}'")
        return
    for caller_sym, edge in callers:
        print(f"{caller_sym.name}  {edge.file}:{edge.line}  ({edge.callee_raw})")
