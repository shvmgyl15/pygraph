from __future__ import annotations

import json
from pathlib import Path

import pytest

from pygraph.graph.serialize import deserialize, read_graph, serialize, write_graph
from pygraph.graph.types import (
    SCHEMA_VERSION,
    make_call_edge,
    make_dependency,
    make_env_read,
    make_error_edge,
    make_file_node,
    make_graph,
    make_http_route,
    make_implements_edge,
    make_import_edge,
    make_mutation_edge,
    make_package_node,
    make_struct_field,
    make_symbol_node,
    make_test_edge,
)


class TestSchemaVersion:
    def test_is_1(self) -> None:
        assert SCHEMA_VERSION == "1"


class TestFactoryDefaults:
    def test_make_graph_defaults(self) -> None:
        g = make_graph()
        assert g.schema_version == SCHEMA_VERSION
        assert g.generated_at != ""
        assert g.project_root == ""
        assert g.packages == []
        assert g.files == []
        assert g.symbols == []
        assert g.calls == []
        assert g.imports == []
        assert g.routes == []
        assert g.env_reads == []
        assert g.dependencies == []
        assert g.test_edges == []
        assert g.implements == []
        assert g.mutations == []
        assert g.errors == []

    def test_make_graph_overrides(self) -> None:
        g = make_graph(project_root="/project")
        assert g.project_root == "/project"

    def test_make_graph_iso_timestamp(self) -> None:
        g = make_graph()
        from datetime import datetime
        parsed = datetime.fromisoformat(g.generated_at)
        assert parsed is not None

    def test_make_package_node_defaults(self) -> None:
        p = make_package_node()
        assert p.id != ""
        assert p.name == ""
        assert p.import_path_best_effort == ""
        assert p.dir == ""
        assert p.files == []

    def test_make_package_node_overrides(self) -> None:
        p = make_package_node(name="utils", dir="./utils")
        assert p.name == "utils"
        assert p.dir == "./utils"
        assert p.files == []

    def test_make_file_node_defaults(self) -> None:
        f = make_file_node()
        assert f.id != ""
        assert f.path == ""
        assert f.package_name == ""
        assert f.lines == 0
        assert f.generated is False

    def test_make_file_node_overrides(self) -> None:
        f = make_file_node(path="src/main.py", generated=True, lines=42)
        assert f.path == "src/main.py"
        assert f.generated is True
        assert f.lines == 42

    def test_make_symbol_node_defaults(self) -> None:
        s = make_symbol_node()
        assert s.id != ""
        assert s.kind == "function"
        assert s.name == ""
        assert s.package_name == ""
        assert s.file == ""
        assert s.line == 0
        assert s.end_line == 0
        assert s.is_exported is False

    def test_make_symbol_node_overrides(self) -> None:
        s = make_symbol_node(name="Foo", kind="class", is_exported=True, line=10, end_line=30)
        assert s.name == "Foo"
        assert s.kind == "class"
        assert s.is_exported is True
        assert s.line == 10
        assert s.end_line == 30

    def test_make_symbol_node_python_fields(self) -> None:
        s = make_symbol_node(
            is_async=True,
            is_generator=True,
            is_classmethod=True,
            is_staticmethod=False,
            is_property=True,
            is_abstractmethod=False,
            decorators=["staticmethod", "cache"],
            bases=["BaseModel"],
            type_annotation="str",
        )
        assert s.is_async is True
        assert s.is_generator is True
        assert s.is_classmethod is True
        assert s.is_staticmethod is False
        assert s.is_property is True
        assert s.is_abstractmethod is False
        assert s.decorators == ["staticmethod", "cache"]
        assert s.bases == ["BaseModel"]
        assert s.type_annotation == "str"

    def test_make_symbol_node_with_struct_fields(self) -> None:
        field = make_struct_field(name="name", type="str")
        s = make_symbol_node(struct_fields=[field])
        assert len(s.struct_fields) == 1
        assert s.struct_fields[0].name == "name"
        assert s.struct_fields[0].type == "str"

    def test_make_call_edge_defaults(self) -> None:
        e = make_call_edge()
        assert e.caller_symbol_id == ""
        assert e.caller_name == ""
        assert e.callee_raw == ""
        assert e.file == ""
        assert e.line == 0

    def test_make_import_edge_defaults(self) -> None:
        e = make_import_edge()
        assert e.from_file == ""
        assert e.from_package == ""
        assert e.import_path == ""
        assert e.is_default is False

    def test_make_import_edge_is_default(self) -> None:
        e = make_import_edge(is_default=True)
        assert e.is_default is True

    def test_make_dependency_defaults(self) -> None:
        d = make_dependency()
        assert d.module == ""
        assert d.version == ""

    def test_make_http_route_defaults(self) -> None:
        r = make_http_route()
        assert r.method == ""
        assert r.path == ""
        assert r.handler == ""
        assert r.file == ""
        assert r.line == 0

    def test_make_env_read_defaults(self) -> None:
        e = make_env_read()
        assert e.key == ""
        assert e.accessor == ""
        assert e.file == ""
        assert e.line == 0

    def test_make_test_edge_defaults(self) -> None:
        t = make_test_edge()
        assert t.test_func == ""
        assert t.target == ""
        assert t.file == ""
        assert t.line == 0

    def test_make_implements_edge_defaults(self) -> None:
        e = make_implements_edge()
        assert e.interface == ""
        assert e.concrete == ""

    def test_make_mutation_edge_defaults(self) -> None:
        m = make_mutation_edge()
        assert m.field == ""
        assert m.function_name == ""
        assert m.file == ""
        assert m.line == 0

    def test_make_error_edge_defaults(self) -> None:
        e = make_error_edge()
        assert e.message == ""
        assert e.function_name == ""
        assert e.file == ""
        assert e.line == 0

    def test_make_struct_field_defaults(self) -> None:
        f = make_struct_field()
        assert f.name == ""
        assert f.type == ""

    def test_make_struct_field_overrides(self) -> None:
        f = make_struct_field(name="id", type="int", tag="json:id")
        assert f.name == "id"
        assert f.type == "int"
        assert f.tag == "json:id"


