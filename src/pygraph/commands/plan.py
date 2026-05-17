from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery, since: str = "HEAD") -> None:
    plan = query.get_plan(since)
    if "error" in plan:
        print(plan["error"][0]["message"])
        return

    summary = plan["summary"]
    changes = plan["changes"]
    tests = plan["affected_tests"]
    risks = plan["risk_items"]

    print("=== Change Plan ===\n")

    print(f"Symbols added:     {summary['symbols_added']}")
    print(f"Symbols removed:   {summary['symbols_removed']}")
    print(f"Symbols changed:   {summary['symbols_changed']}")
    print(f"Files affected:    {len(summary['files_changed'])}")
    print(f"Risk score:        {summary['total_risk_score']}")

    if summary["files_changed"]:
        print("\nFiles:\n  " + "\n  ".join(summary["files_changed"]))

    if changes.get("added_symbols"):
        print(f"\nAdded symbols ({len(changes['added_symbols'])}):")
        for s in changes["added_symbols"]:
            print(f"  + {s['name']} ({s['kind']}, {s['file']}:{s['line']})")

    if changes.get("removed_symbols"):
        print(f"\nRemoved symbols ({len(changes['removed_symbols'])}):")
        for s in changes["removed_symbols"]:
            print(f"  - {s['name']} ({s['kind']}, was {s['file']}:{s['line']})")

    if changes.get("changed_symbols"):
        print(f"\nChanged symbols ({len(changes['changed_symbols'])}):")
        for s in changes["changed_symbols"]:
            print(f"  ~ {s['name']} ({s['new_file']})")

    if tests:
        print(f"\nAffected tests ({len(tests)}):")
        for t in tests:
            print(f"  {t['test_func']} (tests {t['target']})")

    if risks:
        print("\nTop risk items:")
        for r in risks[:5]:
            print(f"  {r['name']:30s}  score={r['score']}  "
                  f"complexity={r['complexity']}  coupling={r['coupling']}")
