from __future__ import annotations

import ast
from typing import Any

from pygraph.graph.types import SymbolNode


def _decorator_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        inner = _decorator_name(node.value)
        return f"{inner}.{node.attr}" if inner else node.attr
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return None


def _match_callee(node: ast.Call, pattern: str) -> bool:
    parts = pattern.split(".")
    callee = node.func
    i = len(parts) - 1
    while i >= 0:
        if isinstance(callee, ast.Attribute):
            if callee.attr == parts[i]:
                callee = callee.value
                i -= 1
            else:
                return False
        elif isinstance(callee, ast.Name):
            if i == 0 and callee.id == parts[i]:
                return True
            return i < 0
        elif isinstance(callee, ast.Call):
            callee = callee.func
        else:
            return False
    # All segments consumed — match succeeded regardless of remaining callee
    return True


def _extract_kwarg(call: ast.Call, name: str) -> str | None:
    for kw in call.keywords:
        if kw.arg == name and isinstance(kw.value, ast.Constant):
            val: object = kw.value.value
            if isinstance(val, str):
                return val
    return None


def _extract_arg_by_index(call: ast.Call, index: int) -> str | None:
    if index < len(call.args):
        arg = call.args[index]
        if isinstance(arg, ast.Constant):
            val: object = arg.value
            if isinstance(val, str):
                return val
    return None


