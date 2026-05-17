import typer

app = typer.Typer()


@app.command()
def build(root: str = ".") -> None:
    """Index project into .pygraph/graph.json + GRAPH_REPORT.md"""
    ...


@app.command()
def query(pattern: str) -> None:
    """Search symbols by pattern"""
    ...
