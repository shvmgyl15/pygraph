from __future__ import annotations

from pathlib import Path

import typer

from pygraph.builder import build_and_write
from pygraph.graph.serialize import read_graph
from pygraph.query import GraphQuery

app = typer.Typer()


def _load_query(root: str) -> GraphQuery:
    graph_path = Path(root) / ".pygraph" / "graph.json"
    if not graph_path.exists():
        typer.echo(f"Error: no graph found at {graph_path}. Run `pygraph build` first.")
        raise typer.Exit(1)
    graph = read_graph(graph_path)
    return GraphQuery(graph, root=root)


@app.command()
def build(root: str = typer.Option(".", "--root", help="Project root directory")) -> None:
    """Index project into .pygraph/graph.json"""
    out_path = build_and_write(root)
    typer.echo(f"Built {out_path}")


@app.command()
def callers(
    name: str,
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """Show who calls the given symbol"""
    query = _load_query(root)
    from pygraph.commands.callers import run
    run(query, name)


@app.command()
def callees(
    name: str,
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """Show what the given symbol calls"""
    query = _load_query(root)
    from pygraph.commands.callees import run
    run(query, name)


@app.command()
def node(
    name: str,
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """Show details of a symbol"""
    query = _load_query(root)
    from pygraph.commands.node import run
    run(query, name)


@app.command()
def source(
    file_path: str,
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """Show source code of a file"""
    query = _load_query(root)
    from pygraph.commands.source import run
    run(query, file_path)


@app.command()
def query(
    pattern: str,
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """Search symbols by pattern (regex or substring)"""
    query = _load_query(root)
    from pygraph.commands.query_cmd import run
    run(query, pattern)


@app.command()
def context(
    name: str,
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """Show symbol with callers, callees, tests, and source"""
    query = _load_query(root)
    from pygraph.commands.context import run
    run(query, name)


@app.command()
def imports(
    file_path: str,
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """Show imports of a file"""
    query = _load_query(root)
    from pygraph.commands.imports_cmd import run
    run(query, file_path)


@app.command()
def public(
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """List all exported (public) symbols"""
    query = _load_query(root)
    from pygraph.commands.public import run
    run(query)


@app.command()
def focus(
    name: str,
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """Show JSON detail for a symbol"""
    query = _load_query(root)
    from pygraph.commands.focus import run
    run(query, name)


@app.command()
def impact(
    name: str,
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """Show downstream impact (BFS from symbol)"""
    query = _load_query(root)
    from pygraph.commands.impact import run
    run(query, name)


@app.command()
def path(
    from_name: str,
    to_name: str,
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """Show shortest call path between two symbols"""
    query = _load_query(root)
    from pygraph.commands.path_cmd import run
    run(query, from_name, to_name)


@app.command()
def orphans(
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """List uncalled private symbols"""
    query = _load_query(root)
    from pygraph.commands.orphans import run
    run(query)


@app.command()
def trace(
    message: str,
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """Find error messages and trace their call paths"""
    query = _load_query(root)
    from pygraph.commands.trace import run
    run(query, message)
