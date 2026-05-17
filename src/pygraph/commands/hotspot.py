from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery, top_n: int = 10) -> None:
    results = query.get_hotspots(top_n)
    if not results:
        print("No hotspot data found")
        return

    print(f"{'Score':>8}  {'Complexity':>10}  {'Coupling':>8}  {'Name':<30}  {'File'}")
    print(f"{'-'*8}  {'-'*10}  {'-'*8}  {'-'*30}  {'-'*40}")
    for r in results:
        print(
            f"{r['score']:>8}  {r['complexity']:>10}  {r['coupling']:>8}  "
            f"{r['name']:<30}  {r['file']}"
        )
