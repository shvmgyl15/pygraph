from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from pygraph.builder import build_and_write
from pygraph.graph.serialize import read_graph
from pygraph.graph.types import SymbolNode
from pygraph.query import GraphQuery

server = FastMCP(
    "pygraph",
    instructions="Query a Python/Flask codebase using pygraph's AST index.",
)

_query_override: GraphQuery | None = None


def set_query_override(query: GraphQuery | None) -> None:
    global _query_override
    _query_override = query


def create_query(root: str) -> GraphQuery:
    if _query_override is not None:
        return _query_override
    graph_path = Path(root) / ".pygraph" / "graph.json"
    if not graph_path.exists():
        raise FileNotFoundError(
            f"Graph not found at {graph_path}. Run `pygraph build` first."
        )
    graph = read_graph(graph_path)
    return GraphQuery(graph, root=root)


def _symbol_to_dict(sym: SymbolNode) -> dict[str, Any]:
    return {
        "id": sym.id,
        "kind": sym.kind,
        "name": sym.name,
        "receiver": sym.receiver,
        "package_name": sym.package_name,
        "file": sym.file,
        "line": sym.line,
        "end_line": sym.end_line,
        "doc": sym.doc,
        "signature": sym.signature,
        "is_exported": sym.is_exported,
        "is_async": sym.is_async,
        "is_generator": sym.is_generator,
        "decorators": sym.decorators,
        "bases": sym.bases,
        "type_annotation": sym.type_annotation,
        "arity": sym.arity,
        "complexity": sym.complexity,
    }


@server.tool()
def build_graph(root: str = ".") -> dict[str, str]:
    """Index project into .pygraph/graph.json"""
    out_path = build_and_write(root)
    return {"status": "ok", "path": str(out_path)}


@server.tool()
def callers(name: str, root: str = ".") -> list[dict[str, Any]]:
    """Show who calls the given symbol"""
    query = create_query(root)
    return [
        {
            "caller": cs.name,
            "file": ce.file,
            "line": ce.line,
            "callee_raw": ce.callee_raw,
        }
        for cs, ce in query.get_callers(name)
    ]


@server.tool()
def callees(name: str, root: str = ".") -> list[dict[str, Any]]:
    """Show what the given symbol calls"""
    query = create_query(root)
    return [
        {
            "callee": cs.name if cs else ce.callee_raw,
            "file": ce.file,
            "line": ce.line,
            "callee_raw": ce.callee_raw,
        }
        for cs, ce in query.get_callees(name)
    ]


@server.tool()
def node(name: str, root: str = ".") -> dict[str, Any] | dict[str, str]:
    """Show details of a symbol"""
    query = create_query(root)
    sym = query.get_symbol(name)
    if not sym:
        return {"error": f"Symbol '{name}' not found"}
    return _symbol_to_dict(sym)


@server.tool()
def source(file_path: str, root: str = ".") -> dict[str, Any]:
    """Show source code of a file"""
    query = create_query(root)
    src = query.get_source(file_path)
    if src is None:
        return {"error": f"File '{file_path}' not found", "source": None}
    return {"file": file_path, "source": src}


@server.tool()
def query(pattern: str, root: str = ".") -> list[dict[str, Any]]:
    """Search symbols by pattern (regex or substring)"""
    q = create_query(root)
    return [_symbol_to_dict(sym) for sym in q.find_symbols(pattern)]


@server.tool()
def context(name: str, root: str = ".") -> dict[str, Any]:
    """Show symbol with callers, callees, tests, and source"""
    q = create_query(root)
    return q.get_context(name)


@server.tool()
def imports(file_path: str, root: str = ".") -> list[dict[str, Any]]:
    """Show imports of a file"""
    q = create_query(root)
    return [
        {
            "import_path": imp.import_path,
            "alias": imp.alias,
            "from_package": imp.from_package,
            "is_default": imp.is_default,
        }
        for imp in q.get_imports(file_path)
    ]


@server.tool()
def public(root: str = ".") -> list[dict[str, Any]]:
    """List all exported (public) symbols"""
    q = create_query(root)
    return [_symbol_to_dict(sym) for sym in q.get_public()]


