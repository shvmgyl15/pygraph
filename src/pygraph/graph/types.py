from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "1"

_next_id_counter: int = 0


def _generate_id() -> str:
    global _next_id_counter
    _next_id_counter += 1
    return f"gen_{_next_id_counter}"


@dataclass
class StructField:
    name: str = ""
    type: str = ""
    tag: str | None = None


@dataclass
class SymbolNode:
    id: str = ""
    kind: str = "function"
    name: str = ""
    receiver: str | None = None
    package_name: str = ""
    file: str = ""
    line: int = 0
    end_line: int = 0
    doc: str | None = None
    signature: str | None = None
    method_signature: str | None = None
    is_exported: bool = False
    is_async: bool = False
    is_generator: bool = False
    is_classmethod: bool = False
    is_staticmethod: bool = False
    is_property: bool = False
    is_abstractmethod: bool = False
    decorators: list[str] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)
    type_annotation: str | None = None
    struct_fields: list[StructField] = field(default_factory=list)
    embedded_types: list[str] = field(default_factory=list)
    arity: int | None = None
    complexity: int | None = None
    event_productions: list[dict[str, Any]] = field(default_factory=list)
    event_consumptions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PackageNode:
    id: str = ""
    name: str = ""
    import_path_best_effort: str = ""
    dir: str = ""
    files: list[str] = field(default_factory=list)


@dataclass
class FileNode:
    id: str = ""
    path: str = ""
    package_name: str = ""
    lines: int = 0
    generated: bool = False


@dataclass
class CallEdge:
    caller_symbol_id: str = ""
    caller_name: str = ""
    callee_raw: str = ""
    file: str = ""
    line: int = 0


@dataclass
class ImportEdge:
    from_file: str = ""
    from_package: str = ""
    import_path: str = ""
    alias: str | None = None
    is_default: bool = False


@dataclass
class Dependency:
    module: str = ""
    version: str = ""


@dataclass
class HTTPRoute:
    method: str = ""
    path: str = ""
    handler: str = ""
    file: str = ""
    line: int = 0
    response_model: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class ResponseModelRef:
    route_path: str = ""
    method: str = ""
    model_name: str = ""
    model_file: str = ""
    symbol_id: str = ""
    wrapper: str | None = None


@dataclass
class BlueprintDef:
    name: str = ""
    import_name: str = ""
    file: str = ""
    line: int = 0


@dataclass
class BlueprintRegistration:
    app_var: str = ""
    blueprint_var: str = ""
    url_prefix: str = ""
    file: str = ""
    line: int = 0


@dataclass
class TemplateRef:
    template_path: str = ""
    function_name: str = ""
    file: str = ""
    line: int = 0


@dataclass
class ExtensionUsage:
    name: str = ""
    file: str = ""
    line: int = 0


@dataclass
class EnvRead:
    key: str = ""
    accessor: str = ""
    file: str = ""
    line: int = 0
    function_name: str | None = None


@dataclass
class TestEdge:
    test_func: str = ""
    target: str = ""
    file: str = ""
    line: int = 0


@dataclass
class ImplementsEdge:
    interface: str = ""
    concrete: str = ""
    file: str = ""
    line: int = 0


@dataclass
class MutationEdge:
    field: str = ""
    function_name: str = ""
    file: str = ""
    line: int = 0


@dataclass
class ErrorEdge:
    message: str = ""
    function_name: str = ""
    file: str = ""
    line: int = 0


@dataclass
class HttpCallEdge:
    source_file: str = ""
    source_line: int = 0
    function_name: str = ""
    method: str = ""
    url: str = ""
    static_segments: list[str] = field(default_factory=list)
    has_dynamic: bool = False


@dataclass
class Graph:
    schema_version: str = SCHEMA_VERSION
    generated_at: str = ""
    project_root: str = ""
    packages: list[PackageNode] = field(default_factory=list)
    files: list[FileNode] = field(default_factory=list)
    symbols: list[SymbolNode] = field(default_factory=list)
    calls: list[CallEdge] = field(default_factory=list)
    imports: list[ImportEdge] = field(default_factory=list)
    routes: list[HTTPRoute] = field(default_factory=list)
    env_reads: list[EnvRead] = field(default_factory=list)
    dependencies: list[Dependency] = field(default_factory=list)
    test_edges: list[TestEdge] = field(default_factory=list)
    implements: list[ImplementsEdge] = field(default_factory=list)
    mutations: list[MutationEdge] = field(default_factory=list)
    errors: list[ErrorEdge] = field(default_factory=list)
    blueprints: list[BlueprintDef] = field(default_factory=list)
    blueprint_registrations: list[BlueprintRegistration] = field(default_factory=list)
    template_refs: list[TemplateRef] = field(default_factory=list)
    extensions: list[ExtensionUsage] = field(default_factory=list)
    http_calls: list[HttpCallEdge] = field(default_factory=list)
    response_model_refs: list[ResponseModelRef] = field(default_factory=list)


def make_graph(*, project_root: str = "") -> Graph:
    return Graph(
        schema_version=SCHEMA_VERSION,
        generated_at=datetime.now(UTC).isoformat(),
        project_root=project_root,
    )