class TestSerialize:
    def test_produces_valid_json(self) -> None:
        g = make_graph()
        text = serialize(g)
        assert text.startswith("{")
        parsed = json.loads(text)
        assert parsed["schema_version"] == SCHEMA_VERSION

    def test_throws_on_version_mismatch(self) -> None:
        g = make_graph()
        g.schema_version = "999"
        with pytest.raises(ValueError, match="version mismatch"):
            serialize(g)


class TestDeserialize:
    def test_round_trips_all_fields(self) -> None:
        original = make_graph(project_root="/test")
        original.packages = [make_package_node(name="main", dir=".")]
        original.files = [make_file_node(path="main.py", package_name="main")]
        original.symbols = [
            make_symbol_node(name="run", kind="function", file="main.py", line=1, end_line=5)
        ]
        original.calls = [
            make_call_edge(
                caller_symbol_id="s1", caller_name="run",
                callee_raw="log", file="main.py", line=2,
            )
        ]
        original.imports = [make_import_edge(from_file="main.py", import_path="os")]
        original.dependencies = [make_dependency(module="flask", version="3.0")]
        original.routes = [
            make_http_route(method="GET", path="/api", handler="index", file="routes.py", line=3)
        ]
        original.env_reads = [
            make_env_read(key="PORT", accessor="os.environ.get('PORT')", file="config.py", line=5)
        ]
        original.test_edges = [
            make_test_edge(test_func="test_run", target="run", file="test_main.py", line=1)
        ]
        original.implements = [
            make_implements_edge(interface="Repository", concrete="PostgresRepo")
        ]
        original.mutations = [
            make_mutation_edge(field="User.name", function_name="rename", file="user.py", line=8)
        ]
        original.errors = [
            make_error_edge(message="not found", function_name="find_user", file="user.py", line=12)
        ]

        text = serialize(original)
        restored = deserialize(text)

        assert restored.schema_version == original.schema_version
        assert restored.project_root == original.project_root
        assert len(restored.packages) == 1
        assert len(restored.files) == 1
        assert len(restored.symbols) == 1
        assert len(restored.calls) == 1
        assert len(restored.imports) == 1
        assert len(restored.dependencies) == 1
        assert len(restored.routes) == 1
        assert len(restored.env_reads) == 1
        assert len(restored.test_edges) == 1
        assert len(restored.implements) == 1
        assert len(restored.mutations) == 1
        assert len(restored.errors) == 1

    def test_round_trips_empty_graph(self) -> None:
        original = make_graph(project_root="/empty")
        text = serialize(original)
        restored = deserialize(text)
        assert restored.project_root == "/empty"
        assert restored.packages == []

    def test_rejects_malformed_json(self) -> None:
        with pytest.raises(ValueError, match="Invalid JSON"):
            deserialize("not json")

    def test_rejects_null(self) -> None:
        with pytest.raises(ValueError, match="expected a JSON object"):
            deserialize("null")

    def test_rejects_missing_version(self) -> None:
        data: dict = {
            "generated_at": "",
            "project_root": "/x",
            "packages": [], "files": [], "symbols": [],
            "calls": [], "imports": [], "routes": [],
            "env_reads": [], "dependencies": [], "test_edges": [],
            "implements": [], "mutations": [], "errors": [],
        }
        with pytest.raises(ValueError, match="Missing required field"):
            deserialize(json.dumps(data))

    def test_rejects_version_mismatch(self) -> None:
        g = make_graph()
        g.schema_version = "2"
        with pytest.raises(ValueError, match="version mismatch"):
            deserialize(serialize(g))

    def test_rejects_missing_array_fields(self) -> None:
        data = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": "",
            "project_root": "",
        }
        with pytest.raises(ValueError, match="Missing required field"):
            deserialize(json.dumps(data))

    def test_rejects_non_list_array_field(self) -> None:
        data = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": "",
            "project_root": "",
            "packages": "not_a_list", "files": [], "symbols": [],
            "calls": [], "imports": [], "routes": [],
            "env_reads": [], "dependencies": [], "test_edges": [],
            "implements": [], "mutations": [], "errors": [],
            "blueprints": [], "blueprint_registrations": [],
            "template_refs": [], "extensions": [],
        }
        with pytest.raises(ValueError, match="must be a list"):
            deserialize(json.dumps(data))

    def test_accepts_extra_unknown_fields(self) -> None:
        g = make_graph(project_root="/future")
        text = serialize(g)
        data = json.loads(text)
        data["future_field"] = "hello"
        restored = deserialize(json.dumps(data))
        assert restored.project_root == "/future"


