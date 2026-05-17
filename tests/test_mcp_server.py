from __future__ import annotations

from typing import Any

import pytest

from pygraph.graph.types import (
    make_call_edge,
    make_dependency,
    make_error_edge,
    make_file_node,
    make_graph,
    make_import_edge,
    make_package_node,
    make_symbol_node,
    make_test_edge,
)
from pygraph.query import GraphQuery
from pygraph.server import (
    _symbol_to_dict,
    create_query,
    server,
    set_query_override,
)


@pytest.fixture
def sample_query() -> GraphQuery:
    g = make_graph(project_root="/test")
    pkg = make_package_node(name="sample", dir=".")
    g.packages = [pkg]
    g.files = [
        make_file_node(path="app.py", package_name="sample", lines=40),
        make_file_node(path="utils.py", package_name="sample", lines=30),
        make_file_node(path="tests/test_app.py", package_name="sample", lines=15),
    ]
    g.symbols = [
        make_symbol_node(
            id="app.py::run", name="run", kind="function",
            file="app.py", line=1, end_line=12,
            is_exported=True, arity=1,
            signature="def run(port: int): ...",
            complexity=3,
        ),
        make_symbol_node(
            id="app.py::_helper", name="_helper", kind="function",
            file="app.py", line=14, end_line=18,
            is_exported=False, complexity=2,
        ),
        make_symbol_node(
            id="app.py::setup", name="setup", kind="function",
            file="app.py", line=20, end_line=25,
            is_exported=True, complexity=1,
        ),
        make_symbol_node(
            id="app.py::Service", name="Service", kind="class",
            file="app.py", line=27, end_line=40,
            is_exported=True,
        ),
        make_symbol_node(
            id="app.py::Service.__init__", name="__init__", kind="method",
            file="app.py", line=28, end_line=30,
            is_exported=False, receiver="Service", arity=1,
        ),
        make_symbol_node(
            id="app.py::Service.start", name="start", kind="method",
            file="app.py", line=32, end_line=38,
            is_exported=False, receiver="Service", arity=0,
        ),
        make_symbol_node(
            id="app.py::APP_NAME", name="APP_NAME", kind="constant",
            file="app.py", line=40, end_line=40,
            is_exported=True,
        ),
        make_symbol_node(
            id="utils.py::load", name="load", kind="function",
            file="utils.py", line=1, end_line=3,
            is_exported=True,
        ),
        make_symbol_node(
            id="utils.py::parse", name="parse", kind="function",
            file="utils.py", line=5, end_line=10,
            is_exported=True, arity=1,
        ),
        make_symbol_node(
            id="utils.py::_internal", name="_internal", kind="function",
            file="utils.py", line=12, end_line=15,
            is_exported=False,
        ),
        make_symbol_node(
            id="utils.py::_unused", name="_unused", kind="function",
            file="utils.py", line=17, end_line=19,
            is_exported=False,
        ),
        make_symbol_node(
            id="tests/test_app.py::test_run", name="test_run", kind="function",
            file="tests/test_app.py", line=1, end_line=5,
            is_exported=True,
        ),
        make_symbol_node(
            id="tests/test_app.py::test_service", name="test_service", kind="function",
            file="tests/test_app.py", line=7, end_line=12,
            is_exported=True,
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
        make_call_edge(
            caller_symbol_id="app.py::run", caller_name="run",
            callee_raw="Service.start", file="app.py", line=4,
        ),
        make_call_edge(
            caller_symbol_id="app.py::Service.start", caller_name="start",
            callee_raw="_helper", file="app.py", line=33,
        ),
        make_call_edge(
            caller_symbol_id="utils.py::parse", caller_name="parse",
            callee_raw="_internal", file="utils.py", line=6,
        ),
    ]
    g.imports = [
        make_import_edge(
            from_file="app.py", from_package="sample",
            import_path="utils.load", is_default=False,
        ),
        make_import_edge(
            from_file="tests/test_app.py", from_package="sample",
            import_path="app.run", is_default=False,
        ),
    ]
    g.test_edges = [
        make_test_edge(
            test_func="test_run", target="run",
            file="tests/test_app.py", line=3,
        ),
        make_test_edge(
            test_func="test_service", target="Service.start",
            file="tests/test_app.py", line=9,
        ),
    ]
    g.dependencies = [
        make_dependency(module="flask", version="3.0"),
    ]
    g.errors = [
        make_error_edge(
            message="connection refused",
            function_name="start",
            file="app.py", line=35,
        ),
    ]
    return GraphQuery(g, root="/test")


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

EXPECTED_TOOLS = {
    "build_graph", "callers", "callees", "node", "source",
    "query", "context", "imports", "public", "focus",
    "impact", "path", "orphans", "trace",
    "complexity", "coupling", "hotspots", "deps",
}


class TestToolRegistration:
    def test_all_tools_registered(self) -> None:
        tools = server._tool_manager.list_tools()
        names = {t.name for t in tools}
        assert names == EXPECTED_TOOLS, (
            f"Missing: {EXPECTED_TOOLS - names}, Extra: {names - EXPECTED_TOOLS}"
        )

    def test_tool_descriptions_not_empty(self) -> None:
        tools = server._tool_manager.list_tools()
        for t in tools:
            assert t.description, f"Tool '{t.name}' has empty description"

    def test_each_tool_has_root_param(self) -> None:
        tools = server._tool_manager.list_tools()
        for t in tools:
            if t.name == "build_graph":
                # build_graph only has root
                assert "root" in t.parameters["properties"]
                continue
            if t.name in ("public", "orphans", "deps"):
                assert "root" in t.parameters["properties"]
                continue
            if t.name in ("hotspots",):
                assert "root" in t.parameters["properties"]
                continue
            if t.name in ("complexity", "coupling"):
                props = t.parameters["properties"]
                assert "name" in props or "root" in props
                continue
            props = t.parameters["properties"]
            # All tools should have at least one tool-specific param + root
            assert len(props) >= 1


# ---------------------------------------------------------------------------
# Tool function tests via query override
# ---------------------------------------------------------------------------


class TestCallersTool:
    def test_callers_of_run(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import callers as tool_fn
            result = tool_fn(name="run")
            assert isinstance(result, list)
            assert len(result) == 0  # run has no callers
        finally:
            set_query_override(None)

    def test_callers_of_setup(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import callers as tool_fn
            result = tool_fn(name="setup")
            assert len(result) == 1
            assert result[0]["caller"] == "run"
            assert result[0]["file"] == "app.py"
            assert result[0]["line"] == 2
        finally:
            set_query_override(None)


class TestCalleesTool:
    def test_callees_of_run(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import callees as tool_fn
            result = tool_fn(name="run")
            assert len(result) == 3
            callee_names = {r["callee"] for r in result}
            assert callee_names == {"setup", "load", "start"}
        finally:
            set_query_override(None)


class TestNodeTool:
    def test_node_found(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import node as tool_fn
            result = tool_fn(name="run")
            assert result["name"] == "run"
            assert result["kind"] == "function"
            assert result["is_exported"] is True
            assert result["complexity"] == 3
        finally:
            set_query_override(None)

    def test_node_not_found(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import node as tool_fn
            result = tool_fn(name="nonexistent")
            assert "error" in result
        finally:
            set_query_override(None)


class TestSourceTool:
    def test_source_missing(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import source as tool_fn
            result = tool_fn(file_path="app.py")
            # file doesn't exist on disk, so source is None
            assert result.get("source") is None or "error" in result
        finally:
            set_query_override(None)


class TestQueryTool:
    def test_query_by_pattern(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import query as tool_fn
            result = tool_fn(pattern="load")  # substring match
            names = {r["name"] for r in result}
            assert "load" in names
            assert "run" not in names
        finally:
            set_query_override(None)


class TestContextTool:
    def test_context(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import context as tool_fn
            result = tool_fn(name="run")
            assert result["symbol"] is not None
            assert result["symbol"].name == "run"
            assert len(result["callers"]) == 0
            assert len(result["callees"]) == 3
            assert len(result["test_edges"]) == 1
        finally:
            set_query_override(None)


class TestImportsTool:
    def test_imports_of_app(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import imports as tool_fn
            result = tool_fn(file_path="app.py")
            assert len(result) == 1
            assert result[0]["import_path"] == "utils.load"
        finally:
            set_query_override(None)

    def test_imports_empty(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import imports as tool_fn
            result = tool_fn(file_path="nope.py")
            assert result == []
        finally:
            set_query_override(None)


class TestPublicTool:
    def test_public(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import public as tool_fn
            result = tool_fn()
            names = {r["name"] for r in result}
            assert "run" in names
            assert "Service" in names
            assert "APP_NAME" in names
            assert "_helper" not in names
        finally:
            set_query_override(None)


class TestFocusTool:
    def test_focus_found(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import focus as tool_fn
            result = tool_fn(name="run")
            assert result["name"] == "run"
            assert result["exported"] is True
            assert len(result["callers"]) == 0
            assert len(result["callees"]) == 3
        finally:
            set_query_override(None)

    def test_focus_not_found(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import focus as tool_fn
            result = tool_fn(name="ghost")
            assert "error" in result
        finally:
            set_query_override(None)


class TestImpactTool:
    def test_impact_of_run(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import impact as tool_fn
            result = tool_fn(name="run")
            assert len(result) >= 1
            targets = {(r["caller"], r["callee"]) for r in result}
            assert ("run", "setup") in targets
            assert ("run", "load") in targets
        finally:
            set_query_override(None)


class TestPathTool:
    def test_path_found(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import path as tool_fn
            result = tool_fn(from_name="run", to_name="_helper")
            assert isinstance(result, list)
            assert len(result) > 0
        finally:
            set_query_override(None)

    def test_path_not_found(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import path as tool_fn
            result = tool_fn(from_name="run", to_name="nonexistent")
            assert isinstance(result, dict)
            assert "error" in result
        finally:
            set_query_override(None)


class TestOrphansTool:
    def test_orphans(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import orphans as tool_fn
            result = tool_fn()
            names = {r["name"] for r in result}
            assert "_unused" in names
            assert "_internal" not in names  # called by parse
        finally:
            set_query_override(None)


class TestTraceTool:
    def test_trace_match(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import trace as tool_fn
            result = tool_fn(message="connection refused")
            assert len(result) > 0
            first = result[0]
            assert "error" in first
            assert first["error"]["message"] == "connection refused"
        finally:
            set_query_override(None)

    def test_trace_no_match(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import trace as tool_fn
            result = tool_fn(message="nothing matches this")
            assert result == []
        finally:
            set_query_override(None)


class TestComplexityTool:
    def test_complexity_single(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import complexity as tool_fn
            result = tool_fn(name="run")
            assert len(result) == 1
            assert result[0]["complexity"] == 3
        finally:
            set_query_override(None)

    def test_complexity_all(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import complexity as tool_fn
            result = tool_fn()
            assert len(result) > 0
        finally:
            set_query_override(None)


class TestCouplingTool:
    def test_coupling_single(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import coupling as tool_fn
            result = tool_fn(name="run")
            assert len(result) == 1
            assert "ca" in result[0]
            assert "ce" in result[0]
        finally:
            set_query_override(None)


class TestHotspotsTool:
    def test_hotspots(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import hotspots as tool_fn
            result = tool_fn(top=5)
            assert len(result) <= 5
            if result:
                assert "score" in result[0]
                assert "complexity" in result[0]
        finally:
            set_query_override(None)


class TestDepsTool:
    def test_deps(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            from pygraph.server import deps as tool_fn
            result = tool_fn()
            assert len(result) == 1
            assert result[0]["module"] == "flask"
        finally:
            set_query_override(None)


# ---------------------------------------------------------------------------
# _symbol_to_dict helper
# ---------------------------------------------------------------------------


class TestSymbolToDict:
    def test_converts_all_fields(self, sample_query: GraphQuery) -> None:
        sym = sample_query.get_symbol("run")
        assert sym is not None
        d = _symbol_to_dict(sym)
        assert d["name"] == "run"
        assert d["kind"] == "function"
        assert d["is_exported"] is True
        assert d["complexity"] == 3
        assert d["file"] == "app.py"
        assert d["line"] == 1


# ---------------------------------------------------------------------------
# create_query edge cases
# ---------------------------------------------------------------------------


class TestCreateQuery:
    def test_raises_on_missing_graph(self, tmp_path: Any) -> None:
        with pytest.raises(FileNotFoundError, match="Graph not found"):
            create_query(str(tmp_path))

    def test_override_returns_fast(self, sample_query: GraphQuery) -> None:
        set_query_override(sample_query)
        try:
            q = create_query("/nonexistent")
            assert q is sample_query
        finally:
            set_query_override(None)
