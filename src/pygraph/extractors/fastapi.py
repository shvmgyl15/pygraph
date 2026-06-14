from __future__ import annotations

import ast
from typing import Any

from pygraph.graph.types import HTTPRoute, ResponseModelRef, SymbolNode

HTTP_METHOD_DECORATORS = frozenset({
    "get", "post", "put", "patch", "delete", "options", "head", "trace", "websocket",
})

SKIP_CONTAINER_TYPES = frozenset({
    "list", "List", "set", "Set", "tuple", "Tuple", "dict", "Dict",
    "Optional", "Union",
    "Iterable", "Sequence", "Type",
    "Annotated",
    "Awaitable", "Coroutine",
    "Page", "Paginated",
})


def _decorator_dotted_name(dec: ast.expr) -> str | None:
    if isinstance(dec, ast.Name):
        return dec.id
    if isinstance(dec, ast.Attribute):
        parts: list[str] = []
        cur: ast.expr = dec
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    if isinstance(dec, ast.Call):
        return _decorator_dotted_name(dec.func)
    return None


def _string_from_node(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _string_list_from_node(node: ast.expr) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple)):
        return [
            elt.value
            for elt in node.elts
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        ]
    return []


def _unpack_response_models(expr_str: str) -> list[str]:
    """Parse a response_model expression and return base model names.

    Handles: UserResponse, list[UserResponse], Optional[Union[A, B]], etc.
    """
    try:
        tree = ast.parse(expr_str, mode="eval")
    except SyntaxError:
        return []

    names: list[str] = []

    def _walk(node: ast.AST) -> None:
        if isinstance(node, ast.Name):
            if node.id not in SKIP_CONTAINER_TYPES:
                names.append(node.id)
        elif isinstance(node, ast.Subscript):
            _walk(node.value)
            if isinstance(node.slice, ast.AST):
                _walk(node.slice)
            elif isinstance(node.slice, (list, tuple)):
                for el in node.slice:
                    _walk(el)
        elif isinstance(node, ast.Tuple):
            for el in node.elts:
                _walk(el)
        elif isinstance(node, ast.Attribute):
            _walk(node.value)

    _walk(tree.body)

    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            result.append(n)
    return result


def _detect_fastapi_apps(tree: ast.Module) -> tuple[set[str], set[str]]:
    """Find variable names assigned from FastAPI() and from APIRouter()."""
    app_vars: set[str] = set()
    router_vars: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(node.value, ast.Call):
                    func_name = _decorator_dotted_name(node.value.func)
                    if func_name == "FastAPI":
                        app_vars.add(target.id)
                    elif func_name == "APIRouter":
                        router_vars.add(target.id)
    return app_vars, router_vars


def _extract_routes(
    tree: ast.Module,
    file_path: str,
    app_vars: set[str],
    router_vars: set[str],
) -> list[HTTPRoute]:
    routes: list[HTTPRoute] = []

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue

            dotted = _decorator_dotted_name(dec)
            if dotted is None:
                continue

            parts = dotted.rsplit(".", 1)
            if len(parts) != 2:
                continue

            app_or_router = parts[0]
            decorator_method = parts[1]

            if decorator_method not in HTTP_METHOD_DECORATORS:
                continue
            if app_or_router not in app_vars:
                continue
            if app_or_router in router_vars:
                continue

            path = ""
            if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(
                dec.args[0].value, str
            ):
                path = dec.args[0].value

            method = decorator_method.upper()
            if decorator_method == "websocket":
                method = "WS"

            response_model: str | None = None
            tags: list[str] = []

            for kw in dec.keywords:
                if kw.arg == "response_model":
                    response_model = ast.unparse(kw.value)
                elif kw.arg == "tags":
                    tags = _string_list_from_node(kw.value)

            routes.append(HTTPRoute(
                method=method,
                path=path,
                handler=f"{file_path}::{node.name}",
                file=file_path,
                line=node.lineno,
                response_model=response_model,
                tags=tags,
            ))

    return routes