def make_symbol_node(**overrides: Any) -> SymbolNode:
    base: dict[str, Any] = {
        "id": _generate_id(),
        "kind": "function",
        "name": "",
        "package_name": "",
        "file": "",
        "line": 0,
        "end_line": 0,
        "is_exported": False,
    }
    base.update(overrides)
    return SymbolNode(**{k: v for k, v in base.items() if v is not None})


def make_package_node(**overrides: Any) -> PackageNode:
    base: dict[str, Any] = {
        "id": _generate_id(),
        "name": "",
        "import_path_best_effort": "",
        "dir": "",
        "files": [],
    }
    base.update(overrides)
    return PackageNode(**{k: v for k, v in base.items() if v is not None})


def make_file_node(**overrides: Any) -> FileNode:
    base: dict[str, Any] = {
        "id": _generate_id(),
        "path": "",
        "package_name": "",
        "lines": 0,
        "generated": False,
    }
    base.update(overrides)
    return FileNode(**{k: v for k, v in base.items() if v is not None})


def make_call_edge(**overrides: Any) -> CallEdge:
    base: dict[str, Any] = {
        "caller_symbol_id": "",
        "caller_name": "",
        "callee_raw": "",
        "file": "",
        "line": 0,
    }
    base.update(overrides)
    return CallEdge(**{k: v for k, v in base.items() if v is not None})


def make_import_edge(**overrides: Any) -> ImportEdge:
    base: dict[str, Any] = {
        "from_file": "",
        "from_package": "",
        "import_path": "",
        "is_default": False,
    }
    base.update(overrides)
    return ImportEdge(**{k: v for k, v in base.items() if v is not None})


def make_dependency(**overrides: Any) -> Dependency:
    base: dict[str, Any] = {"module": "", "version": ""}
    base.update(overrides)
    return Dependency(**{k: v for k, v in base.items() if v is not None})


def make_http_route(**overrides: Any) -> HTTPRoute:
    base: dict[str, Any] = {
        "method": "",
        "path": "",
        "handler": "",
        "file": "",
        "line": 0,
    }
    base.update(overrides)
    return HTTPRoute(**{k: v for k, v in base.items() if v is not None})


def make_env_read(**overrides: Any) -> EnvRead:
    base: dict[str, Any] = {
        "key": "",
        "accessor": "",
        "file": "",
        "line": 0,
    }
    base.update(overrides)
    return EnvRead(**{k: v for k, v in base.items() if v is not None})


def make_test_edge(**overrides: Any) -> TestEdge:
    base: dict[str, Any] = {
        "test_func": "",
        "target": "",
        "file": "",
        "line": 0,
    }
    base.update(overrides)
    return TestEdge(**{k: v for k, v in base.items() if v is not None})


def make_implements_edge(**overrides: Any) -> ImplementsEdge:
    base: dict[str, Any] = {"interface": "", "concrete": ""}
    base.update(overrides)
    return ImplementsEdge(**{k: v for k, v in base.items() if v is not None})


def make_mutation_edge(**overrides: Any) -> MutationEdge:
    base: dict[str, Any] = {
        "field": "",
        "function_name": "",
        "file": "",
        "line": 0,
    }
    base.update(overrides)
    return MutationEdge(**{k: v for k, v in base.items() if v is not None})


def make_error_edge(**overrides: Any) -> ErrorEdge:
    base: dict[str, Any] = {
        "message": "",
        "function_name": "",
        "file": "",
        "line": 0,
    }
    base.update(overrides)
    return ErrorEdge(**{k: v for k, v in base.items() if v is not None})


def make_http_call_edge(**overrides: Any) -> HttpCallEdge:
    base: dict[str, Any] = {
        "source_file": "",
        "source_line": 0,
        "function_name": "",
        "method": "",
        "url": "",
        "static_segments": [],
        "has_dynamic": False,
    }
    base.update(overrides)
    return HttpCallEdge(**{k: v for k, v in base.items() if v is not None})


def make_struct_field(**overrides: Any) -> StructField:
    base: dict[str, Any] = {"name": "", "type": ""}
    base.update(overrides)
    return StructField(**{k: v for k, v in base.items() if v is not None})


def make_blueprint_def(**overrides: Any) -> BlueprintDef:
    base: dict[str, Any] = {"name": "", "import_name": "", "file": "", "line": 0}
    base.update(overrides)
    return BlueprintDef(**{k: v for k, v in base.items() if v is not None})


def make_blueprint_registration(**overrides: Any) -> BlueprintRegistration:
    base: dict[str, Any] = {
        "app_var": "", "blueprint_var": "", "url_prefix": "", "file": "", "line": 0
    }
    base.update(overrides)
    return BlueprintRegistration(**{k: v for k, v in base.items() if v is not None})


def make_template_ref(**overrides: Any) -> TemplateRef:
    base: dict[str, Any] = {
        "template_path": "", "function_name": "", "file": "", "line": 0
    }
    base.update(overrides)
    return TemplateRef(**{k: v for k, v in base.items() if v is not None})


def make_extension_usage(**overrides: Any) -> ExtensionUsage:
    base: dict[str, Any] = {"name": "", "file": "", "line": 0}
    base.update(overrides)
    return ExtensionUsage(**{k: v for k, v in base.items() if v is not None})
