from __future__ import annotations

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


def run_server(root: str = ".") -> None:
    """Start the MCP stdio server."""
    server.run(transport="stdio")