def _detect_include_router(
    tree: ast.Module,
    file_path: str,
    app_vars: set[str],
    router_vars: set[str],
) -> list[HTTPRoute]:
    """Extract routes from app.include_router(router, prefix=...) calls."""
    extra_routes: list[HTTPRoute] = []
    router_prefixes: dict[str, str] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "include_router":
            continue

        app_var = ast.unparse(func.value) if isinstance(func.value, ast.Name) else ""
        if app_var not in app_vars or app_var in router_vars:
            continue

        if not node.args:
            continue
        router_var = ast.unparse(node.args[0]) if isinstance(node.args[0], ast.Name) else ""
        if not router_var:
            continue

        prefix = ""
        for kw in node.keywords:
            if kw.arg == "prefix":
                val = _string_from_node(kw.value)
                if val is not None:
                    prefix = val

        router_prefixes[router_var] = prefix

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            dotted = _decorator_dotted_name(dec)
            if dotted is None:
                continue
            parts = dotted.rsplit(".", 1)
            if len(parts) != 2:
                continue
            app_or_router = parts[0]
            decorator_method = parts[1]
            if decorator_method not in HTTP_METHOD_DECORATORS:
                continue
            if app_or_router not in router_prefixes:
                continue

            router_var = app_or_router
            prefix = router_prefixes.get(router_var, "")

            path = ""
            if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(
                dec.args[0].value, str
            ):
                path = dec.args[0].value

            full_path = prefix.rstrip("/") + "/" + path.lstrip("/") if prefix else path

            method = decorator_method.upper()
            if decorator_method == "websocket":
                method = "WS"

            response_model: str | None = None
            tags: list[str] = []

            for kw in dec.keywords:
                if kw.arg == "response_model":
                    response_model = ast.unparse(kw.value)
                elif kw.arg == "tags":
                    tags = _string_list_from_node(kw.value)

            extra_routes.append(HTTPRoute(
                method=method,
                path=full_path,
                handler=f"{file_path}::{node.name}",
                file=file_path,
                line=node.lineno,
                response_model=response_model,
                tags=tags,
            ))

    return extra_routes


def _create_response_model_refs(
    routes: list[HTTPRoute],
    symbols: list[SymbolNode],
    file_path: str,
) -> list[ResponseModelRef]:
    refs: list[ResponseModelRef] = []

    for route in routes:
        if not route.response_model:
            continue

        model_names = _unpack_response_models(route.response_model)
        if not model_names:
            continue

        for model_name in model_names:
            # Find the class symbol for this model
            matching = [
                s for s in symbols
                if s.name == model_name and s.kind == "class" and s.file == file_path
            ]
            if not matching:
                continue

            sym = matching[0]
            # Determine wrapper from the original expression
            wrapper: str | None = None
            raw = route.response_model.strip()
            if raw.startswith("list[") or raw.startswith("List["):
                wrapper = "List"
            elif raw.startswith("Optional["):
                wrapper = "Optional"
            elif raw.startswith("Union["):
                wrapper = "Union"
            elif "[" in raw and (raw.endswith("]") or raw.endswith("]]")):
                # Generic container, determine top-level wrapper
                top = raw.split("[", 1)[0].strip()
                if top not in ("list", "List", "Optional", "Union", "dict", "Dict"):
                    wrapper = top

            refs.append(ResponseModelRef(
                route_path=route.path,
                method=route.method,
                model_name=model_name,
                model_file=sym.file,
                symbol_id=sym.id,
                wrapper=wrapper,
            ))

    return refs


def extract_fastapi(
    source: str,
    file_path: str,
    symbols: list[SymbolNode] | None = None,
) -> dict[str, Any]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"routes": [], "response_model_refs": []}

    app_vars, router_vars = _detect_fastapi_apps(tree)
    if not app_vars and not router_vars:
        return {"routes": [], "response_model_refs": []}

    routes = _extract_routes(tree, file_path, app_vars, router_vars)
    routes.extend(_detect_include_router(tree, file_path, app_vars, router_vars))

    refs: list[ResponseModelRef] = []
    if symbols is not None:
        refs = _create_response_model_refs(routes, symbols, file_path)

    return {
        "routes": routes,
        "response_model_refs": refs,
    }
