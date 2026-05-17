from __future__ import annotations

from pathlib import Path

import pytest

from pygraph.graph.types import (
    make_file_node,
    make_graph,
    make_package_node,
    make_symbol_node,
)
from pygraph.query import GraphQuery
from pygraph.server import set_query_override


@pytest.fixture
def plugin_query() -> GraphQuery:
    g = make_graph(project_root="/test")
    g.packages = [make_package_node(name="sample", dir=".")]
    g.files = [make_file_node(path="app.py", package_name="sample", lines=10)]
    g.symbols = [
        make_symbol_node(
            id="app.py::run", name="run", kind="function",
            file="app.py", line=1, is_exported=True,
        ),
    ]
    return GraphQuery(g, root="/test")


class TestOpenCodePluginCommand:
    def test_creates_opencode_json(
        self, plugin_query: GraphQuery, tmp_path: Path
    ) -> None:
        from pygraph.commands.opencode_plugin import run
        root = str(tmp_path)
        run(plugin_query, root)
        config_path = tmp_path / ".opencode.json"
        assert config_path.exists()
        content = config_path.read_text()
        assert "mcp_servers" in content
        assert "pygraph" in content
        assert "agents" in content


class TestMCPOpenCodePlugin:
    def test_add_opencode_plugin_tool(
        self, plugin_query: GraphQuery, tmp_path: Path
    ) -> None:
        set_query_override(plugin_query)
        try:
            from pygraph.server import add_opencode_plugin as tool_fn
            result = tool_fn(root=str(tmp_path))
            assert "Created" in result
            assert (tmp_path / ".opencode.json").exists()
        finally:
            set_query_override(None)
