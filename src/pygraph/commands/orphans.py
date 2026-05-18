from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery, include_public: bool = False) -> None:
    orphans = query.get_orphans(include_public=include_public)
    if not orphans:
        print("No orphan symbols found")
        return
    for s in orphans:
        marker = "+" if s.is_exported else " "
        print(f"{marker} {s.kind:12s} {s.name:30s} {s.file}:{s.line}")
    if include_public:
        public_count = sum(1 for s in orphans if s.is_exported)
        if public_count:
            print(f"\n({public_count} public, {len(orphans) - public_count} private)")
