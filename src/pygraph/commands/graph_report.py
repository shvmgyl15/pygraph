from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery) -> None:
    report = query.get_graph_report()

    s = report["summary"]

    print("# Graph Report\n")
    print(f"Generated from `.pygraph/graph.json`\n")

    print("## Overview\n")
    print(f"| Metric | Value |")
    print(f"|--------|-------|")
    print(f"| Symbols | {s['total_symbols']} |")
    print(f"| Exported | {s['exported']} |")
    print(f"| Files | {s['files']} |")
    print(f"| Call edges | {s['calls']} |")
    print(f"| Routes | {s['routes']} |")
    print(f"| Dependencies | {s['dependencies']} |")
    print(f"| Test edges | {s['tests']} |\n")

    kinds = report["symbols_by_kind"]
    if kinds:
        print("## Symbols by Kind\n")
        print(f"| Kind | Count |")
        print(f"|------|-------|")
        for kind in sorted(kinds):
            print(f"| {kind} | {kinds[kind]} |")
        print()

    if report["hotspots"]:
        print("## Hotspots (Top 10)\n")
        print(f"| Score | Complexity | Coupling | Name | File |")
        print(f"|-------|------------|----------|------|------|")
        for h in report["hotspots"]:
            print(f"| {h['score']} | {h['complexity']} | "
                  f"{h['coupling']} | {h['name']} | {h['file']} |")
        print()

    if report["coupling"]:
        print("## Coupling (Top 10)\n")
        print(f"| Name | Ca | Ce | Instability |")
        print(f"|------|----|----|-------------|")
        for c in report["coupling"]:
            print(f"| {c['name']} | {c['ca']} | {c['ce']} | "
                  f"{c['instability']} |")
        print()
