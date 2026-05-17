from __future__ import annotations

import re
from collections import deque
from pathlib import Path
from typing import Any

from pygraph.graph.types import CallEdge, FileNode, Graph, ImportEdge, SymbolNode


def _resolve_callee(
    callee_raw: str,
    symbols_by_name: dict[str, list[SymbolNode]],
    symbols_by_receiver: dict[str, list[SymbolNode]] | None = None,
) -> SymbolNode | None:
    if callee_raw in symbols_by_name:
        return symbols_by_name[callee_raw][0]

    parts = callee_raw.split(".")
    if len(parts) >= 2 and symbols_by_receiver is not None:
        receiver = parts[0]
        method = ".".join(parts[1:])
        candidates = symbols_by_receiver.get(receiver, [])
        for sym in candidates:
            if sym.name == method:
                return sym

    for i in range(len(parts), 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in symbols_by_name:
            return symbols_by_name[candidate][0]

    return None


class GraphQuery:
    def __init__(self, graph: Graph, root: str = ".") -> None:
        self.graph = graph
        self.root = root
        self._symbols_by_name: dict[str, list[SymbolNode]] = {}
        self._symbols_by_id: dict[str, SymbolNode] = {}
        self._symbols_by_receiver: dict[str, list[SymbolNode]] = {}
        self._files_by_path: dict[str, FileNode] = {}
        self._callees_of: dict[str, list[CallEdge]] = {}
        self._callers_by_name: dict[str, list[tuple[str, CallEdge]]] = {}
        self._imports_by_file: dict[str, list[ImportEdge]] = {}
        self._build_index()

    def _build_index(self) -> None:
        for sym in self.graph.symbols:
            self._symbols_by_name.setdefault(sym.name, []).append(sym)
            self._symbols_by_id[sym.id] = sym
            if sym.receiver:
                self._symbols_by_receiver.setdefault(
                    sym.receiver, []
                ).append(sym)

        for f in self.graph.files:
            self._files_by_path[f.path] = f

        for call in self.graph.calls:
            self._callees_of.setdefault(call.caller_symbol_id, []).append(call)
            callee = _resolve_callee(
                call.callee_raw,
                self._symbols_by_name,
                self._symbols_by_receiver,
            )
            if callee:
                self._callers_by_name.setdefault(callee.name, []).append(
                    (call.caller_symbol_id, call)
                )

        for imp in self.graph.imports:
            self._imports_by_file.setdefault(imp.from_file, []).append(imp)

    def _symbols_by_receiver_method(self, name: str) -> list[SymbolNode]:
        if "." not in name:
            return []
        parts = name.rsplit(".", 1)
        receiver, method = parts[0], parts[1]
        result: list[SymbolNode] = []
        for sym in self._symbols_by_receiver.get(receiver, []):
            if sym.name == method:
                result.append(sym)
        return result

    def _load_source(self, file_path: str) -> str | None:
        full = Path(self.root) / file_path
        try:
            return full.read_text()
        except OSError:
            return None

    def _match(self, name: str, pattern: str) -> bool:
        try:
            return re.search(pattern, name) is not None
        except re.error:
            return pattern in name

    def find_symbols(self, pattern: str) -> list[SymbolNode]:
        matched: list[SymbolNode] = []
        seen: set[str] = set()
        for sym in self.graph.symbols:
            if sym.id not in seen and self._match(sym.name, pattern):
                matched.append(sym)
                seen.add(sym.id)
        return matched

    def get_symbol(self, name: str) -> SymbolNode | None:
        matches = self._symbols_by_name.get(name, [])
        if matches:
            return matches[0]
        rm = self._symbols_by_receiver_method(name)
        if rm:
            return rm[0]
        return None

    def get_all_symbols(self, name: str) -> list[SymbolNode]:
        result = self._symbols_by_name.get(name, [])
        rm = self._symbols_by_receiver_method(name)
        result.extend(rm)
        return result

    def get_callers(
        self, symbol_name: str
    ) -> list[tuple[SymbolNode, CallEdge]]:
        result: list[tuple[SymbolNode, CallEdge]] = []
        for sym in self.get_all_symbols(symbol_name):
            for edge in self.graph.calls:
                if edge.callee_raw == sym.name or edge.callee_raw.endswith(
                    f".{sym.name}"
                ):
                    caller = self._symbols_by_id.get(edge.caller_symbol_id)
                    if caller:
                        result.append((caller, edge))
        return result

    def get_callees(
        self, symbol_name: str
    ) -> list[tuple[SymbolNode | None, CallEdge]]:
        result: list[tuple[SymbolNode | None, CallEdge]] = []
        for sym in self.get_all_symbols(symbol_name):
            edges = self._callees_of.get(sym.id, [])
            for edge in edges:
                callee = _resolve_callee(
                    edge.callee_raw,
                    self._symbols_by_name,
                    self._symbols_by_receiver,
                )
                result.append((callee, edge))
        return result

    def get_imports(self, file_path: str) -> list[ImportEdge]:
        return self._imports_by_file.get(file_path, [])

    def get_file(self, file_path: str) -> FileNode | None:
        return self._files_by_path.get(file_path)

    def get_public(self) -> list[SymbolNode]:
        return [s for s in self.graph.symbols if s.is_exported]

    def get_source(self, file_path: str) -> str | None:
        return self._load_source(file_path)

    def get_context(self, symbol_name: str) -> dict[str, Any]:
        symbol = self.get_symbol(symbol_name)
        source: str | None = None
        callers: list[dict[str, Any]] = []
        callees: list[dict[str, Any]] = []
        test_edges: list[dict[str, Any]] = []

        if symbol:
            for caller_sym, edge in self.get_callers(symbol_name):
                callers.append({
                    "caller": caller_sym.name,
                    "file": caller_sym.file,
                    "line": edge.line,
                    "callee_raw": edge.callee_raw,
                })
            for callee_sym, edge in self.get_callees(symbol_name):
                callees.append({
                    "callee": callee_sym.name if callee_sym else edge.callee_raw,
                    "file": callee_sym.file if callee_sym else "",
                    "line": edge.line,
                    "callee_raw": edge.callee_raw,
                })
            if symbol.file:
                source = self._load_source(symbol.file)

            for te in self.graph.test_edges:
                if te.target == symbol_name:
                    test_edges.append({
                        "test_func": te.test_func,
                        "file": te.file,
                        "line": te.line,
                    })

        return {
            "symbol": symbol,
            "callers": callers,
            "callees": callees,
            "test_edges": test_edges,
            "source": source,
        }

    def get_tests_for(self, symbol_name: str) -> list[dict[str, Any]]:
        tests: list[dict[str, Any]] = []
        for te in self.graph.test_edges:
            if te.target == symbol_name:
                tests.append({
                    "test_func": te.test_func,
                    "file": te.file,
                    "line": te.line,
                })
        return tests

    def _get_entry_point_names(self) -> set[str]:
        entry_points: set[str] = set()
        for sym in self.graph.symbols:
            if sym.is_exported:
                entry_points.add(sym.name)
        for route in self.graph.routes:
            parts = route.handler.rsplit(".", 1)
            entry_points.add(parts[-1])
        for te in self.graph.test_edges:
            entry_points.add(te.test_func)
        return entry_points

    def get_orphans(self) -> list[SymbolNode]:
        entry_points = self._get_entry_point_names()

        visited_ids: set[str] = set()
        queue: deque[str] = deque()

        for ep_name in entry_points:
            for sym in self.get_all_symbols(ep_name):
                if sym.id not in visited_ids:
                    visited_ids.add(sym.id)
                    queue.append(sym.name)

        while queue:
            current = queue.popleft()
            for sym in self.get_all_symbols(current):
                for edge in self._callees_of.get(sym.id, []):
                    callee = _resolve_callee(
                        edge.callee_raw,
                        self._symbols_by_name,
                        self._symbols_by_receiver,
                    )
                    if callee and callee.id not in visited_ids:
                        visited_ids.add(callee.id)
                        queue.append(callee.name)

        orphans: list[SymbolNode] = []
        for sym in self.graph.symbols:
            if not sym.is_exported and sym.id not in visited_ids:
                orphans.append(sym)

        return orphans

    def get_impact(
        self, symbol_name: str, max_depth: int | None = None
    ) -> list[dict[str, Any]]:
        visited_ids: set[str] = set()
        queue: deque[tuple[str, int]] = deque()
        result: list[dict[str, Any]] = []

        queue.append((symbol_name, 0))

        while queue:
            current, depth = queue.popleft()
            if max_depth is not None and depth >= max_depth:
                continue

            for sym in self.get_all_symbols(current):
                if sym.id in visited_ids:
                    continue
                visited_ids.add(sym.id)

                for edge in self._callees_of.get(sym.id, []):
                    callee = _resolve_callee(
                        edge.callee_raw,
                        self._symbols_by_name,
                        self._symbols_by_receiver,
                    )
                    if callee is None:
                        continue
                    result.append({
                        "caller": current,
                        "callee": callee.name,
                        "file": edge.file,
                        "line": edge.line,
                    })
                    if callee.id not in visited_ids:
                        queue.append((callee.name, depth + 1))

        return result

    def get_path(
        self, from_name: str, to_name: str
    ) -> list[dict[str, Any]] | None:
        if from_name == to_name:
            return []

        visited_ids: set[str] = set()
        queue: deque[list[str]] = deque([[from_name]])
        edge_cache: dict[tuple[str, str], dict[str, Any]] = {}

        while queue:
            path = queue.popleft()
            last = path[-1]

            for sym in self.get_all_symbols(last):
                if sym.id in visited_ids:
                    continue
                visited_ids.add(sym.id)

                for edge in self._callees_of.get(sym.id, []):
                    callee = _resolve_callee(
                        edge.callee_raw,
                        self._symbols_by_name,
                        self._symbols_by_receiver,
                    )
                    if callee is None:
                        continue
                    edge_cache[(last, callee.name)] = {
                        "from": last,
                        "to": callee.name,
                        "file": edge.file,
                        "line": edge.line,
                    }
                    if callee.name == to_name:
                        result: list[dict[str, Any]] = []
                        for i in range(len(path) - 1):
                            key = (path[i], path[i + 1])
                            result.append(edge_cache.get(key, {"from": path[i], "to": path[i + 1]}))
                        result.append(edge_cache[(last, to_name)])
                        return result
                    if callee.name not in visited_ids and callee.id not in visited_ids:
                        queue.append(path + [callee.name])

        return None

    def get_trace(
        self, error_message: str
    ) -> list[dict[str, Any]]:
        matching: list[dict[str, Any]] = []
        for err in self.graph.errors:
            if error_message in err.message or (
                err.message in error_message
            ):
                matching.append({
                    "message": err.message,
                    "function": err.function_name,
                    "file": err.file,
                    "line": err.line,
                })
        return matching

    def get_complexity(
        self, name: str | None = None
    ) -> list[dict[str, Any]]:
        if name:
            sym = self.get_symbol(name)
            if not sym:
                return []
            return [{
                "name": sym.name,
                "kind": sym.kind,
                "file": sym.file,
                "line": sym.line,
                "complexity": sym.complexity or 1,
            }]

        ranked: list[dict[str, Any]] = []
        for sym in self.graph.symbols:
            if sym.kind in ("function", "method") and sym.complexity is not None:
                ranked.append({
                    "name": sym.name,
                    "kind": sym.kind,
                    "file": sym.file,
                    "line": sym.line,
                    "complexity": sym.complexity,
                })
        ranked.sort(key=lambda x: x["complexity"], reverse=True)
        return ranked[:20]

    def get_coupling(
        self, name: str | None = None
    ) -> list[dict[str, Any]]:
        ca: dict[str, int] = {}
        ce: dict[str, int] = {}

        for sym in self.graph.symbols:
            n = sym.name
            ca.setdefault(n, 0)
            ce.setdefault(n, 0)

        for call in self.graph.calls:
            caller_name = call.caller_name
            ca_parts = call.callee_raw.split(".")
            callee_name = ca_parts[-1]
            ce[caller_name] = ce.get(caller_name, 0) + 1
            ca[callee_name] = ca.get(callee_name, 0) + 1

        if name:
            if name not in ca and name not in ce:
                return []
            a = ca.get(name, 0)
            e = ce.get(name, 0)
            instability = e / (a + e) if (a + e) > 0 else 0.0
            return [{"name": name, "ca": a, "ce": e, "instability": round(instability, 3)}]

        all_coupling: list[dict[str, Any]] = []
        for n in ca:
            a = ca[n]
            e = ce.get(n, 0)
            instability = e / (a + e) if (a + e) > 0 else 0.0
            all_coupling.append({"name": n, "ca": a, "ce": e, "instability": round(instability, 3)})
        all_coupling.sort(key=lambda x: x["ce"] + x["ca"], reverse=True)
        return all_coupling[:20]

    def get_hotspots(self, top_n: int = 10) -> list[dict[str, Any]]:
        ca: dict[str, int] = {}
        ce: dict[str, int] = {}

        for sym in self.graph.symbols:
            n = sym.name
            ca.setdefault(n, 0)
            ce.setdefault(n, 0)

        for call in self.graph.calls:
            caller_name = call.caller_name
            ca_parts = call.callee_raw.split(".")
            callee_name = ca_parts[-1]
            ce[caller_name] = ce.get(caller_name, 0) + 1
            ca[callee_name] = ca.get(callee_name, 0) + 1

        scores: list[dict[str, Any]] = []
        for sym in self.graph.symbols:
            if sym.kind not in ("function", "method") or sym.complexity is None:
                continue
            coupling = ca.get(sym.name, 0) + ce.get(sym.name, 0)
            score = sym.complexity * max(coupling, 1)
            scores.append({
                "name": sym.name,
                "kind": sym.kind,
                "file": sym.file,
                "line": sym.line,
                "complexity": sym.complexity,
                "coupling": coupling,
                "score": score,
            })
        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores[:top_n]

    def get_deps(self) -> list[dict[str, Any]]:
        return [
            {"module": d.module, "version": d.version}
            for d in self.graph.dependencies
        ]

    def get_errorflow(
        self, error_message: str
    ) -> list[dict[str, Any]]:
        matching_errors = [
            e for e in self.graph.errors
            if error_message in e.message or e.message in error_message
        ]

        result: list[dict[str, Any]] = []
        visited_funcs: set[str] = set()
        for err in matching_errors:
            if err.function_name in visited_funcs:
                continue
            visited_funcs.add(err.function_name)

            trace: list[dict[str, Any]] = []
            queue: deque[tuple[str, int]] = deque([(err.function_name, 0)])

            while queue:
                fn_name, _depth = queue.popleft()
                callers = self._callers_by_name.get(fn_name, [])
                for caller_id, edge in callers:
                    caller = self._symbols_by_id.get(caller_id)
                    if caller and caller.name not in visited_funcs:
                        visited_funcs.add(caller.name)
                        trace.append({
                            "from": caller.name,
                            "to": fn_name,
                            "file": edge.file,
                            "line": edge.line,
                        })
                        queue.append((caller.name, _depth + 1))

            result.append({
                "error": err,
                "trace": trace,
            })

        return result
