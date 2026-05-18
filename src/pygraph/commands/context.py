from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery, name: str, show_source: bool = False) -> None:
    ctx = query.get_context(name, include_source=show_source)
    symbol = ctx["symbol"]
    if not symbol:
        print(f"Symbol '{name}' not found")
        return

    print(f"=== {symbol.name} ({symbol.kind}) ===")
    print(f"  File: {symbol.file}:{symbol.line}")
    if symbol.receiver:
        print(f"  Receiver: {symbol.receiver}")
    if symbol.complexity is not None:
        print(f"  Complexity: {symbol.complexity}")
    if symbol.doc:
        doc = symbol.doc.strip().split("\n")[0]
        print(f"  Doc: {doc}")

    if ctx["callers"]:
        print(f"\nCallers ({len(ctx['callers'])}):")
        for c in ctx["callers"]:
            print(f"  {c['caller']}  {c['file']}:{c['line']}")

    if ctx["callees"]:
        print(f"\nCallees ({len(ctx['callees'])}):")
        for c in ctx["callees"]:
            caller = f"{c.get('callee', '?')}"
            print(f"  {caller}  {c['file']}:{c['line']}")

    if ctx["test_edges"]:
        print(f"\nTests ({len(ctx['test_edges'])}):")
        for t in ctx["test_edges"]:
            print(f"  {t['test_func']}  {t['file']}:{t['line']}")

    if show_source and ctx["source"]:
        print(f"\n--- {symbol.file} ---")
        print(ctx["source"])
