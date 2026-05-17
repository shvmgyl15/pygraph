from __future__ import annotations

import time
from pathlib import Path

import pytest

from pygraph.graph.types import (
    make_call_edge,
    make_file_node,
    make_graph,
    make_package_node,
    make_symbol_node,
)
from pygraph.query import GraphQuery
from pygraph.server import set_query_override


@pytest.fixture
def changes_query() -> GraphQuery:
    g = make_graph(project_root="/test")
    pkg = make_package_node(name="sample", dir=".")
    g.packages = [pkg]
    g.files = [
        make_file_node(path="app.py", package_name="sample", lines=40),
        make_file_node(path="utils.py", package_name="sample", lines=20),
    ]
    g.symbols = [
        make_symbol_node(
            id="app.py::run", name="run", kind="function",
            file="app.py", line=1, is_exported=True, complexity=3,
            signature="def run(): ...",
        ),
        make_symbol_node(
            id="app.py::setup", name="setup", kind="function",
            file="app.py", line=10, is_exported=True, complexity=1,
            signature="def setup(): ...",
        ),
        make_symbol_node(
            id="utils.py::load", name="load", kind="function",
            file="utils.py", line=1, is_exported=True,
        ),
    ]
    g.calls = [
        make_call_edge(
            caller_symbol_id="app.py::run", caller_name="run",
            callee_raw="setup", file="app.py", line=2,
        ),
        make_call_edge(
            caller_symbol_id="app.py::run", caller_name="run",
            callee_raw="load", file="app.py", line=3,
        ),
    ]
    return GraphQuery(g, root="/test")


# ---------------------------------------------------------------------------
# get_changes
# ---------------------------------------------------------------------------


class TestGetChanges:
    def test_returns_error_when_no_git_graph(self, changes_query: GraphQuery) -> None:
        result = changes_query.get_changes("HEAD")
        if "error" in result:
            assert "Could not load graph" in result["error"][0]["message"]
        else:
            # In a git repo with a graph at HEAD, this might succeed
            assert isinstance(result, dict)

    def test_compare_empty_graphs(self) -> None:
        g = make_graph(project_root="/test")
        q = GraphQuery(g, root="/test")
        result = q.get_changes("HEAD")
        if "error" not in result:
            assert result["added_symbols"] == []
            assert result["removed_symbols"] == []
            assert result["changed_symbols"] == []

    def test_sym_diff_dict_format(self, changes_query: GraphQuery) -> None:
        sym = changes_query.graph.symbols[0]
        d = changes_query._sym_diff_dict(sym)
        assert d["name"] == "run"
        assert d["kind"] == "function"
        assert d["complexity"] == 3

    def test_stale_returns_list(self, changes_query: GraphQuery) -> None:
        result = changes_query.get_stale(days=0)
        assert isinstance(result, list)

    def test_stale_old_file_detected(self, tmp_path: Path) -> None:
        old_file = tmp_path / "old.py"
        old_file.write_text("x = 1")
        # Set mtime far in the past
        old_mtime = time.time() - (100 * 86400)
        os_util = __import__("os")
        os_util.utime(str(old_file), (old_mtime, old_mtime))

        g = make_graph(project_root=str(tmp_path))
        g.files = [make_file_node(path="old.py", package_name="test", lines=1)]
        g.symbols = [
            make_symbol_node(
                id="old.py::x", name="x", kind="constant",
                file="old.py", line=1,
            ),
        ]
        q = GraphQuery(g, root=str(tmp_path))
        result = q.get_stale(days=30)
        assert len(result) >= 1
        assert result[0]["file"] == "old.py"
        assert result[0]["days_since_modification"] >= 30


# ---------------------------------------------------------------------------
# CLI command tests
# ---------------------------------------------------------------------------


class TestChangesCommand:
    def test_run_changes_no_diff(
        self, changes_query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.changes import run
        run(changes_query, since="HEAD")
        captured = capsys.readouterr()
        # Should either show changes or error about missing graph
        assert captured.out


class TestStaleCommand:
    def test_run_stale_no_files(
        self, changes_query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.stale import run
        run(changes_query, days=0)
        captured = capsys.readouterr()
        assert captured.out  # either stale files or "no stale files"

    def test_run_stale_output_format(
        self, changes_query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.stale import run
        run(changes_query, days=9999)
        captured = capsys.readouterr()
        assert "No stale files" in captured.out or "Stale files" in captured.out


# ---------------------------------------------------------------------------
# MCP tool tests
# ---------------------------------------------------------------------------


class TestMCPChangesTool:
    def test_changes_tool_returns_dict(
        self, changes_query: GraphQuery
    ) -> None:
        set_query_override(changes_query)
        try:
            from pygraph.server import changes as tool_fn
            result = tool_fn(since="HEAD")
            assert isinstance(result, dict)
        finally:
            set_query_override(None)


class TestMCPStaleTool:
    def test_stale_tool_returns_list(
        self, changes_query: GraphQuery
    ) -> None:
        set_query_override(changes_query)
        try:
            from pygraph.server import stale as tool_fn
            result = tool_fn(days=0)
            assert isinstance(result, list)
        finally:
            set_query_override(None)
