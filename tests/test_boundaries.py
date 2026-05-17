from __future__ import annotations

import json
from pathlib import Path

import pytest

from pygraph.graph.boundaries import (
    BoundaryConfig,
    BoundaryLayer,
    load_boundary_config,
)
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
def layered_query() -> GraphQuery:
    g = make_graph(project_root="/test")
    pkg = make_package_node(name="app", dir=".")
    g.packages = [pkg]
    g.files = [
        make_file_node(path="src/views/user.py", package_name="app", lines=20),
        make_file_node(path="src/services/user.py", package_name="app", lines=30),
        make_file_node(path="src/models/user.py", package_name="app", lines=15),
        make_file_node(path="src/repos/user.py", package_name="app", lines=25),
    ]
    g.symbols = [
        make_symbol_node(
            id="views::get_user", name="get_user", kind="function",
            file="src/views/user.py", line=1, is_exported=True,
        ),
        make_symbol_node(
            id="services::find_user", name="find_user", kind="function",
            file="src/services/user.py", line=1, is_exported=True,
        ),
        make_symbol_node(
            id="services::helper", name="_helper", kind="function",
            file="src/services/user.py", line=10, is_exported=False,
        ),
        make_symbol_node(
            id="models::UserModel", name="UserModel", kind="class",
            file="src/models/user.py", line=1, is_exported=True,
        ),
        make_symbol_node(
            id="repos::fetch_repo", name="fetch_repo", kind="function",
            file="src/repos/user.py", line=1, is_exported=True,
        ),
    ]
    g.calls = [
        make_call_edge(
            caller_symbol_id="views::get_user", caller_name="get_user",
            callee_raw="find_user", file="src/views/user.py", line=2,
        ),
        make_call_edge(
            caller_symbol_id="views::get_user", caller_name="get_user",
            callee_raw="UserModel", file="src/views/user.py", line=3,
        ),
        make_call_edge(
            caller_symbol_id="services::find_user", caller_name="find_user",
            callee_raw="_helper", file="src/services/user.py", line=5,
        ),
        make_call_edge(
            caller_symbol_id="services::find_user", caller_name="find_user",
            callee_raw="fetch_repo", file="src/services/user.py", line=6,
        ),
        make_call_edge(
            caller_symbol_id="repos::fetch_repo", caller_name="fetch_repo",
            callee_raw="UserModel", file="src/repos/user.py", line=2,
        ),
    ]
    return GraphQuery(g, root="/test")


@pytest.fixture
def sample_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "boundaries.json"
    cfg.write_text(json.dumps({
        "layers": [
            {
                "name": "views",
                "pattern": "src/views/",
                "allowed": ["services"],
            },
            {
                "name": "services",
                "pattern": "src/services/",
                "allowed": ["models", "repos", "services"],
            },
            {
                "name": "models",
                "pattern": "src/models/",
                "allowed": [],
            },
            {
                "name": "repos",
                "pattern": "src/repos/",
                "allowed": ["models"],
            },
        ],
    }))
    return cfg


# ---------------------------------------------------------------------------
# Config unit tests
# ---------------------------------------------------------------------------


class TestBoundaryLayer:
    def test_matches_by_substring(self) -> None:
        layer = BoundaryLayer(name="views", pattern="src/views/", allowed=[])
        assert layer.matches("src/views/user.py") is True
        assert layer.matches("src/services/user.py") is False


class TestBoundaryConfig:
    def test_layer_for_returns_correct_layer(self) -> None:
        cfg = BoundaryConfig([
            BoundaryLayer("views", "src/views/", []),
            BoundaryLayer("services", "src/services/", []),
        ])
        assert cfg.layer_for("src/views/user.py") == "views"
        assert cfg.layer_for("src/services/user.py") == "services"
        assert cfg.layer_for("src/models/user.py") is None

    def test_is_allowed_valid(self) -> None:
        cfg = BoundaryConfig([
            BoundaryLayer("views", "src/views/", ["services"]),
        ])
        assert cfg.is_allowed("views", "services") is True
        assert cfg.is_allowed("views", "models") is False

    def test_is_allowed_unknown_caller_layer(self) -> None:
        cfg = BoundaryConfig([
            BoundaryLayer("views", "src/views/", []),
        ])
        assert cfg.is_allowed("nonexistent", "views") is True


