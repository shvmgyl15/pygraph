from __future__ import annotations

from pathlib import Path

from pygraph.builder import _run_plugins
from pygraph.graph.types import Graph, make_graph


def _make_test_graph() -> Graph:
    g = make_graph(project_root="/test")
    g.symbols = []
    g.calls = []
    return g


GOOD_PLUGIN = """
from pygraph.graph.types import Graph, make_call_edge

def run(graph: Graph) -> None:
    graph.calls.append(
        make_call_edge(
            caller_symbol_id="app.py::run",
            caller_name="run",
            callee_raw="db.query",
            file="app.py",
            line=10,
        )
    )
"""

NO_RUN_PLUGIN = """
x = 1
"""

RAISY_PLUGIN = """
from pygraph.graph.types import Graph

def run(graph: Graph) -> None:
    raise RuntimeError("plugin oops")
"""


class TestRunPlugins:
    def test_runs_plugin_and_modifies_graph(self, tmp_path: Path) -> None:
        plugin_path = tmp_path / "my_plugin.py"
        plugin_path.write_text(GOOD_PLUGIN)
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pygraph]\nplugins = ["my_plugin.py"]\n'
        )
        graph = _make_test_graph()
        _run_plugins(graph, str(tmp_path))
        assert len(graph.calls) == 1
        assert graph.calls[0].callee_raw == "db.query"

    def test_missing_plugin_warns(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pygraph]\nplugins = ["ghost.py"]\n'
        )
        graph = _make_test_graph()
        _run_plugins(graph, str(tmp_path))
        assert len(graph.calls) == 0

    def test_plugin_with_no_run_function_warns(self, tmp_path: Path) -> None:
        plugin_path = tmp_path / "no_run.py"
        plugin_path.write_text(NO_RUN_PLUGIN)
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pygraph]\nplugins = ["no_run.py"]\n'
        )
        graph = _make_test_graph()
        _run_plugins(graph, str(tmp_path))
        assert len(graph.calls) == 0

    def test_plugin_that_raises_warns_and_continues(self, tmp_path: Path) -> None:
        plugin_path = tmp_path / "raisy.py"
        plugin_path.write_text(RAISY_PLUGIN)
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pygraph]\nplugins = ["raisy.py"]\n'
        )
        graph = _make_test_graph()
        _run_plugins(graph, str(tmp_path))
        assert len(graph.calls) == 0

    def test_no_plugins_no_op(self, tmp_path: Path) -> None:
        graph = _make_test_graph()
        _run_plugins(graph, str(tmp_path))
        assert len(graph.calls) == 0

    def test_multiple_plugins_run_in_order(self, tmp_path: Path) -> None:
        plugin1 = tmp_path / "p1.py"
        plugin1.write_text(GOOD_PLUGIN)
        plugin2 = tmp_path / "p2.py"
        plugin2.write_text(GOOD_PLUGIN)
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pygraph]\nplugins = ["p1.py", "p2.py"]\n'
        )
        graph = _make_test_graph()
        _run_plugins(graph, str(tmp_path))
        assert len(graph.calls) == 2

    def test_plugin_failure_does_not_block_next(self, tmp_path: Path) -> None:
        raisy = tmp_path / "raisy.py"
        raisy.write_text(RAISY_PLUGIN)
        good = tmp_path / "good.py"
        good.write_text(GOOD_PLUGIN)
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pygraph]\nplugins = ["raisy.py", "good.py"]\n'
        )
        graph = _make_test_graph()
        _run_plugins(graph, str(tmp_path))
        assert len(graph.calls) == 1
        assert graph.calls[0].callee_raw == "db.query"
