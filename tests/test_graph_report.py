from __future__ import annotations

import pytest

from pygraph.graph.types import (
    make_call_edge,
    make_dependency,
    make_file_node,
    make_graph,
    make_package_node,
    make_symbol_node,
)
from pygraph.query import GraphQuery
from pygraph.server import set_query_override


@pytest.fixture
def report_query() -> GraphQuery:
    g = make_graph(project_root="/test")
    pkg = make_package_node(name="sample", dir=".")
    g.packages = [pkg]
    g.files = [
        make_file_node(path="app.py", package_name="sample", lines=10),
        make_file_node(path="utils.py", package_name="sample", lines=5),
    ]
    g.symbols = [
        make_symbol_node(
            id="app.py::run", name="run", kind="function",
            file="app.py", line=1, is_exported=True, complexity=3,
        ),
        make_symbol_node(
            id="app.py::APP_NAME", name="APP_NAME", kind="constant",
            file="app.py", line=5, is_exported=True,
        ),
        make_symbol_node(
            id="utils.py::load", name="load", kind="function",
            file="utils.py", line=1, is_exported=True, complexity=2,
        ),
    ]
    g.calls = [
        make_call_edge(
            caller_symbol_id="app.py::run", caller_name="run",
            callee_raw="load", file="app.py", line=2,
        ),
    ]
    g.routes = [
        type("HTTPRoute", (), {"method": "GET", "path": "/", "handler": "run",
                               "file": "app.py", "line": 1})(),
    ]
    g.dependencies = [make_dependency(module="flask", version="3.0")]
    g.test_edges = [
        type("TestEdge", (), {"test_func": "test_run", "target": "run",
                              "file": "test_app.py", "line": 1})(),
    ]
    return GraphQuery(g, root="/test")


class TestGetGraphReport:
    def test_report_has_summary(self, report_query: GraphQuery) -> None:
        report = report_query.get_graph_report()
        assert "summary" in report
        s = report["summary"]
        assert s["total_symbols"] == 3
        assert s["exported"] == 3
        assert s["files"] == 2
        assert s["calls"] == 1
        assert s["routes"] == 1
        assert s["dependencies"] == 1
        assert s["tests"] == 1

    def test_symbols_by_kind(self, report_query: GraphQuery) -> None:
        report = report_query.get_graph_report()
        kinds = report["symbols_by_kind"]
        assert kinds.get("function") == 2
        assert kinds.get("constant") == 1


class TestGraphReportCommand:
    def test_run_output(
        self, report_query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.graph_report import run
        run(report_query)
        captured = capsys.readouterr()
        assert "Graph Report" in captured.out
        assert "Symbols" in captured.out
        assert "Hotspots" in captured.out


class TestMCPGraphReport:
    def test_graph_report_tool(
        self, report_query: GraphQuery
    ) -> None:
        set_query_override(report_query)
        try:
            from pygraph.server import graph_report as tool_fn
            result = tool_fn()
            assert isinstance(result, str)
            assert "Graph Report" in result
        finally:
            set_query_override(None)
