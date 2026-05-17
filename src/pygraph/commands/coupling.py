from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery, name: str | None = None) -> None:
    results = query.get_coupling(name)
    if not results:
        if name:
            print(f"Symbol '{name}' not found")
        else:
            print("No coupling data found")
        return

    if name:
        r = results[0]
        print(f"Symbol:      {r['name']}")
        print(f"Ca (callers):   {r['ca']}")
        print(f"Ce (callees):   {r['ce']}")
        print(f"Instability: {r['instability']}")
        return

    print(f"{'Name':<30}  {'Ca':>5}  {'Ce':>5}  {'Instability':>12}")
    print(f"{'-'*30}  {'-'*5}  {'-'*5}  {'-'*12}")
    for r in results:
        print(f"{r['name']:<30}  {r['ca']:>5}  {r['ce']:>5}  {r['instability']:>12}")
