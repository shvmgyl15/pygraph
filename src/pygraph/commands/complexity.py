from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery, name: str | None = None) -> None:
    results = query.get_complexity(name)
    if not results:
        if name:
            print(f"Symbol '{name}' not found")
        else:
            print("No symbols with complexity data found")
        return

    if name:
        r = results[0]
        print(f"Complexity: {r['complexity']}")
        print(f"Symbol:     {r['name']}")
        print(f"Kind:       {r['kind']}")
        print(f"File:       {r['file']}")
        print(f"Line:       {r['line']}")
        return

    print(f"{'Complexity':>10}  {'Name':<30}  {'Kind':<10}  {'File'}")
    print(f"{'-'*10}  {'-'*30}  {'-'*10}  {'-'*40}")
    for r in results:
        print(f"{r['complexity']:>10}  {r['name']:<30}  {r['kind']:<10}  {r['file']}")
