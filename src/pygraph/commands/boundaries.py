from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery, config_path: str = "") -> None:
    violations = query.get_boundary_violations(config_path)
    if not violations:
        print("No boundary violations found")
        return

    print(f"Found {len(violations)} boundary violation(s):\n")
    for v in violations:
        print(
            f"  {v['from_layer']} -> {v['to_layer']}: "
            f"{v['from']} calls {v['to']}  "
            f"({v['file']}:{v['line']})"
        )