@server.tool()
def focus(name: str, root: str = ".") -> dict[str, Any]:
    """Show JSON detail for a symbol"""
    q = create_query(root)
    sym = q.get_symbol(name)
    if not sym:
        return {"error": f"Symbol '{name}' not found"}
    callers_list = [
        {"caller": cs.name, "file": ce.file, "line": ce.line}
        for cs, ce in q.get_callers(name)
    ]
    callees_list = [
        {
            "callee": cs.name if cs else ce.callee_raw,
            "file": ce.file,
            "line": ce.line,
        }
        for cs, ce in q.get_callees(name)
    ]
    return {
        "name": sym.name,
        "kind": sym.kind,
        "file": sym.file,
        "line": sym.line,
        "end_line": sym.end_line,
        "exported": sym.is_exported,
        "callers": callers_list,
        "callees": callees_list,
    }


@server.tool()
def impact(name: str, root: str = ".") -> list[dict[str, Any]]:
    """Show downstream impact (BFS from symbol)"""
    q = create_query(root)
    return q.get_impact(name)


@server.tool()
def path(
    from_name: str, to_name: str, root: str = "."
) -> dict[str, Any] | list[dict[str, Any]]:
    """Show shortest call path between two symbols"""
    q = create_query(root)
    result = q.get_path(from_name, to_name)
    if result is None:
        return {"error": f"No path from '{from_name}' to '{to_name}'"}
    return result


@server.tool()
def orphans(root: str = ".") -> list[dict[str, Any]]:
    """List uncalled private symbols"""
    q = create_query(root)
    return [_symbol_to_dict(sym) for sym in q.get_orphans()]


@server.tool()
def trace(message: str, root: str = ".") -> list[dict[str, Any]]:
    """Find error messages and trace their call paths"""
    q = create_query(root)
    results = q.get_errorflow(message)
    if not results:
        plain = q.get_trace(message)
        return [
            {
                "message": r["message"],
                "function": r["function"],
                "file": r["file"],
                "line": r["line"],
            }
            for r in plain
        ]
    return [
        {
            "error": {
                "message": item["error"].message,
                "function": item["error"].function_name,
                "file": item["error"].file,
                "line": item["error"].line,
            },
            "trace": item["trace"],
        }
        for item in results
    ]


@server.tool()
def complexity(
    name: str | None = None, root: str = "."
) -> list[dict[str, Any]]:
    """Show McCabe cyclomatic complexity"""
    q = create_query(root)
    return q.get_complexity(name)


@server.tool()
def coupling(
    name: str | None = None, root: str = "."
) -> list[dict[str, Any]]:
    """Show afferent/efferent coupling metrics"""
    q = create_query(root)
    return q.get_coupling(name)


@server.tool()
def hotspots(top: int = 10, root: str = ".") -> list[dict[str, Any]]:
    """Show high-risk symbols (complexity x coupling)"""
    q = create_query(root)
    return q.get_hotspots(top)


@server.tool()
def deps(root: str = ".") -> list[dict[str, Any]]:
    """List external dependencies"""
    q = create_query(root)
    return q.get_deps()


@server.tool()
def boundaries(
    config: str = "", root: str = "."
) -> list[dict[str, Any]]:
    """Check architecture boundary violations"""
    q = create_query(root)
    return q.get_boundary_violations(config)


@server.tool()
def changes(
    since: str = "HEAD", root: str = "."
) -> dict[str, Any]:
    """Show symbol changes since a git ref"""
    q = create_query(root)
    return q.get_changes(since)


@server.tool()
def stale(days: int = 30, root: str = ".") -> list[dict[str, Any]]:
    """List files not modified in N days with their symbols"""
    q = create_query(root)
    return q.get_stale(days)


@server.tool()
def plan(
    since: str = "HEAD", root: str = "."
) -> dict[str, Any]:
    """Generate a change plan report"""
    q = create_query(root)
    return q.get_plan(since)


