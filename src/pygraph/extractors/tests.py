from __future__ import annotations

import ast

from pygraph.graph.types import TestEdge


def extract_test_edges(source: str, file_path: str) -> list[TestEdge]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    edges: list[TestEdge] = []
    is_test_file = file_path.startswith(("test_", "tests/")) or "/test_" in file_path

    if not is_test_file:
        return edges

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue

        test_func_name = node.name
        targets: set[str] = set()

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Attribute):
                    callee = ast.unparse(func)
                    parts = callee.split(".")
                    for p in parts:
                        if p.endswith("()"):
                            p = p[:-2]
                        if p and not p.startswith("test_") and p[0].islower():
                            targets.add(p)
                elif isinstance(func, ast.Name):
                    name = func.id
                    skip = {"assert", "self", "None", "True", "False"}
                    qualifies = name and not name.startswith("test_") and name[0].islower()
                    if qualifies and name not in skip:
                        targets.add(name)
                        targets.add(name)

        for target in targets:
            edges.append(
                TestEdge(
                    test_func=test_func_name,
                    target=target,
                    file=file_path,
                    line=node.lineno,
                )
            )

    return edges
