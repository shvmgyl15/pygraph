import typer

from pygraph.builder import build_and_write

app = typer.Typer()


@app.command()
def build(root: str = ".") -> None:
    """Index project into .pygraph/graph.json + GRAPH_REPORT.md"""
    out_path = build_and_write(root)
    typer.echo(f"Built {out_path}")


@app.command()
def query(pattern: str) -> None:
    """Search symbols by pattern"""
    ...
