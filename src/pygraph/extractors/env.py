from __future__ import annotations

import ast

from pygraph.graph.types import EnvRead


def _enclosing_function_name(tree: ast.Module, line_no: int) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            node.lineno <= line_no <= (node.end_lineno or node.lineno)
        ):
            return node.name
    return None


def extract_env_reads(source: str, file_path: str) -> list[EnvRead]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    reads: list[EnvRead] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        accessor: str | None = None
        key: str | None = None

        if isinstance(func, ast.Attribute):
            if func.attr == "get":
                value = func.value
                if isinstance(value, ast.Attribute) and value.attr == "environ":
                    accessor = "os.environ.get"
                elif isinstance(value, ast.Name) and value.id == "environ":
                    accessor = "environ.get"
            elif func.attr == "getenv":
                if isinstance(func.value, ast.Name) and func.value.id == "os":
                    accessor = "os.getenv"

        if accessor and node.args:
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                key = first_arg.value

        if key and accessor:
            fn_name = _enclosing_function_name(tree, node.lineno)
            reads.append(
                EnvRead(
                    key=key,
                    accessor=accessor,
                    file=file_path,
                    line=node.lineno,
                    function_name=fn_name or "",
                )
            )

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "environ"
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            fn_name = _enclosing_function_name(tree, node.lineno)
            reads.append(
                EnvRead(
                    key=node.slice.value,
                    accessor="os.environ[]",
                    file=file_path,
                    line=node.lineno,
                    function_name=fn_name or "",
                )
            )

    return reads
