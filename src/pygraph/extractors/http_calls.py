from __future__ import annotations

import ast
from urllib.parse import urlparse

from pygraph.graph.types import HttpCallEdge

HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete"})
# Generic method names that accept the HTTP method as their first string argument.
# Users can extend this set via pyproject.toml [tool.pygraph.http_client.generic_methods].
GENERIC_HTTP_METHODS = frozenset({
    "request", "call", "invoke", "fetch", "send", "execute",
})


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

    def _is_client_constructor(call: ast.Call, module: str, classes: set[str]) -> bool:
        return (
            isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == module
            and call.func.attr in classes
        )

    for node in ast.walk(tree):
        # Pattern 1: Simple assignment: X = httpx.Client() / X = aiohttp.ClientSession()
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call = node.value
            if _is_client_constructor(call, "httpx", {"Client", "AsyncClient"}) \
                    or _is_client_constructor(call, "aiohttp", {"ClientSession"}):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        vars_set.add(target.id)

        # Pattern 2: Async context manager: async with httpx.AsyncClient() as X:
        #                                    async with aiohttp.ClientSession() as X:
        if isinstance(node, ast.AsyncWith):
            for item in node.items:
                if isinstance(item.context_expr, ast.Call):
                    call = item.context_expr
                    if _is_client_constructor(call, "httpx", {"AsyncClient"}) \
                            or _is_client_constructor(call, "aiohttp", {"ClientSession"}):
                        if isinstance(item.optional_vars, ast.Name):
                            vars_set.add(item.optional_vars.id)

    return vars_set


def _is_http_object(obj: ast.expr) -> bool:
    """Check if a call's receiver object could be an HTTP client.
    Accepts bare names (any variable) and attribute chains (self.client, self.http).
    Named constants and subscripts are excluded."""
    return isinstance(obj, (ast.Name, ast.Attribute))


def _extract_url(
    url_arg: ast.expr,
) -> tuple[str, bool, list[str]] | None:
    """Extract URL details from an AST expression node.
    Returns (url, has_dynamic, static_segments) or None if unresolvable."""
    if isinstance(url_arg, ast.Constant) and isinstance(url_arg.value, str):
        url = url_arg.value
        return url, False, _extract_static_segments(url)
    if isinstance(url_arg, ast.JoinedStr):
        url = ast.unparse(url_arg)
        return url, True, _extract_static_segments_from_joinedstr(url_arg)
    return None


def extract_http_calls(source: str, file_path: str) -> list[HttpCallEdge]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    _client_vars = _get_http_client_vars(tree)  # kept for future config use

    calls: list[HttpCallEdge] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        if not isinstance(func, ast.Attribute):
            continue

        # Step 1: Is the receiver a plausible HTTP client object?
        obj = func.value
        if not _is_http_object(obj):
            continue

        # Step 2: Determine the call pattern
        method_name = func.attr.lower()

        if method_name in HTTP_METHODS:
            # Standard pattern: client.get(url), self.client.post(url)
            if not node.args:
                continue
            url_result = _extract_url(node.args[0])
            if url_result is None:
                continue
            url, has_dynamic, static_segments = url_result
            http_method = method_name.upper()

        elif method_name in GENERIC_HTTP_METHODS:
            # Generic pattern: client.request("GET", url), self.client.call("POST", url)
            if len(node.args) < 2:
                continue
            # First argument must be a string literal (the HTTP method)
            method_arg = node.args[0]
            if not isinstance(method_arg, ast.Constant) or not isinstance(method_arg.value, str):
                continue
            http_method_raw = method_arg.value.upper()
            if http_method_raw not in {m.upper() for m in HTTP_METHODS}:
                continue
            # Second argument is the URL
            url_result = _extract_url(node.args[1])
            if url_result is None:
                continue
            url, has_dynamic, static_segments = url_result
            http_method = http_method_raw

        else:
            continue

        fn_name = _enclosing_function_name(tree, node.lineno) or ""

        calls.append(
            HttpCallEdge(
                source_file=file_path,
                source_line=node.lineno,
                function_name=fn_name,
                method=http_method,
                url=url,
                static_segments=static_segments,
                has_dynamic=has_dynamic,
            )
        )

    return calls
