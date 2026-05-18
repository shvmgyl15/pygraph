from __future__ import annotations

import ast
from typing import Any

from pygraph.graph.types import (
    BlueprintDef,
    BlueprintRegistration,
    ExtensionUsage,
    HTTPRoute,
    TemplateRef,
)

KNOWN_FLASK_EXTENSIONS = frozenset({
    "flask_sqlalchemy",
    "flask_migrate",
    "flask_login",
    "flask_wtf",
    "flask_mail",
    "flask_caching",
    "flask_restful",
    "flask_socketio",
    "flask_cors",
    "flask_admin",
    "flask_bcrypt",
    "flask_httpauth",
    "flask_limiter",
    "flask_smorest",
    "flask_praetorian",
    "flask_apscheduler",
    "flask_bootstrap",
    "flask_marshmallow",
    "flask_uploads",
    "flask_talisman",
    "flask_security",
    "flask_debugtoolbar",
    "flask_testing",
    "flask_oauthlib",
    "flask_s3",
    "flask_session",
    "flask_sijax",
    "flask_themes2",
    "flask_xcape",
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
    if isinstance(node, (ast.List, ast.Tuple)):
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                return elt.value
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


def _detect_blueprint_assignments(tree: ast.Module) -> list[BlueprintDef]:
    blueprints: list[BlueprintDef] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(node.value, ast.Call):
                    func = node.value.func
                    func_name = _decorator_dotted_name(func)
                    if func_name == "Blueprint":
                        args = node.value.args
                        name = _string_from_node(args[0]) if args else ""
                        if name is None:
                            name = ""
                        import_name = ""
                        if len(args) > 1:
                            val = _string_from_node(args[1])
                            if val is not None:
                                import_name = val
                        blueprints.append(
                            BlueprintDef(
                                name=name,
                                import_name=import_name,
                                file="",
                                line=node.lineno,
                            )
                        )
    return blueprints


def _detect_extensions(tree: ast.Module) -> list[ExtensionUsage]:
    extensions: list[ExtensionUsage] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "init_app":
                inner = func.value
                if isinstance(inner, ast.Name):
                    extensions.append(
                        ExtensionUsage(
                            name=inner.id,
                            file="",
                            line=node.lineno,
                        )
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                if mod in KNOWN_FLASK_EXTENSIONS:
                    extensions.append(
                        ExtensionUsage(
                            name=mod,
                            file="",
                            line=node.lineno,
                        )
                    )
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                top = (node.module or alias.name).split(".")[0]
                if top in KNOWN_FLASK_EXTENSIONS:
                    extensions.append(
                        ExtensionUsage(
                            name=top,
                            file="",
                            line=node.lineno,
                        )
                    )
    return extensions


def _extract_routes(tree: ast.Module, file_path: str) -> list[HTTPRoute]:
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
            if len(parts) != 2 or parts[1] != "route":
                continue

            path = ""
            if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(
                dec.args[0].value, str
            ):
                path = dec.args[0].value

            methods: list[str] = ["GET"]
            for kw in dec.keywords:
                if kw.arg == "methods":
                    raw = _string_list_from_node(kw.value)
                    if raw:
                        methods = raw

            for method in methods:
                routes.append(
                    HTTPRoute(
                        method=method.upper(),
                        path=path,
                        handler=f"{file_path}::{node.name}",
                        file=file_path,
                        line=node.lineno,
                    )
                )
    return routes


def _extract_blueprint_registrations(
    tree: ast.Module, file_path: str
) -> list[BlueprintRegistration]:
    registrations: list[BlueprintRegistration] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "register_blueprint":
            continue
        app_var_node = func.value
        app_var = ast.unparse(app_var_node) if isinstance(app_var_node, ast.Name) else ""
        if not app_var:
            continue
        if not node.args:
            continue
        bp_var = ast.unparse(node.args[0]) if isinstance(node.args[0], ast.Name) else ""
        if not bp_var:
            continue

        url_prefix = ""
        for kw in node.keywords:
            if kw.arg == "url_prefix":
                val = _string_from_node(kw.value)
                if val is not None:
                    url_prefix = val

        registrations.append(
            BlueprintRegistration(
                app_var=app_var,
                blueprint_var=bp_var,
                url_prefix=url_prefix,
                file=file_path,
                line=node.lineno,
            )
        )
    return registrations


def _extract_template_refs(tree: ast.Module, file_path: str) -> list[TemplateRef]:
    refs: list[TemplateRef] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func_name = _decorator_dotted_name(node)
        if func_name not in ("render_template", "render_template_string"):
            continue
        if not node.args:
            continue
        template_path = _string_from_node(node.args[0])
        if template_path is None:
            template_path = ast.unparse(node.args[0])

        enclosing = _enclosing_function_name(tree, node.lineno)

        refs.append(
            TemplateRef(
                template_path=template_path,
                function_name=enclosing or "",
                file=file_path,
                line=node.lineno,
            )
        )
    return refs


def _enclosing_function_name(tree: ast.Module, line_no: int) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            node.lineno <= line_no <= (node.end_lineno or node.lineno)
        ):
            return node.name
    return None


def _extract_error_handlers(tree: ast.Module, file_path: str) -> list[HTTPRoute]:
    handlers: list[HTTPRoute] = []
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
            if len(parts) != 2 or parts[1] != "errorhandler":
                continue

            error_code = ""
            if dec.args:
                error_code = ast.unparse(dec.args[0]).strip("\"'")

            handlers.append(
                HTTPRoute(
                    method="ERRORHANDLER",
                    path=error_code,
                    handler=f"{file_path}::{node.name}",
                    file=file_path,
                    line=node.lineno,
                )
            )
    return handlers


def _extract_cli_commands(tree: ast.Module, file_path: str) -> list[HTTPRoute]:
    commands: list[HTTPRoute] = []
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            dotted = _decorator_dotted_name(dec)
            if dotted is None:
                continue
            parts = dotted.rsplit(".", 2)
            if len(parts) < 3 or parts[1] != "cli" or parts[2] != "command":
                continue

            cmd_name = node.name
            if dec.args:
                extracted = _string_from_node(dec.args[0])
                if extracted is not None:
                    cmd_name = extracted

            commands.append(
                HTTPRoute(
                    method="CLI",
                    path=cmd_name,
                    handler=f"{file_path}::{node.name}",
                    file=file_path,
                    line=node.lineno,
                )
            )
    return commands


def _extract_add_url_rule_calls(tree: ast.Module, file_path: str) -> list[HTTPRoute]:
    routes: list[HTTPRoute] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "add_url_rule":
            continue

        if not node.args:
            continue
        path = _string_from_node(node.args[0])
        if path is None:
            path = ast.unparse(node.args[0])

        methods: list[str] = ["GET"]
        view_func: str | None = None

        for kw in node.keywords:
            if kw.arg == "methods":
                raw = _string_list_from_node(kw.value)
                if raw:
                    methods = raw
            elif kw.arg == "view_func":
                view_func = ast.unparse(kw.value)

        if view_func is None and len(node.args) > 1 and isinstance(node.args[1], ast.Name):
            view_func = node.args[1].id

        if view_func:
            for method in methods:
                routes.append(
                    HTTPRoute(
                        method=method.upper(),
                        path=path,
                        handler=f"{file_path}::{view_func}",
                        file=file_path,
                        line=node.lineno,
                    )
                )
    return routes


def extract_flask(source: str, file_path: str) -> dict[str, Any]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {
            "routes": [],
            "blueprints": [],
            "blueprint_registrations": [],
            "template_refs": [],
            "error_handlers": [],
            "cli_commands": [],
            "extensions": [],
        }

    return {
        "routes": _extract_routes(tree, file_path) + _extract_add_url_rule_calls(tree, file_path),
        "blueprints": _detect_blueprint_assignments(tree),
        "blueprint_registrations": _extract_blueprint_registrations(tree, file_path),
        "template_refs": _extract_template_refs(tree, file_path),
        "error_handlers": _extract_error_handlers(tree, file_path),
        "cli_commands": _extract_cli_commands(tree, file_path),
        "extensions": _detect_extensions(tree),
    }
