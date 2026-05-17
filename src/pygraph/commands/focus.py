from __future__ import annotations

import json

from pygraph.query import GraphQuery


def run(query: GraphQuery, name: str) -> None:
    symbol = query.get_symbol(name)
    if not symbol:
        print(f"Symbol '{name}' not found")
        return

    callers = [
        {"caller": cs.name, "file": ce.file, "line": ce.line}
        for cs, ce in query.get_callers(name)
    ]
    callees = [
        {
            "callee": cs.name if cs else ce.callee_raw,
            "file": ce.file,
            "line": ce.line,
        }
        for cs, ce in query.get_callees(name)
    ]

    result = {
        "name": symbol.name,
        "kind": symbol.kind,
        "file": symbol.file,
        "line": symbol.line,
        "end_line": symbol.end_line,
        "exported": symbol.is_exported,
        "callers": callers,
        "callees": callees,
    }
    print(json.dumps(result, indent=2))