class TestFileIO:
    def test_round_trip(self, tmp_path: Path) -> None:
        graph_path = tmp_path / ".pygraph" / "graph.json"
        original = make_graph(project_root="/test")
        write_graph(original, graph_path)
        assert graph_path.exists()
        restored = read_graph(graph_path)
        assert restored.project_root == "/test"
        assert restored.schema_version == SCHEMA_VERSION
        assert restored.generated_at == original.generated_at

    def test_write_creates_parent_dirs(self, tmp_path: Path) -> None:
        deep_path = tmp_path / "a" / "b" / "c" / "graph.json"
        g = make_graph()
        write_graph(g, deep_path)
        assert deep_path.exists()
        restored = read_graph(deep_path)
        assert restored.schema_version == SCHEMA_VERSION


class TestPythonSpecificFields:
    def test_symbol_node_async_defaults(self) -> None:
        s = make_symbol_node()
        assert s.is_async is False
        assert s.is_generator is False

    def test_symbol_node_method_type_defaults(self) -> None:
        s = make_symbol_node()
        assert s.is_classmethod is False
        assert s.is_staticmethod is False
        assert s.is_property is False
        assert s.is_abstractmethod is False

    def test_symbol_node_collection_defaults(self) -> None:
        s = make_symbol_node()
        assert s.decorators == []
        assert s.bases == []
        assert s.struct_fields == []
        assert s.embedded_types == []

    def test_round_trip_python_fields(self) -> None:
        original = make_graph()
        original.symbols = [
            make_symbol_node(
                name="validate",
                kind="function",
                is_async=True,
                is_generator=False,
                is_classmethod=False,
                is_staticmethod=True,
                decorators=["staticmethod"],
                type_annotation="bool",
                bases=[],
            )
        ]
        text = serialize(original)
        restored = deserialize(text)
        assert len(restored.symbols) == 1
        s = restored.symbols[0]
        assert s.name == "validate"
        assert s.is_async is True
        assert s.is_staticmethod is True
        assert s.decorators == ["staticmethod"]
        assert s.type_annotation == "bool"

    def test_round_trip_struct_fields(self) -> None:
        original = make_graph()
        original.symbols = [
            make_symbol_node(
                name="User",
                kind="class",
                struct_fields=[
                    make_struct_field(name="name", type="str"),
                    make_struct_field(name="age", type="int"),
                ],
            )
        ]
        text = serialize(original)
        restored = deserialize(text)
        s = restored.symbols[0]
        assert len(s.struct_fields) == 2
        assert s.struct_fields[0].name == "name"
        assert s.struct_fields[0].type == "str"
        assert s.struct_fields[1].name == "age"
        assert s.struct_fields[1].type == "int"
