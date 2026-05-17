from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery, days: int = 30) -> None:
    results = query.get_stale(days)
    if not results:
        print(f"No stale files (modified within last {days} days)")
        return

    print(f"Stale files (not modified in >{days} days):\n")
    print(f"{'Days':>5}  {'File':<50}  {'Symbols'}")
    print(f"{'-'*5}  {'-'*50}  {'-'*20}")
    for r in results:
        sym_names = ", ".join(s["name"] for s in r["symbols"][:5])
        if len(r["symbols"]) > 5:
            sym_names += f" ... (+{len(r['symbols']) - 5} more)"
        print(f"{r['days_since_modification']:>5}  {r['file']:<50}  {sym_names}")
