from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery) -> None:
    report = query.get_graph_report()

    s = report["summary"]

    print("# Graph Report\n")
    print("Generated from `.pygraph/graph.json`\n")

    print("## Overview\n")
    print("| Metric | Value |")
    print("|--------|-------|")
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
        print("| Kind | Count |")
        print("|------|-------|")
        for kind in sorted(kinds):
            print(f"| {kind} | {kinds[kind]} |")
        print()

    if report["hotspots"]:
        print("## Hotspots (Top 10)\n")
        print("| Score | Complexity | Coupling | Name | File |")
        print("|-------|------------|----------|------|------|")
        for h in report["hotspots"]:
            print(f"| {h['score']} | {h['complexity']} | "
                  f"{h['coupling']} | {h['name']} | {h['file']} |")
        print()

    if report["coupling"]:
        print("## Coupling (Top 10)\n")
        print("| Name | Ca | Ce | Instability |")
        print("|------|----|----|-------------|")
        for c in report["coupling"]:
            print(f"| {c['name']} | {c['ca']} | {c['ce']} | "
                  f"{c['instability']} |")
        print()