@server.tool()
def review(
    since: str = "HEAD", root: str = "."
) -> str:
    """Generate a Markdown code review report"""
    q = create_query(root)
    plan_data = q.get_plan(since)
    if "error" in plan_data:
        return str(plan_data["error"][0]["message"])

    lines: list[str] = []
    lines.append("# Code Review Report\n")
    s = plan_data["summary"]
    lines.append(f"**Scope:** {len(s['files_changed'])} files across "
                 f"{len(s['modules_changed'])} modules\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Symbols added | {s['symbols_added']} |")
    lines.append(f"| Symbols removed | {s['symbols_removed']} |")
    lines.append(f"| Symbols changed | {s['symbols_changed']} |")
    lines.append(f"| Files touched | {len(s['files_changed'])} |")
    lines.append(f"| Risk score | {s['total_risk_score']} |\n")

    changes = plan_data["changes"]
    if changes.get("added_symbols"):
        lines.append("## Added Symbols\n")
        for sym in changes["added_symbols"]:
            lines.append(f"- `{sym['name']}` ({sym['kind']}) — "
                         f"`{sym['file']}:{sym['line']}`")

    if changes.get("removed_symbols"):
        lines.append("\n## Removed Symbols\n")
        for sym in changes["removed_symbols"]:
            lines.append(f"- `{sym['name']}` ({sym['kind']}) — "
                         f"was `{sym['file']}:{sym['line']}`")

    if changes.get("changed_symbols"):
        lines.append("\n## Changed Symbols\n")
        for sym in changes["changed_symbols"]:
            lines.append(f"- `{sym['name']}`")
            if sym.get("old_signature") != sym.get("new_signature"):
                lines.append(f"  - Signature: `{sym['old_signature']}` → "
                             f"`{sym['new_signature']}`")
            if sym.get("old_complexity") != sym.get("new_complexity"):
                lines.append(f"  - Complexity: {sym['old_complexity']} → "
                             f"{sym['new_complexity']}")

    if plan_data.get("affected_tests"):
        lines.append("\n## Related Tests\n")
        for t in plan_data["affected_tests"]:
            lines.append(f"- `{t['test_func']}` tests `{t['target']}`")

    if plan_data.get("risk_items"):
        lines.append("\n## Risk Assessment\n")
        lines.append("| Symbol | Score | Complexity | Coupling |")
        lines.append("|--------|-------|------------|----------|")
        for r in plan_data["risk_items"][:10]:
            lines.append(f"| {r['name']} | {r['score']} | "
                         f"{r['complexity']} | {r['coupling']} |")

    return "\n".join(lines)


@server.tool()
def add_opencode_plugin(root: str = ".") -> str:
    """Create .opencode.json with pygraph MCP config"""
    root_path = Path(root).resolve()
    config_path = root_path / ".opencode.json"

    config = {
        "$schema": "https://opencode.ai/config.json",
        "mcp_servers": {
            "pygraph": {
                "command": "uv",
                "args": ["run", "pygraph", "mcp", "--root", str(root_path)],
                "env": {},
            },
        },
        "agents": {
            "architect": {
                "model": "opencode-go/deepseek-v4-flash",
                "instructions": [
                    "Use pygraph MCP tools to query the code graph.",
                    "Check architecture boundaries before suggesting changes.",
                ],
            },
        },
    }

    config_path.write_text(json.dumps(config, indent=2))
    return f"Created {config_path}"


@server.tool()
def graph_report(root: str = ".") -> str:
    """Generate a Markdown report about the codebase graph"""
    q = create_query(root)
    report = q.get_graph_report()
    s = report["summary"]

    lines: list[str] = []
    lines.append("# Graph Report\n")
    lines.append("## Overview\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Symbols | {s['total_symbols']} |")
    lines.append(f"| Exported | {s['exported']} |")
    lines.append(f"| Files | {s['files']} |")
    lines.append(f"| Call edges | {s['calls']} |")
    lines.append(f"| Routes | {s['routes']} |")
    lines.append(f"| Dependencies | {s['dependencies']} |")
    lines.append(f"| Test edges | {s['tests']} |\n")

    kinds = report["symbols_by_kind"]
    if kinds:
        lines.append("## Symbols by Kind\n")
        lines.append("| Kind | Count |")
        lines.append("|------|-------|")
        for kind in sorted(kinds):
            lines.append(f"| {kind} | {kinds[kind]} |")

    if report["hotspots"]:
        lines.append("\n## Hotspots (Top 10)\n")
        lines.append("| Score | Complexity | Coupling | Name | File |")
        lines.append("|-------|------------|----------|------|------|")
        for h in report["hotspots"]:
            lines.append(f"| {h['score']} | {h['complexity']} | "
                         f"{h['coupling']} | {h['name']} | {h['file']} |")

    return "\n".join(lines)


def run_server(root: str = ".") -> None:
    """Start the MCP stdio server."""
    server.run(transport="stdio")
