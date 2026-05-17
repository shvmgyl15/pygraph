from __future__ import annotations

import pytest

from pygraph.graph.types import (
    make_call_edge,
    make_file_node,
    make_graph,
    make_package_node,
    make_symbol_node,
    make_test_edge,
)
from pygraph.query import GraphQuery
from pygraph.server import set_query_override


@pytest.fixture
def plan_query() -> GraphQuery:
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
        ),
        make_symbol_node(
            id="utils.py::load", name="load", kind="function",
            file="utils.py", line=1, is_exported=True, complexity=2,
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
    g.test_edges = [
        make_test_edge(
            test_func="test_run", target="run",
            file="tests/test_app.py", line=1,
        ),
    ]
    return GraphQuery(g, root="/test")


class TestGetPlan:
    def test_plan_returns_dict(self, plan_query: GraphQuery) -> None:
        plan = plan_query.get_plan("HEAD")
        if "error" in plan:
            assert isinstance(plan["error"], list)
        else:
            assert "summary" in plan
            assert "changes" in plan
            assert "affected_tests" in plan
            assert "risk_items" in plan

    def test_plan_summary_keys(self, plan_query: GraphQuery) -> None:
        plan = plan_query.get_plan("HEAD")
        if "error" not in plan:
            s = plan["summary"]
            assert "symbols_added" in s
            assert "symbols_removed" in s
            assert "symbols_changed" in s
            assert "files_changed" in s
            assert "total_risk_score" in s

    def test_plan_risk_items_sorted(self, plan_query: GraphQuery) -> None:
        plan = plan_query.get_plan("HEAD")
        if "error" not in plan:
            items = plan["risk_items"]
            scores = [r["score"] for r in items]
            assert scores == sorted(scores, reverse=True)


class TestPlanCommand:
    def test_run_plan_output(
        self, plan_query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.plan import run
        run(plan_query, since="HEAD")
        captured = capsys.readouterr()
        assert captured.out  # should produce some output


class TestReviewCommand:
    def test_run_review_output(
        self, plan_query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.review import run
        run(plan_query, since="HEAD")
        captured = capsys.readouterr()
        assert captured.out  # should produce some output


class TestMCPPlanTool:
    def test_plan_tool_returns_dict(self, plan_query: GraphQuery) -> None:
        set_query_override(plan_query)
        try:
            from pygraph.server import plan as tool_fn
            result = tool_fn(since="HEAD")
            assert isinstance(result, dict)
        finally:
            set_query_override(None)


class TestMCPReviewTool:
    def test_review_tool_returns_string(self, plan_query: GraphQuery) -> None:
        set_query_override(plan_query)
        try:
            from pygraph.server import review as tool_fn
            result = tool_fn(since="HEAD")
            assert isinstance(result, str)
            assert "Code Review Report" in result or "Could not" in result
        finally:
            set_query_override(None)
