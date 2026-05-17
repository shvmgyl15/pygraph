from __future__ import annotations

import json
from pathlib import Path

import pytest

from pygraph.graph.serialize import serialize, write_graph
from pygraph.graph.types import (
    Graph,
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


@pytest.fixture
def sample_graph() -> Graph:
    g = make_graph(project_root="/test")

    pkg = make_package_node(name="sample", dir=".")
    g.packages = [pkg]

    g.files = [
        make_file_node(path="app.py", package_name="sample", lines=40),
        make_file_node(path="utils.py", package_name="sample", lines=30),
        make_file_node(path="tests/test_app.py", package_name="sample", lines=15),
    ]

    g.symbols = [
        # app.py symbols
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
            is_exported=False,
            complexity=2,
        ),
        make_symbol_node(
            id="app.py::setup", name="setup", kind="function",
            file="app.py", line=20, end_line=25,
            is_exported=True,
            complexity=1,
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
        # utils.py symbols
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
        # test symbols
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

    return g


@pytest.fixture
def query(sample_graph: Graph) -> GraphQuery:
    return GraphQuery(sample_graph, root="/test")


class TestFindSymbols:
    def test_find_by_exact_name(self, query: GraphQuery) -> None:
        symbols = query.find_symbols(r"\brun\b")
        names = {s.name for s in symbols}
        assert "run" in names
        assert "test_run" not in names

    def test_find_by_regex(self, query: GraphQuery) -> None:
        symbols = query.find_symbols("test_.*")
        names = {s.name for s in symbols}
        assert "test_run" in names
        assert "test_service" in names

    def test_find_substring(self, query: GraphQuery) -> None:
        symbols = query.find_symbols("helper")
        assert any(s.name == "_helper" for s in symbols)

    def test_find_no_match(self, query: GraphQuery) -> None:
        symbols = query.find_symbols("nonexistent")
        assert symbols == []

    def test_find_invalid_regex_falls_back(self, query: GraphQuery) -> None:
        symbols = query.find_symbols("[invalid")
        assert symbols == []


class TestGetSymbol:
    def test_get_existing_symbol(self, query: GraphQuery) -> None:
        s = query.get_symbol("run")
        assert s is not None
        assert s.name == "run"
        assert s.kind == "function"
        assert s.file == "app.py"

    def test_get_nonexistent_symbol(self, query: GraphQuery) -> None:
        s = query.get_symbol("ghost")
        assert s is None

    def test_get_class_symbol(self, query: GraphQuery) -> None:
        s = query.get_symbol("Service")
        assert s is not None
        assert s.kind == "class"
        assert s.is_exported is True

    def test_get_private_symbol(self, query: GraphQuery) -> None:
        s = query.get_symbol("_internal")
        assert s is not None
        assert s.is_exported is False

    def test_get_constant_symbol(self, query: GraphQuery) -> None:
        s = query.get_symbol("APP_NAME")
        assert s is not None
        assert s.kind == "constant"


class TestGetCallers:
    def test_get_callers_of_function(self, query: GraphQuery) -> None:
        callers = query.get_callers("setup")
        assert len(callers) == 1
        assert callers[0][0].name == "run"
        assert callers[0][1].callee_raw == "setup"

    def test_get_callers_of_method(self, query: GraphQuery) -> None:
        callers = query.get_callers("Service.start")
        assert len(callers) == 1
        assert callers[0][0].name == "run"

    def test_get_callers_of_uncalled(self, query: GraphQuery) -> None:
        callers = query.get_callers("_unused")
        assert callers == []

    def test_get_callers_nonexistent(self, query: GraphQuery) -> None:
        callers = query.get_callers("ghost")
        assert callers == []


class TestGetCallees:
    def test_get_callees_of_function(self, query: GraphQuery) -> None:
        callees = query.get_callees("run")
        assert len(callees) == 3

    def test_get_callees_includes_resolved(self, query: GraphQuery) -> None:
        callees = query.get_callees("run")
        resolved = [c for c, _ in callees if c is not None]
        names = {c.name for c in resolved}
        assert "setup" in names
        assert "load" in names

    def test_get_callees_of_method(self, query: GraphQuery) -> None:
        callees = query.get_callees("start")
        assert len(callees) == 1
        _, edge = callees[0]
        assert edge.callee_raw == "_helper"

    def test_get_callees_of_symbol_without_calls(self, query: GraphQuery) -> None:
        callees = query.get_callees("load")
        assert callees == []


class TestGetPublic:
    def test_returns_exported_symbols(self, query: GraphQuery) -> None:
        public = query.get_public()
        names = {s.name for s in public}
        assert "run" in names
        assert "setup" in names
        assert "Service" in names
        assert "APP_NAME" in names
        assert "load" in names
        assert "parse" in names

    def test_excludes_private(self, query: GraphQuery) -> None:
        public = query.get_public()
        names = {s.name for s in public}
        assert "_helper" not in names
        assert "_internal" not in names
        assert "_unused" not in names


class TestGetImports:
    def test_get_imports_of_file(self, query: GraphQuery) -> None:
        imports = query.get_imports("app.py")
        assert len(imports) == 1
        assert imports[0].import_path == "utils.load"

    def test_get_imports_of_file_without_imports(self, query: GraphQuery) -> None:
        imports = query.get_imports("utils.py")
        assert imports == []

    def test_get_imports_nonexistent_file(self, query: GraphQuery) -> None:
        imports = query.get_imports("ghost.py")
        assert imports == []


class TestGetFile:
    def test_get_existing_file(self, query: GraphQuery) -> None:
        f = query.get_file("app.py")
        assert f is not None
        assert f.path == "app.py"
        assert f.lines == 40

    def test_get_nonexistent_file(self, query: GraphQuery) -> None:
        f = query.get_file("ghost.py")
        assert f is None


class TestGetSource:
    def test_source_nonexistent_file(self, query: GraphQuery) -> None:
        src = query.get_source("ghost.py")
        assert src is None


class TestGetContext:
    def test_context_includes_symbol(self, query: GraphQuery) -> None:
        ctx = query.get_context("run")
        assert ctx["symbol"] is not None
        assert ctx["symbol"].name == "run"

    def test_context_includes_callers(self, query: GraphQuery) -> None:
        ctx = query.get_context("setup")
        assert len(ctx["callers"]) == 1
        assert ctx["callers"][0]["caller"] == "run"

    def test_context_includes_callees(self, query: GraphQuery) -> None:
        ctx = query.get_context("run")
        assert len(ctx["callees"]) == 3

    def test_context_includes_tests(self, query: GraphQuery) -> None:
        ctx = query.get_context("run")
        assert len(ctx["test_edges"]) == 1
        assert ctx["test_edges"][0]["test_func"] == "test_run"

    def test_context_nonexistent(self, query: GraphQuery) -> None:
        ctx = query.get_context("ghost")
        assert ctx["symbol"] is None
        assert ctx["callers"] == []
        assert ctx["callees"] == []


class TestGetTestsFor:
    def test_get_tests_for_existing(self, query: GraphQuery) -> None:
        tests = query.get_tests_for("run")
        assert len(tests) == 1
        assert tests[0]["test_func"] == "test_run"

    def test_get_tests_for_nonexistent(self, query: GraphQuery) -> None:
        tests = query.get_tests_for("ghost")
        assert tests == []


class TestGetOrphans:
    def test_identifies_orphans(self, query: GraphQuery) -> None:
        orphans = query.get_orphans()
        names = {s.name for s in orphans}
        assert "_unused" in names

    def test_excludes_called_privates(self, query: GraphQuery) -> None:
        orphans = query.get_orphans()
        names = {s.name for s in orphans}
        assert "_helper" not in names
        assert "_internal" not in names

    def test_excludes_exported(self, query: GraphQuery) -> None:
        orphans = query.get_orphans()
        names = {s.name for s in orphans}
        assert "run" not in names
        assert "setup" not in names


class TestGetImpact:
    def test_impact_of_function(self, query: GraphQuery) -> None:
        edges = query.get_impact("run")
        assert len(edges) >= 2
        names = {e["callee"] for e in edges}
        assert "setup" in names
        assert "load" in names

    def test_impact_nonexistent(self, query: GraphQuery) -> None:
        edges = query.get_impact("ghost")
        assert edges == []


class TestGetPath:
    def test_path_between_symbols(self, query: GraphQuery) -> None:
        path = query.get_path("run", "_helper")
        assert path is not None
        assert len(path) >= 1

    def test_path_nonexistent_source(self, query: GraphQuery) -> None:
        path = query.get_path("ghost", "run")
        assert path is None

    def test_path_same_symbol(self, query: GraphQuery) -> None:
        path = query.get_path("run", "run")
        assert path is not None
        assert path == []


class TestGetTrace:
    def test_trace_matching_error(self, query: GraphQuery) -> None:
        results = query.get_trace("connection refused")
        assert len(results) == 1
        assert results[0]["message"] == "connection refused"

    def test_trace_no_match(self, query: GraphQuery) -> None:
        results = query.get_trace("nothing")
        assert results == []


class TestGetErrorflow:
    def test_errorflow(self, query: GraphQuery) -> None:
        results = query.get_errorflow("connection refused")
        assert len(results) >= 1
        assert results[0]["error"].function_name == "start"


class TestGraphSerialization:
    def test_round_trip_through_json(self, sample_graph: Graph) -> None:
        text = serialize(sample_graph)
        data = json.loads(text)

        assert data["schema_version"] == "1"
        assert len(data["symbols"]) == 13
        assert len(data["calls"]) == 5
        assert len(data["imports"]) == 2
        assert len(data["test_edges"]) == 2
        assert len(data["errors"]) == 1
        assert len(data["dependencies"]) == 1

    def test_round_trip_preserves_query(self, sample_graph: Graph, tmp_path: Path) -> None:
        graph_path = tmp_path / ".pygraph" / "graph.json"
        write_graph(sample_graph, graph_path)
        from pygraph.graph.serialize import read_graph
        restored = read_graph(graph_path)
        q = GraphQuery(restored, root="/test")
        assert q.get_symbol("run") is not None
        assert len(q.get_callers("setup")) == 1


class TestCommandOutput:
    def test_node_command_shows_fields(
        self, query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.node import run
        run(query, "run")
        captured = capsys.readouterr()
        assert "run" in captured.out
        assert "function" in captured.out
        assert "app.py" in captured.out

    def test_node_command_not_found(
        self, query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.node import run
        run(query, "ghost")
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_public_command_output(
        self, query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.public import run
        run(query)
        captured = capsys.readouterr()
        assert "run" in captured.out
        assert "_helper" not in captured.out

    def test_callers_command_output(
        self, query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.callers import run
        run(query, "setup")
        captured = capsys.readouterr()
        assert "run" in captured.out

    def test_callees_command_output(
        self, query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.callees import run
        run(query, "run")
        captured = capsys.readouterr()
        assert "setup" in captured.out

    def test_imports_command_output(
        self, query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.imports_cmd import run
        run(query, "app.py")
        captured = capsys.readouterr()
        assert "utils.load" in captured.out

    def test_orphans_command_output(
        self, query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.orphans import run
        run(query)
        captured = capsys.readouterr()
        assert "_unused" in captured.out

    def test_focus_command_output(
        self, query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.focus import run
        run(query, "run")
        captured = capsys.readouterr()
        assert '"name": "run"' in captured.out
        assert '"callers"' in captured.out

    def test_query_command_output(
        self, query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.query_cmd import run
        run(query, "test_.*")
        captured = capsys.readouterr()
        assert "test_run" in captured.out
        assert "test_service" in captured.out

    def test_context_command_output(
        self, query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.context import run
        run(query, "run")
        captured = capsys.readouterr()
        assert "=== run (function) ===" in captured.out
        assert "Callees" in captured.out

    def test_impact_command_output(
        self, query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.impact import run
        run(query, "run")
        captured = capsys.readouterr()
        assert "->" in captured.out

    def test_path_command_output(
        self, query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.path_cmd import run
        run(query, "run", "_helper")
        captured = capsys.readouterr()
        assert "->" in captured.out

    def test_trace_command_output(
        self, query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.trace import run
        run(query, "connection refused")
        captured = capsys.readouterr()
        assert "connection refused" in captured.out

    def test_source_command_not_found(
        self, query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.source import run
        run(query, "nonexistent.py")
        captured = capsys.readouterr()
        assert "not found" in captured.out


class TestGetComplexity:
    def test_complexity_for_symbol(self, query: GraphQuery) -> None:
        results = query.get_complexity("run")
        assert len(results) == 1
        assert results[0]["name"] == "run"
        assert results[0]["complexity"] == 3

    def test_complexity_ranking(self, query: GraphQuery) -> None:
        results = query.get_complexity()
        names = [r["name"] for r in results]
        assert "run" in names
        assert "_helper" in names
        assert results[0]["complexity"] >= results[1]["complexity"]

    def test_complexity_not_found(self, query: GraphQuery) -> None:
        results = query.get_complexity("ghost")
        assert results == []

    def test_complexity_command_output(
        self, query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.complexity import run
        run(query, "run")
        captured = capsys.readouterr()
        assert "Complexity: 3" in captured.out
        assert "run" in captured.out

    def test_complexity_command_ranked_output(
        self, query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.complexity import run
        run(query)
        captured = capsys.readouterr()
        assert "Complexity" in captured.out
        assert "run" in captured.out
        assert "_helper" in captured.out


class TestGetCoupling:
    def test_coupling_for_symbol(self, query: GraphQuery) -> None:
        results = query.get_coupling("run")
        assert len(results) == 1
        assert results[0]["name"] == "run"
        assert results[0]["ce"] >= 1

    def test_coupling_not_found(self, query: GraphQuery) -> None:
        results = query.get_coupling("ghost")
        assert results == []

    def test_coupling_ranking(self, query: GraphQuery) -> None:
        results = query.get_coupling()
        assert len(results) > 0
        assert all("ca" in r and "ce" in r and "instability" in r for r in results)

    def test_coupling_command_output(
        self, query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.coupling import run
        run(query, "run")
        captured = capsys.readouterr()
        assert "Ca" in captured.out
        assert "Ce" in captured.out
        assert "Instability" in captured.out


class TestGetHotspots:
    def test_hotspots_found(self, query: GraphQuery) -> None:
        results = query.get_hotspots(top_n=5)
        assert len(results) > 0
        assert all("score" in r and "complexity" in r and "coupling" in r for r in results)

    def test_hotspot_command_output(
        self, query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.hotspot import run
        run(query, top_n=5)
        captured = capsys.readouterr()
        assert "Score" in captured.out
        assert "Complexity" in captured.out
        assert "Coupling" in captured.out


class TestGetDeps:
    def test_deps_found(self, query: GraphQuery) -> None:
        results = query.get_deps()
        assert len(results) >= 1
        assert results[0]["module"] == "flask"
        assert results[0]["version"] == "3.0"

    def test_deps_command_output(
        self, query: GraphQuery, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from pygraph.commands.deps import run
        run(query)
        captured = capsys.readouterr()
        assert "flask" in captured.out
        assert "3.0" in captured.out


class TestGetImpactExtended:
    def test_impact_transitive(self, query: GraphQuery) -> None:
        edges = query.get_impact("run")
        names = {e["callee"] for e in edges}
        assert "_helper" in names

    def test_impact_max_depth(self, query: GraphQuery) -> None:
        edges = query.get_impact("run", max_depth=1)
        names = {e["callee"] for e in edges}
        assert "setup" in names
        assert "load" in names
        assert "start" in names
        assert "_helper" not in names

    def test_impact_no_callees(self, query: GraphQuery) -> None:
        edges = query.get_impact("load")
        assert edges == []


class TestGetPathExtended:
    def test_path_includes_file_line(self, query: GraphQuery) -> None:
        path = query.get_path("run", "_helper")
        assert path is not None
        assert len(path) == 2
        for step in path:
            assert "file" in step
            assert "line" in step

    def test_path_no_path(self, query: GraphQuery) -> None:
        path = query.get_path("parse", "_unused")
        assert path is None


class TestGetOrphansExtended:
    def test_orphans_dead_chain(self, query: GraphQuery) -> None:
        g = query.graph
        g.symbols.append(make_symbol_node(
            id="utils.py::_dead_helper", name="_dead_helper", kind="function",
            file="utils.py", line=20, end_line=22, is_exported=False,
        ))
        g.calls.append(make_call_edge(
            caller_symbol_id="utils.py::_unused", caller_name="_unused",
            callee_raw="_dead_helper", file="utils.py", line=18,
        ))
        q2 = GraphQuery(g, root="/test")
        names = {s.name for s in q2.get_orphans()}
        assert "_unused" in names
        assert "_dead_helper" in names

    def test_orphans_empty_when_all_reachable(self, query: GraphQuery) -> None:
        orphans = query.get_orphans()
        assert len(orphans) >= 1
        assert all(not s.is_exported for s in orphans)


class TestGetErrorflowExtended:
    def test_errorflow_reverse_trace(self, query: GraphQuery) -> None:
        results = query.get_errorflow("connection refused")
        assert len(results) >= 1
        trace = results[0]["trace"]
        assert len(trace) >= 1
        callers = {t["from"] for t in trace}
        assert "run" in callers
        assert all("file" in t and "line" in t for t in trace)

    def test_errorflow_no_match(self, query: GraphQuery) -> None:
        results = query.get_errorflow("nonexistent")
        assert results == []

    def test_errorflow_substring_match(self, query: GraphQuery) -> None:
        results = query.get_errorflow("refused")
        assert len(results) >= 1
        assert results[0]["error"].function_name == "start"
