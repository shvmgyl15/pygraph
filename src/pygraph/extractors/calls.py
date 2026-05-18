from __future__ import annotations

import ast

from pygraph.graph.types import CallEdge

from .symbols import _symbol_id


def _get_enclosing_qualified_name(
    tree: ast.Module,
    line_no: int,
) -> str | None:
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if (
                    isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and item.lineno <= line_no <= (item.end_lineno or item.lineno)
                ):
                    return f"{node.name}.{item.name}"

    best: str | None = None
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.lineno <= line_no <= (node.end_lineno or node.lineno)
        ):
            best = node.name
    return best


def _get_callee_raw(node: ast.Call) -> str:
    return ast.unparse(node.func)


def extract_calls(
    source: str,
    file_path: str,
) -> list[CallEdge]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    calls: list[CallEdge] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            caller = _get_enclosing_qualified_name(tree, node.lineno)
            if caller is None:
                continue
            callee_raw = _get_callee_raw(node)
            calls.append(
                CallEdge(
                    caller_symbol_id=_symbol_id(file_path, caller),
                    caller_name=caller,
                    callee_raw=callee_raw,
                    file=file_path,
                    line=node.lineno,
                )
            )

    return calls
