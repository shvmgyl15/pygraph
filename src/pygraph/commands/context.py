from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery, name: str) -> None:
    ctx = query.get_context(name)
    symbol = ctx["symbol"]
    if not symbol:
        print(f"Symbol '{name}' not found")
        return

    print(f"=== {symbol.name} ({symbol.kind}) ===")
    print(f"File: {symbol.file}:{symbol.line}")

    if ctx["callers"]:
        print("\nCallers:")
        for c in ctx["callers"]:
            print(f"  {c['caller']}  {c['file']}:{c['line']}")

    if ctx["callees"]:
        print("\nCallees:")
        for c in ctx["callees"]:
            print(f"  {c['callee']}  {c['file']}:{c['line']}")

    if ctx["test_edges"]:
        print("\nTests:")
        for t in ctx["test_edges"]:
            print(f"  {t['test_func']}  {t['file']}:{t['line']}")

    if ctx["source"]:
        print(f"\n--- {symbol.file} ---")
        print(ctx["source"])
