from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery, since: str = "HEAD") -> None:
    result = query.get_changes(since)
    if "error" in result:
        print(result["error"][0]["message"])
        return

    added = result["added_symbols"]
    removed = result["removed_symbols"]
    changed = result["changed_symbols"]
    added_calls = result["added_calls"]
    removed_calls = result["removed_calls"]

    if not any([added, removed, changed, added_calls, removed_calls]):
        print("No changes detected")
        return

    if added:
        print(f"Added symbols ({len(added)}):")
        for s in added:
            print(f"  + {s['kind']:12s} {s['name']}  ({s['file']}:{s['line']})")

    if removed:
        print(f"\nRemoved symbols ({len(removed)}):")
        for s in removed:
            print(f"  - {s['kind']:12s} {s['name']}  (was {s['file']}:{s['line']})")

    if changed:
        print(f"\nChanged symbols ({len(changed)}):")
        for s in changed:
            print(f"  ~ {s['name']}")
            if s["old_signature"] != s["new_signature"]:
                print(f"      signature: {s['old_signature']} -> {s['new_signature']}")
            if s["old_complexity"] != s["new_complexity"]:
                print(f"      complexity: {s['old_complexity']} -> {s['new_complexity']}")

    if added_calls:
        print(f"\nAdded calls ({len(added_calls)}):")
        for c in added_calls:
            print(f"  + {c['caller']} calls {c['callee']}")

    if removed_calls:
        print(f"\nRemoved calls ({len(removed_calls)}):")
        for c in removed_calls:
            print(f"  - {c['caller']} called {c['callee']}")
