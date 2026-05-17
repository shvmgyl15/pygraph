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


@app.command()
def complexity(
    name: str | None = typer.Argument(None, help="Symbol name (omit for ranked list)"),
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """Show McCabe cyclomatic complexity"""
    query = _load_query(root)
    from pygraph.commands.complexity import run
    run(query, name)


@app.command()
def coupling(
    name: str | None = typer.Argument(None, help="Symbol name (omit for ranked list)"),
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """Show afferent/efferent coupling metrics"""
    query = _load_query(root)
    from pygraph.commands.coupling import run
    run(query, name)


@app.command()
def hotspot(
    top: int = typer.Option(10, "--top", "-n", help="Number of hotspots to show"),
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """Show high-risk symbols (complexity × coupling)"""
    query = _load_query(root)
    from pygraph.commands.hotspot import run
    run(query, top)


@app.command()
def deps(
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """List external dependencies"""
    query = _load_query(root)
    from pygraph.commands.deps import run
    run(query)


@app.command()
def boundaries(
    config: str = typer.Option(
        "", "--config", "-c", help="Path to boundaries.json"
    ),
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """Check architecture boundary violations"""
    query = _load_query(root)
    from pygraph.commands.boundaries import run
    run(query, config)


@app.command()
def changes(
    since: str = typer.Option(
        "HEAD", "--since", "-s", help="Git ref to compare against"
    ),
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """Show symbol changes since a git ref"""
    query = _load_query(root)
    from pygraph.commands.changes import run
    run(query, since)


@app.command()
def stale(
    days: int = typer.Option(
        30, "--days", "-d", help="Days threshold for staleness"
    ),
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """List files not modified in N days with their symbols"""
    query = _load_query(root)
    from pygraph.commands.stale import run
    run(query, days)


@app.command()
def plan(
    since: str = typer.Option(
        "HEAD", "--since", "-s", help="Git ref to compare against"
    ),
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """Generate a change plan report"""
    query = _load_query(root)
    from pygraph.commands.plan import run
    run(query, since)


@app.command()
def review(
    since: str = typer.Option(
        "HEAD", "--since", "-s", help="Git ref to compare against"
    ),
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """Generate a Markdown code review report"""
    query = _load_query(root)
    from pygraph.commands.review import run
    run(query, since)


@app.command()
def mcp(
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """Start MCP stdio server for AI agent integration"""
    from pygraph.server import run_server
    run_server(root)


@app.command()
def add_opencode_plugin(
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """Create .opencode.json with pygraph MCP config + architect agent"""
    query = _load_query(root)
    from pygraph.commands.opencode_plugin import run
    run(query, root)


@app.command(name="graph-report")
def graph_report(
    root: str = typer.Option(".", "--root", help="Project root directory"),
) -> None:
    """Generate a Markdown report about the codebase graph"""
    query = _load_query(root)
    from pygraph.commands.graph_report import run
    run(query)
