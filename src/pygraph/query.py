from __future__ import annotations

import re
import subprocess
import time
from collections import deque
from pathlib import Path
from typing import Any

from pygraph.builder import build_graph_from_ref, resolve_git_ref
from pygraph.graph.boundaries import BoundaryConfig, load_boundary_config
from pygraph.graph.serialize import deserialize, read_graph, write_graph
from pygraph.graph.types import CallEdge, FileNode, Graph, ImportEdge, SymbolNode


def _split_dotted_path(path: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for ch in path:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "." and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def _strip_call_args(segment: str) -> str:
    paren = segment.find("(")
    return segment[:paren] if paren != -1 else segment


def _normalize_callee_raw(callee_raw: str) -> str:
    parts = _split_dotted_path(callee_raw)
    cleaned = [_strip_call_args(p) for p in parts]
    return ".".join(cleaned)


def _resolve_callee(
    callee_raw: str,
    symbols_by_name: dict[str, list[SymbolNode]],
    symbols_by_receiver: dict[str, list[SymbolNode]] | None = None,
) -> SymbolNode | None:
    normalized = _normalize_callee_raw(callee_raw)

    if normalized in symbols_by_name:
        return symbols_by_name[normalized][0]

    parts = normalized.split(".")
    if len(parts) >= 2 and symbols_by_receiver is not None:
        for i in range(len(parts) - 2, -1, -1):
            cls_name = parts[i]
            if cls_name in symbols_by_name:
                for cls_sym in symbols_by_name[cls_name]:
                    if cls_sym.kind == "class":
                        method_name = ".".join(parts[i + 1 :])
                        for msym in symbols_by_receiver.get(cls_name, []):
                            if msym.name == method_name:
                                return msym

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
                if callee.receiver:
                    self._callers_by_name.setdefault(callee.receiver, []).append(
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
        target_ids: set[str] = set()
        for sym in self.get_all_symbols(symbol_name):
            target_ids.add(sym.id)

        for edge in self.graph.calls:
            callee = _resolve_callee(
                edge.callee_raw,
                self._symbols_by_name,
                self._symbols_by_receiver,
            )
            if callee is None:
                continue
            if callee.id in target_ids or callee.receiver == symbol_name:
                caller = self._symbols_by_id.get(edge.caller_symbol_id)
                if caller:
                    result.append((caller, edge))
        return result

    def get_callees(
        self, symbol_name: str
    ) -> list[tuple[SymbolNode | None, CallEdge]]:
        result: list[tuple[SymbolNode | None, CallEdge]] = []
        seen: set[tuple[str, str, int]] = set()
        for sym in self.get_all_symbols(symbol_name):
            edges = self._callees_of.get(sym.id, [])
            for edge in edges:
                callee = _resolve_callee(
                    edge.callee_raw,
                    self._symbols_by_name,
                    self._symbols_by_receiver,
                )
                key = (edge.caller_symbol_id, edge.callee_raw, edge.line)
                if key not in seen:
                    seen.add(key)
                    result.append((callee, edge))

            if sym.kind == "class":
                for method_sym in self._symbols_by_receiver.get(sym.name, []):
                    method_edges = self._callees_of.get(method_sym.id, [])
                    for edge in method_edges:
                        callee = _resolve_callee(
                            edge.callee_raw,
                            self._symbols_by_name,
                            self._symbols_by_receiver,
                        )
                        key = (edge.caller_symbol_id, edge.callee_raw, edge.line)
                        if key not in seen:
                            seen.add(key)
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

    def get_context(
        self, symbol_name: str, include_source: bool = True
    ) -> dict[str, Any]:
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
            if include_source and symbol.file:
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
            parts = route.handler.rsplit("::", 1)
            if len(parts) > 1:
                entry_points.add(parts[-1])
        for te in self.graph.test_edges:
            entry_points.add(te.test_func)
        return entry_points

    def get_orphans(self, include_public: bool = False) -> list[SymbolNode]:
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
            if sym.id not in visited_ids and (include_public or not sym.is_exported):
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
                    if callee.id not in visited_ids:
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

    def _qualified_name(self, sym: SymbolNode) -> str:
        return f"{sym.receiver}.{sym.name}" if sym.receiver else sym.name

    def get_coupling(
        self, name: str | None = None
    ) -> list[dict[str, Any]]:
        ca: dict[str, int] = {}
        ce: dict[str, int] = {}

        for sym in self.graph.symbols:
            key = self._qualified_name(sym)
            ca.setdefault(key, 0)
            ce.setdefault(key, 0)

        for call in self.graph.calls:
            caller_sym = self._symbols_by_id.get(call.caller_symbol_id)
            if caller_sym:
                caller_key = self._qualified_name(caller_sym)
                ce[caller_key] = ce.get(caller_key, 0) + 1

            callee = _resolve_callee(
                call.callee_raw,
                self._symbols_by_name,
                self._symbols_by_receiver,
            )
            if callee:
                callee_key = self._qualified_name(callee)
                ca[callee_key] = ca.get(callee_key, 0) + 1

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
            key = self._qualified_name(sym)
            ca.setdefault(key, 0)
            ce.setdefault(key, 0)

        for call in self.graph.calls:
            caller_sym = self._symbols_by_id.get(call.caller_symbol_id)
            if caller_sym:
                caller_key = self._qualified_name(caller_sym)
                ce[caller_key] = ce.get(caller_key, 0) + 1

            callee = _resolve_callee(
                call.callee_raw,
                self._symbols_by_name,
                self._symbols_by_receiver,
            )
            if callee:
                callee_key = self._qualified_name(callee)
                ca[callee_key] = ca.get(callee_key, 0) + 1

        scores: list[dict[str, Any]] = []
        for sym in self.graph.symbols:
            if sym.kind not in ("function", "method") or sym.complexity is None:
                continue
            key = self._qualified_name(sym)
            coupling = ca.get(key, 0) + ce.get(key, 0)
            score = sym.complexity * max(coupling, 1)
            scores.append({
                "name": key,
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

    def get_boundary_violations(
        self, config_path: str = ""
    ) -> list[dict[str, Any]]:
        search_root = Path(self.root)
        candidates = [
            search_root / ".pygraph" / "boundaries.json",
            Path(config_path) if config_path else None,
        ]
        cfg: BoundaryConfig | None = None
        for p in candidates:
            if p and p.exists():
                cfg = load_boundary_config(str(p))
                break
        if cfg is None:
            return []

        violations: list[dict[str, Any]] = []

        for call in self.graph.calls:
            caller_sym = self._symbols_by_id.get(call.caller_symbol_id)
            if not caller_sym:
                continue

            caller_layer = cfg.layer_for(caller_sym.file)
            if caller_layer is None:
                continue

            callee_sym = _resolve_callee(
                call.callee_raw,
                self._symbols_by_name,
                self._symbols_by_receiver,
            )
            if not callee_sym:
                continue

            callee_layer = cfg.layer_for(callee_sym.file)
            if callee_layer is None:
                continue

            if not cfg.is_allowed(caller_layer, callee_layer):
                violations.append({
                    "from": caller_sym.name,
                    "to": callee_sym.name,
                    "from_layer": caller_layer,
                    "to_layer": callee_layer,
                    "file": call.file,
                    "line": call.line,
                })

        return violations

    def _load_git_graph(self, since: str) -> Graph | None:
        try:
            cwd = self.root if Path(self.root).exists() else None
            result = subprocess.run(
                ["git", "show", f"{since}:.pygraph/graph.json"],
                capture_output=True, text=True, timeout=10,
                cwd=cwd,
            )
            if result.returncode == 0:
                return deserialize(result.stdout)
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError):
            pass

        sha = resolve_git_ref(since, root=self.root)
        if sha is None:
            return None

        cache_path = Path(self.root) / ".pygraph" / f"ref-{sha}.json"
        if cache_path.exists():
            try:
                return read_graph(cache_path)
            except (ValueError, OSError):
                pass

        print(f"no graph at ref {since}, building from source...")
        try:
            graph = build_graph_from_ref(since, self.root)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            write_graph(graph, cache_path)
            return graph
        except (ValueError, PermissionError, OSError, FileNotFoundError):
            return None

    def _symbol_key(self, sym: SymbolNode) -> tuple[str, str | None]:
        return (sym.name, sym.receiver)

    def get_changes(
        self, since: str = "HEAD"
    ) -> dict[str, list[dict[str, Any]]]:
        old_graph = self._load_git_graph(since)
        if old_graph is None:
            return {
                "error": [
                    {
                        "message": (
                            f"Could not load graph at '{since}'. "
                            f"Run `pygraph build` at the target ref first so "
                            f".pygraph/graph.json exists in that commit."
                        )
                    }
                ]
            }

        old_syms: dict[tuple[str, str | None], SymbolNode] = {}
        for s in old_graph.symbols:
            old_syms[self._symbol_key(s)] = s

        new_syms: dict[tuple[str, str | None], SymbolNode] = {}
        for s in self.graph.symbols:
            new_syms[self._symbol_key(s)] = s

        old_keys = set(old_syms)
        new_keys = set(new_syms)

        added_keys = new_keys - old_keys
        removed_keys = old_keys - new_keys
        common_keys = old_keys & new_keys

        added = [self._sym_diff_dict(new_syms[k]) for k in added_keys]
        removed = [self._sym_diff_dict(old_syms[k]) for k in removed_keys]

        changed: list[dict[str, Any]] = []
        for k in common_keys:
            old_s = old_syms[k]
            new_s = new_syms[k]
            if (
                old_s.signature != new_s.signature
                or old_s.complexity != new_s.complexity
                or old_s.is_exported != new_s.is_exported
                or old_s.file != new_s.file
                or old_s.doc != new_s.doc
            ):
                changed.append({
                    "name": k[0],
                    "receiver": k[1],
                    "old_file": old_s.file,
                    "new_file": new_s.file,
                    "old_signature": old_s.signature,
                    "new_signature": new_s.signature,
                    "old_complexity": old_s.complexity,
                    "new_complexity": new_s.complexity,
                    "old_exported": old_s.is_exported,
                    "new_exported": new_s.is_exported,
                })

        old_call_set = {
            (c.caller_name, c.callee_raw) for c in old_graph.calls
        }
        new_call_set = {
            (c.caller_name, c.callee_raw) for c in self.graph.calls
        }

        added_calls = [
            {"caller": c, "callee": cal}
            for c, cal in (new_call_set - old_call_set)
        ]
        removed_calls = [
            {"caller": c, "callee": cal}
            for c, cal in (old_call_set - new_call_set)
        ]

        return {
            "added_symbols": added,
            "removed_symbols": removed,
            "changed_symbols": changed,
            "added_calls": added_calls,
            "removed_calls": removed_calls,
        }

    def _sym_diff_dict(self, sym: SymbolNode) -> dict[str, Any]:
        return {
            "name": sym.name,
            "receiver": sym.receiver,
            "kind": sym.kind,
            "file": sym.file,
            "line": sym.line,
            "signature": sym.signature,
            "complexity": sym.complexity,
            "is_exported": sym.is_exported,
        }

    def get_stale(self, days: int = 30) -> list[dict[str, Any]]:
        cutoff = time.time() - (days * 86400)
        stale: list[dict[str, Any]] = []

        for fnode in self.graph.files:
            full_path = Path(self.root) / fnode.path
            try:
                mtime = full_path.stat().st_mtime
            except OSError:
                continue
            if mtime < cutoff:
                file_syms = [
                    self._sym_diff_dict(s)
                    for s in self.graph.symbols
                    if s.file == fnode.path
                ]
                stale.append({
                    "file": fnode.path,
                    "mtime": mtime,
                    "days_since_modification": int((time.time() - mtime) / 86400),
                    "symbols": file_syms,
                })

        stale.sort(key=lambda x: x["days_since_modification"], reverse=True)
        return stale

    def get_graph_report(self) -> dict[str, Any]:
        syms = self.graph.symbols
        kinds: dict[str, int] = {}
        for s in syms:
            kinds[s.kind] = kinds.get(s.kind, 0) + 1

        exported = sum(1 for s in syms if s.is_exported)
        total_files = len(self.graph.files)
        total_calls = len(self.graph.calls)
        total_routes = len(self.graph.routes)
        total_deps = len(self.graph.dependencies)
        total_tests = len(self.graph.test_edges)

        hotspots = self.get_hotspots(10)
        coupling_ranked = self.get_coupling()[:10]

        return {
            "summary": {
                "total_symbols": len(syms),
                "exported": exported,
                "files": total_files,
                "calls": total_calls,
                "routes": total_routes,
                "dependencies": total_deps,
                "tests": total_tests,
            },
            "symbols_by_kind": kinds,
            "hotspots": hotspots,
            "coupling": coupling_ranked,
        }

    def get_plan(self, since: str = "HEAD") -> dict[str, Any]:
        changes = self.get_changes(since)

        if "error" in changes:
            return {"error": changes["error"]}

        all_changed_names: set[str] = set()
        for s in changes.get("added_symbols", []):
            all_changed_names.add(s["name"])
        for s in changes.get("removed_symbols", []):
            all_changed_names.add(s["name"])
        for s in changes.get("changed_symbols", []):
            all_changed_names.add(s["name"])

        affected_tests: list[dict[str, Any]] = []
        test_targets = {te.target for te in self.graph.test_edges}
        for name in all_changed_names:
            if name in test_targets:
                for te in self.graph.test_edges:
                    if te.target == name:
                        affected_tests.append({
                            "test_func": te.test_func,
                            "target": te.target,
                            "file": te.file,
                            "line": te.line,
                        })

        changed_files: set[str] = set()
        for s in changes.get("added_symbols", []):
            changed_files.add(s.get("file", ""))
        for s in changes.get("removed_symbols", []):
            changed_files.add(s.get("file", ""))
        for s in changes.get("changed_symbols", []):
            changed_files.add(s.get("new_file", ""))
            changed_files.add(s.get("old_file", ""))
        changed_files.discard("")

        changed_modules: set[str] = set()
        for f in changed_files:
            parts = f.split("/")
            if len(parts) >= 2:
                changed_modules.add(parts[0])

        risk_items: list[dict[str, Any]] = []
        for s in changes.get("changed_symbols", []):
            new_cplx = s.get("new_complexity") or 1
            coupling = 0
            for call in self.graph.calls:
                if call.caller_name == s["name"]:
                    coupling += 1
            score = new_cplx * max(coupling, 1)
            risk_items.append({
                "name": s["name"],
                "complexity": new_cplx,
                "coupling": coupling,
                "score": score,
            })
        for s in changes.get("added_symbols", []):
            cplx = s.get("complexity") or 1
            coupling = 0
            for call in self.graph.calls:
                if call.caller_name == s["name"]:
                    coupling += 1
            score = cplx * max(coupling, 1)
            risk_items.append({
                "name": s["name"],
                "complexity": cplx,
                "coupling": coupling,
                "score": score,
            })
        risk_items.sort(key=lambda x: x["score"], reverse=True)

        total_risk = sum(r["score"] for r in risk_items)

        return {
            "summary": {
                "files_changed": sorted(changed_files),
                "modules_changed": sorted(changed_modules),
                "symbols_added": len(changes.get("added_symbols", [])),
                "symbols_removed": len(changes.get("removed_symbols", [])),
                "symbols_changed": len(changes.get("changed_symbols", [])),
                "total_risk_score": total_risk,
            },
            "changes": changes,
            "affected_tests": affected_tests,
            "risk_items": risk_items,
        }
