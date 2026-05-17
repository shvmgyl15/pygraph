from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery) -> None:
    deps = query.get_deps()
    if not deps:
        print("No dependencies found")
        return

    print(f"{'Module':<30}  {'Version'}")
    print(f"{'-'*30}  {'-'*20}")
    for d in deps:
        print(f"{d['module']:<30}  {d['version']}")
