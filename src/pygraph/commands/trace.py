from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery, message: str) -> None:
    results = query.get_errorflow(message)
    if not results:
        plain = query.get_trace(message)
        if plain:
            for r in plain:
                print(f"Error: {r['message']}  {r['function']}  {r['file']}:{r['line']}")
            return
        print(f"No errors matching '{message}'")
        return

    for item in results:
        err = item["error"]
        print(f"Error: {err.message}  {err.function_name}  {err.file}:{err.line}")
        for step in item["trace"]:
            print(f"  {step['from']} -> {step['to']}  {step['file']}:{step['line']}")