def _make_entry(
    boundary: dict[str, Any], name: str, line: int,
    node: ast.Call | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {"boundary": boundary["name"], "symbol": name, "line": line}
    arg_map = boundary.get("match", {}).get("args", {})
    for arg_name, spec in arg_map.items():
        if node is None:
            continue
        if isinstance(spec, int):
            val = _extract_arg_by_index(node, spec)
        elif isinstance(spec, str):
            val = _extract_kwarg(node, spec)
        else:
            val = None
        if val is not None:
            entry[arg_name] = val
    return entry


def extract_event_productions(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    event_config: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for node in ast.walk(func_node):
        if not isinstance(node, ast.Call):
            continue
        for boundary in event_config:
            if boundary.get("type") != "producer":
                continue
            callee_pattern = boundary.get("match", {}).get("callee")
            if not callee_pattern:
                continue
            if not _match_callee(node, callee_pattern):
                continue
            result.append(_make_entry(boundary, func_node.name, node.lineno, node))
    return result


def _extract_guard_value(node: ast.expr) -> dict[str, Any]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {"value": node.value, "const_ref": False, "ref": None}
    if isinstance(node, ast.Name):
        return {"value": None, "const_ref": True, "ref": node.id}
    # Chained attributes: SomeClass.CONSTANT, SomeClass.CONSTANT.value, SomeModel().attr
    parts: list[str] = []
    cur: ast.expr = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    elif isinstance(cur, ast.Call) and isinstance(cur.func, ast.Name):
        parts.append(f"{cur.func.id}()")
    else:
        parts.append(ast.unparse(cur))
    return {"value": None, "const_ref": True, "ref": ".".join(reversed(parts))}


def _extract_guards_from_if(node: ast.If) -> list[dict[str, Any]]:
    if not isinstance(node.test, ast.Compare):
        return []
    compare = node.test
    if len(compare.ops) != 1 or len(compare.comparators) != 1:
        return []
    if not isinstance(compare.ops[0], ast.Eq):
        return []

    # Extract field name from left side
    left = compare.left
    if isinstance(left, ast.Name):
        field = left.id
    elif isinstance(left, ast.Call):
        # data.get("key") == value pattern
        if (isinstance(left.func, ast.Attribute) and left.func.attr == "get"
                and len(left.args) == 1 and isinstance(left.args[0], ast.Constant)
                and isinstance(left.args[0].value, str)):
            field = left.args[0].value
        else:
            return []
    else:
        return []

    # Extract value from right side
    guard = _extract_guard_value(compare.comparators[0])
    guard["field"] = field
    guard["op"] = "eq"
    return [guard]


def extract_dispatch_guards(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[dict[str, Any]]:
    if not func_node.body:
        return []
    first = func_node.body[0]
    if not isinstance(first, ast.If):
        return []
    guards = _extract_guards_from_if(first)
    cur = first.orelse
    while cur:
        if len(cur) == 1 and isinstance(cur[0], ast.If):
            guards.extend(_extract_guards_from_if(cur[0]))
            cur = cur[0].orelse
        else:
            break
    return guards


def _match_consumer_call_sites(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    event_config: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for node in ast.walk(func_node):
        if not isinstance(node, ast.Call):
            continue
        callee_str = ""
        if isinstance(node.func, (ast.Name, ast.Attribute)):
            callee_str = ast.unparse(node.func)
        for boundary in event_config:
            if boundary.get("type") != "consumer":
                continue
            match = boundary.get("match", {})
            cp = match.get("callee_pattern")
            if cp and cp in callee_str:
                result.append(_make_entry(boundary, func_node.name, node.lineno, node))
                continue
            hp = match.get("hook_pattern")
            if hp and hp in callee_str:
                result.append(_make_entry(boundary, func_node.name, node.lineno, node))
    return result


def extract_event_consumptions(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    cls_node: ast.ClassDef | None,
    event_config: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    # Decorator matching
    for dec in func_node.decorator_list:
        name = _decorator_name(dec)
        if not name:
            continue
        for boundary in event_config:
            if boundary.get("type") != "consumer":
                continue
            dec_pattern = boundary.get("match", {}).get("decorator")
            if not dec_pattern or name != dec_pattern:
                continue
            if isinstance(dec, ast.Call):
                result.append(_make_entry(boundary, func_node.name, func_node.lineno, dec))
            else:
                result.append(_make_entry(boundary, func_node.name, func_node.lineno))

    # Call site pattern matching
    result.extend(_match_consumer_call_sites(func_node, event_config))

    # Guards from first if block
    guards = extract_dispatch_guards(func_node)
    if guards and not any(e.get("guards") for e in result):
        result.append({
            "boundary": "dispatch_guards", "guards": guards,
            "symbol": func_node.name, "line": func_node.lineno,
        })

    # Interface matching on class
    if cls_node:
        cls_bases = [ast.unparse(b) for b in cls_node.bases]
        for boundary in event_config:
            if boundary.get("type") != "consumer":
                continue
            iface = boundary.get("match", {}).get("interface")
            if not iface or iface not in cls_bases:
                continue
            entry = _make_entry(boundary, cls_node.name, cls_node.lineno)
            g = extract_dispatch_guards(func_node)
            if g:
                entry["guards"] = g
            result.append(entry)

    return result


def enrich_symbols(
    symbols: list[SymbolNode],
    source: str,
    event_config: list[dict[str, Any]],
) -> list[SymbolNode]:
    if not event_config:
        return symbols
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return symbols

    cls_map: dict[str, ast.ClassDef] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            cls_map[node.name] = node

    enriched: list[SymbolNode] = []
    for sym in symbols:
        if sym.kind in ("function", "method") and sym.file:
            cls_node = cls_map.get(sym.receiver) if sym.receiver else None
            func_node = _find_func_in_tree(tree, sym.name, cls_node)
            if func_node:
                sym.event_productions = extract_event_productions(
                    func_node, event_config,
                )
                sym.event_consumptions = extract_event_consumptions(
                    func_node, cls_node, event_config,
                )
        if sym.kind == "class" and sym.name in cls_map:
            cls_node = cls_map[sym.name]
            for boundary in event_config:
                if boundary.get("type") != "consumer":
                    continue
                iface = boundary.get("match", {}).get("interface")
                if not iface or iface not in [ast.unparse(b) for b in cls_node.bases]:
                    continue
                already = any(
                    e.get("boundary") == boundary["name"]
                    for e in sym.event_consumptions
                )
                if not already:
                    sym.event_consumptions.append({
                        "boundary": boundary["name"],
                        "symbol": sym.name,
                        "line": cls_node.lineno,
                    })
        enriched.append(sym)
    return enriched


def _find_func_in_tree(
    tree: ast.Module, func_name: str, cls_node: ast.ClassDef | None,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    if cls_node:
        for item in cls_node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == func_name:
                return item
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            return node
    return None
