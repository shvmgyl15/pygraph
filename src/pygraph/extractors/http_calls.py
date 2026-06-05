from __future__ import annotations

import ast
from urllib.parse import urlparse

from pygraph.graph.types import HttpCallEdge

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _enclosing_function_name(tree: ast.Module, line_no: int) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            node.lineno <= line_no <= (node.end_lineno or node.lineno)
        ):
            return node.name
    return None


def _extract_static_segments(url: str) -> list[str]:
    parsed = urlparse(url)
    path = parsed.path
    return [s for s in path.split("/") if s]


def _extract_static_segments_from_joinedstr(node: ast.JoinedStr) -> list[str]:
    static_parts: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            static_parts.append(value.value)
    combined = "".join(static_parts)
    return _extract_static_segments(combined)


def _get_http_client_vars(tree: ast.Module) -> set[str]:
    vars_set: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call = node.value
            if (
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "httpx"
                and call.func.attr in ("Client", "AsyncClient")
            ):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        vars_set.add(target.id)
    return vars_set


def extract_http_calls(source: str, file_path: str) -> list[HttpCallEdge]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    client_vars = _get_http_client_vars(tree)

    calls: list[HttpCallEdge] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        if not isinstance(func, ast.Attribute):
            continue

        method = func.attr.lower()
        if method not in HTTP_METHODS:
            continue

        obj = func.value
        if not (
            isinstance(obj, ast.Name)
            and (obj.id in ("requests", "httpx") or obj.id in client_vars)
        ):
            continue

        if not node.args:
            continue

        url_arg = node.args[0]
        fn_name = _enclosing_function_name(tree, node.lineno) or ""

        has_dynamic: bool = False
        url: str = ""
        static_segments: list[str] = []

        if isinstance(url_arg, ast.Constant) and isinstance(url_arg.value, str):
            url = url_arg.value
            has_dynamic = False
            static_segments = _extract_static_segments(url)
        elif isinstance(url_arg, ast.JoinedStr):
            url = ast.unparse(url_arg)
            has_dynamic = True
            static_segments = _extract_static_segments_from_joinedstr(url_arg)
        else:
            continue

        calls.append(
            HttpCallEdge(
                source_file=file_path,
                source_line=node.lineno,
                function_name=fn_name,
                method=method.upper(),
                url=url,
                static_segments=static_segments,
                has_dynamic=has_dynamic,
            )
        )

    return calls
