from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery) -> None:
    orphans = query.get_orphans()
    if not orphans:
        print("No orphan symbols found")
        return
    for s in orphans:
        print(f"{s.kind:12s} {s.name:30s} {s.file}:{s.line}")