class TestLoadBoundaryConfig:
    def test_loads_valid_config(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "boundaries.json"
        cfg_file.write_text(json.dumps({
            "layers": [
                {"name": "web", "pattern": "web/", "allowed": ["core"]},
            ],
        }))
        cfg = load_boundary_config(str(cfg_file))
        assert len(cfg.layers) == 1
        assert cfg.layers[0].name == "web"

    def test_raises_on_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_boundary_config("/nonexistent/boundaries.json")


# ---------------------------------------------------------------------------
# Boundary violation detection
# ---------------------------------------------------------------------------


class TestGetBoundaryViolations:
    def test_allows_valid_cross_layer_calls(
        self, layered_query: GraphQuery, sample_config: Path
    ) -> None:
        violations = layered_query.get_boundary_violations(str(sample_config))
        # With sample_config:
        #   views->services=allowed, views->models=VIOLATION
        #   services->services=allowed, services->repos=allowed
        #   repos->models=allowed
        # So 1 violation expected (views->models)
        assert len(violations) == 1
        assert violations[0]["from_layer"] == "views"
        assert violations[0]["to_layer"] == "models"

    def test_detects_violations(self, layered_query: GraphQuery, tmp_path: Path) -> None:
        cfg_file = tmp_path / "boundaries.json"
        cfg_file.write_text(json.dumps({
            "layers": [
                {"name": "views", "pattern": "src/views/", "allowed": []},
                {"name": "services", "pattern": "src/services/", "allowed": []},
                {"name": "models", "pattern": "src/models/", "allowed": []},
                {"name": "repos", "pattern": "src/repos/", "allowed": []},
            ],
        }))
        violations = layered_query.get_boundary_violations(str(cfg_file))
        # All cross-layer calls should be violations now
        assert len(violations) >= 2  # views->services, views->models
        found_views_services = any(
            v["from_layer"] == "views" and v["to_layer"] == "services"
            for v in violations
        )
        found_views_models = any(
            v["from_layer"] == "views" and v["to_layer"] == "models"
            for v in violations
        )
        assert found_views_services
        assert found_views_models

    def test_ignores_calls_outside_layers(
        self, layered_query: GraphQuery, tmp_path: Path
    ) -> None:
        cfg_file = tmp_path / "boundaries.json"
        cfg_file.write_text(json.dumps({
            "layers": [
                {"name": "views", "pattern": "src/views/", "allowed": []},
            ],
        }))
        violations = layered_query.get_boundary_violations(str(cfg_file))
        # callees (find_user, UserModel) don't match src/views/ so skipped
        assert len(violations) == 0

    def test_no_config_returns_empty(
        self, layered_query: GraphQuery
    ) -> None:
        violations = layered_query.get_boundary_violations()
        assert violations == []

    def test_violation_contains_metadata(
        self, layered_query: GraphQuery, tmp_path: Path
    ) -> None:
        cfg_file = tmp_path / "boundaries.json"
        cfg_file.write_text(json.dumps({
            "layers": [
                {"name": "views", "pattern": "src/views/", "allowed": []},
                {"name": "services", "pattern": "src/services/", "allowed": []},
                {"name": "models", "pattern": "src/models/", "allowed": []},
            ],
        }))
        violations = layered_query.get_boundary_violations(str(cfg_file))
        v = violations[0]
        assert "from" in v
        assert "to" in v
        assert "from_layer" in v
        assert "to_layer" in v
        assert "file" in v
        assert "line" in v


# ---------------------------------------------------------------------------
# MCP boundaries tool
# ---------------------------------------------------------------------------


class TestMCPBoundariesTool:
    def test_boundaries_via_mcp(
        self, layered_query: GraphQuery, tmp_path: Path
    ) -> None:
        cfg_file = tmp_path / "boundaries.json"
        cfg_file.write_text(json.dumps({
            "layers": [
                {"name": "views", "pattern": "src/views/", "allowed": []},
                {"name": "services", "pattern": "src/services/", "allowed": []},
                {"name": "models", "pattern": "src/models/", "allowed": []},
            ],
        }))
        set_query_override(layered_query)
        try:
            from pygraph.server import boundaries as tool_fn
            result = tool_fn(config=str(cfg_file))
            assert len(result) >= 1
            assert result[0]["from_layer"] == "views"
        finally:
            set_query_override(None)

    def test_boundaries_empty_when_no_config(
        self, layered_query: GraphQuery
    ) -> None:
        set_query_override(layered_query)
        try:
            from pygraph.server import boundaries as tool_fn
            result = tool_fn(config="/nonexistent/boundaries.json")
            assert result == []
        finally:
            set_query_override(None)


# ---------------------------------------------------------------------------
# CLI command run
# ---------------------------------------------------------------------------


class TestBoundariesCommand:
    def test_run_no_violations(
        self, layered_query: GraphQuery, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cfg_file = tmp_path / "boundaries.json"
        cfg_file.write_text('{"layers": []}')
        from pygraph.commands.boundaries import run
        run(layered_query, str(cfg_file))
        captured = capsys.readouterr()
        assert "No boundary violations found" in captured.out

    def test_run_with_violations(
        self, layered_query: GraphQuery, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cfg_file = tmp_path / "boundaries.json"
        cfg_file.write_text(json.dumps({
            "layers": [
                {"name": "views", "pattern": "src/views/", "allowed": []},
                {"name": "services", "pattern": "src/services/", "allowed": []},
                {"name": "models", "pattern": "src/models/", "allowed": []},
            ],
        }))
        from pygraph.commands.boundaries import run
        run(layered_query, str(cfg_file))
        captured = capsys.readouterr()
        assert "views -> services" in captured.out
        assert "views -> models" in captured.out
