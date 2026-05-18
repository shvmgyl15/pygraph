from __future__ import annotations

import ast

from pygraph.graph.types import ErrorEdge


def _enclosing_function_name(tree: ast.Module, line_no: int) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            node.lineno <= line_no <= (node.end_lineno or node.lineno)
        ):
            return node.name
    return None


def _raise_message(node: ast.Raise) -> str:
    if node.exc is None:
        return ""
    if isinstance(node.exc, ast.Call):
        return ast.unparse(node.exc)
    return ast.unparse(node.exc)


def extract_errors(source: str, file_path: str) -> list[ErrorEdge]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    errors: list[ErrorEdge] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise):
            continue

        fn_name = _enclosing_function_name(tree, node.lineno)
        if fn_name is None:
            continue

        message = _raise_message(node)

        errors.append(
            ErrorEdge(
                message=message,
                function_name=fn_name,
                file=file_path,
                line=node.lineno,
            )
        )

    return errors
