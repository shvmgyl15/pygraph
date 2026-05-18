from __future__ import annotations

import ast

from pygraph.graph.types import ImplementsEdge


def extract_implements(source: str, file_path: str) -> list[ImplementsEdge]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    edges: list[ImplementsEdge] = []
    import_map: dict[str, str] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                import_map[name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                name = alias.asname or alias.name
                import_map[name] = f"{module}.{alias.name}" if module else alias.name

    is_abc_imported = any(
        v in ("abc", "abc.ABC", "abc.abstractmethod") for v in import_map.values()
    )
    is_protocol_imported = any(
        "typing" in v and "Protocol" in v
        or v == "Protocol"
        for v in import_map.values()
    )

    if not is_abc_imported and not is_protocol_imported:
        return edges

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        concrete_name = node.name

        for base in node.bases:
            base_name = ast.unparse(base)

            base_root = base_name.split(".")[0]
            resolved = import_map.get(base_root, base_root)
            full_base = base_name.replace(base_root, resolved, 1)

            if "ABC" in full_base or "Protocol" in full_base or "abc" in full_base:
                edges.append(
                    ImplementsEdge(
                        interface=full_base,
                        concrete=concrete_name,
                    )
                )

    return edges
