from __future__ import annotations

import ast

from pygraph.graph.types import StructField, SymbolNode


def _symbol_id(file_path: str, name: str) -> str:
    return f"{file_path}::{name}"


def _get_docstring(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Module,
) -> str | None:
    doc = ast.get_docstring(node)
    return doc if doc else None


def _get_decorator_names(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> list[str]:
    names: list[str] = []
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name):
            names.append(dec.id)
        elif isinstance(dec, ast.Attribute):
            parts: list[str] = []
            cur: ast.expr = dec
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
            names.append(".".join(reversed(parts)))
        elif isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Name):
                names.append(dec.func.id)
            elif isinstance(dec.func, ast.Attribute):
                parts2: list[str] = []
                cur2: ast.expr = dec.func
                while isinstance(cur2, ast.Attribute):
                    parts2.append(cur2.attr)
                    cur2 = cur2.value
                if isinstance(cur2, ast.Name):
                    parts2.append(cur2.id)
                names.append(".".join(reversed(parts2)))
    return names


def _has_yield(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(
        isinstance(child, (ast.Yield, ast.YieldFrom))
        for child in ast.walk(node)
    )


def _get_return_annotation(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    if node.returns is None:
        return None
    return ast.unparse(node.returns)


def _get_type_annotation(node: ast.AnnAssign) -> str | None:
    if node.annotation is None:
        return None
    return ast.unparse(node.annotation)


def _extract_all_from_module(
    tree: ast.Module,
    file_path: str,
    package_name: str,
) -> set[str]:
    all_names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "__all__"
                    and isinstance(node.value, (ast.List, ast.Tuple))
                ):
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            all_names.add(elt.value)
    return all_names


def _is_exported(name: str, all_names: set[str]) -> bool:
    if name in all_names:
        return True
    if name.startswith("__") and name.endswith("__"):
        return True
    return not name.startswith("_")


def extract_symbols(
    source: str,
    file_path: str,
    package_name: str,
) -> list[SymbolNode]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    all_names = _extract_all_from_module(tree, file_path, package_name)
    symbols: list[SymbolNode] = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(_function_to_symbol(node, file_path, package_name, all_names))
        elif isinstance(node, ast.ClassDef):
            cls_symbols = _class_to_symbols(node, file_path, package_name, all_names)
            symbols.extend(cls_symbols)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id == "__all__":
                        continue
                    name = target.id
                    symbols.append(
                        SymbolNode(
                            id=_symbol_id(file_path, name),
                            kind="constant" if name.isupper() else "variable",
                            name=name,
                            package_name=package_name,
                            file=file_path,
                            line=node.lineno,
                            end_line=node.end_lineno or node.lineno,
                            is_exported=_is_exported(name, all_names),
                        )
                    )
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                name = node.target.id
                symbols.append(
                    SymbolNode(
                        id=_symbol_id(file_path, name),
                        kind="variable",
                        name=name,
                        package_name=package_name,
                        file=file_path,
                        line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        is_exported=_is_exported(name, all_names),
                        type_annotation=_get_type_annotation(node),
                    )
                )

    return symbols


def _cyclomatic_complexity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    complexity = 1
    for child in ast.walk(node):
        if isinstance(
            child,
            (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler, ast.Assert),
        ):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
        elif isinstance(child, ast.Match):
            complexity += len(child.cases)
        elif isinstance(child, ast.comprehension):
            complexity += len(child.ifs)
    return complexity


def _function_to_symbol(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    file_path: str,
    package_name: str,
    all_names: set[str],
    receiver: str | None = None,
) -> SymbolNode:
    decorators = _get_decorator_names(node)
    deco_set = set(decorators)

    args_count = len(node.args.args)
    kwonly_count = len(node.args.kwonlyargs)
    kwarg_count = 1 if node.args.kwarg else 0
    vararg_count = 1 if node.args.vararg else 0
    arity = args_count + kwonly_count + kwarg_count + vararg_count

    return SymbolNode(
        id=_symbol_id(file_path, f"{receiver + '.' if receiver else ''}{node.name}"),
        kind="method" if receiver else "function",
        name=node.name,
        receiver=receiver,
        package_name=package_name,
        file=file_path,
        line=node.lineno,
        end_line=node.end_lineno or node.lineno,
        doc=_get_docstring(node),
        signature=ast.unparse(node),
        is_exported=_is_exported(node.name, all_names),
        is_async=isinstance(node, ast.AsyncFunctionDef),
        is_generator=_has_yield(node),
        is_classmethod="classmethod" in deco_set,
        is_staticmethod="staticmethod" in deco_set,
        is_property="property" in deco_set,
        is_abstractmethod="abstractmethod" in deco_set,
        decorators=decorators,
        type_annotation=_get_return_annotation(node),
        arity=arity,
        complexity=_cyclomatic_complexity(node),
    )


def _class_to_symbols(
    node: ast.ClassDef,
    file_path: str,
    package_name: str,
    all_names: set[str],
) -> list[SymbolNode]:
    cls_id = _symbol_id(file_path, node.name)
    bases: list[str] = []
    for base in node.bases:
        bases.append(ast.unparse(base))

    struct_fields: list[StructField] = []
    for item in node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            struct_fields.append(
                StructField(
                    name=item.target.id,
                    type=ast.unparse(item.annotation) if item.annotation else "",
                )
            )

    cls_symbol = SymbolNode(
        id=cls_id,
        kind="class",
        name=node.name,
        package_name=package_name,
        file=file_path,
        line=node.lineno,
        end_line=node.end_lineno or node.lineno,
        doc=_get_docstring(node),
        is_exported=_is_exported(node.name, all_names),
        decorators=_get_decorator_names(node),
        bases=bases,
        struct_fields=struct_fields,
    )

    methods: list[SymbolNode] = []
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(
                _function_to_symbol(
                    item, file_path, package_name, all_names, receiver=node.name
                )
            )

    return [cls_symbol, *methods]
