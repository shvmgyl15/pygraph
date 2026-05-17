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

    print("# Code Review Report\n")
    print(f"**Scope:** {len(summary['files_changed'])} files across "
          f"{len(summary['modules_changed'])} modules\n")
    print("| Metric | Value |")
    print("|--------|-------|")
    print(f"| Symbols added | {summary['symbols_added']} |")
    print(f"| Symbols removed | {summary['symbols_removed']} |")
    print(f"| Symbols changed | {summary['symbols_changed']} |")
    print(f"| Files touched | {len(summary['files_changed'])} |")
    print(f"| Risk score | {summary['total_risk_score']} |\n")

    if changes.get("added_symbols"):
        print("## Added Symbols\n")
        for s in changes["added_symbols"]:
            sig = s.get("signature") or ""
            print(f"- `{s['name']}` ({s['kind']}) — `{s['file']}:{s['line']}`")
            if sig:
                print(f"  ```python\n  {sig}\n  ```")

    if changes.get("removed_symbols"):
        print("\n## Removed Symbols\n")
        for s in changes["removed_symbols"]:
            print(f"- `{s['name']}` ({s['kind']}) — was `{s['file']}:{s['line']}`")

    if changes.get("changed_symbols"):
        print("\n## Changed Symbols\n")
        for s in changes["changed_symbols"]:
            print(f"- `{s['name']}`")
            if s.get("old_signature") != s.get("new_signature"):
                print(f"  - Signature: `{s['old_signature']}` → `{s['new_signature']}`")
            if s.get("old_complexity") != s.get("new_complexity"):
                print(f"  - Complexity: {s['old_complexity']} → {s['new_complexity']}")
            if s.get("old_exported") != s.get("new_exported"):
                print(f"  - Exported: {s['old_exported']} → {s['new_exported']}")

    if tests:
        print("\n## Related Tests\n")
        for t in tests:
            print(f"- `{t['test_func']}` tests `{t['target']}` (`{t['file']}:{t['line']}`)")

    if risks:
        print("\n## Risk Assessment\n")
        print("| Symbol | Score | Complexity | Coupling |")
        print("|--------|-------|------------|----------|")
        for r in risks[:10]:
            print(f"| {r['name']} | {r['score']} | {r['complexity']} | "
                  f"{r['coupling']} |")
