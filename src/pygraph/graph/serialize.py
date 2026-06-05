from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from pygraph.graph.types import (
    SCHEMA_VERSION,
    BlueprintDef,
    BlueprintRegistration,
    CallEdge,
    Dependency,
    EnvRead,
    ErrorEdge,
    ExtensionUsage,
    FileNode,
    Graph,
    HttpCallEdge,
    HTTPRoute,
    ImplementsEdge,
    ImportEdge,
    MutationEdge,
    PackageNode,
    StructField,
    SymbolNode,
    TemplateRef,
    TestEdge,
)

ARRAY_FIELDS: set[str] = {
    "packages", "files", "symbols", "calls", "imports", "routes",
    "env_reads", "dependencies", "test_edges", "implements",
    "mutations", "errors", "blueprints", "blueprint_registrations",
    "template_refs", "extensions", "http_calls",
}

REQUIRED_FIELDS: set[str] = ARRAY_FIELDS | {"schema_version", "generated_at", "project_root"}


def _filter_none(obj: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in obj.items() if v is not None}


def graph_to_dict(graph: Graph) -> dict[str, Any]:
    return _filter_none({
        "schema_version": graph.schema_version,
        "generated_at": graph.generated_at,
        "project_root": graph.project_root,
        "packages": [_filter_none(asdict(p)) for p in graph.packages],
        "files": [_filter_none(asdict(f)) for f in graph.files],
        "symbols": [_filter_none(asdict(s)) for s in graph.symbols],
        "calls": [_filter_none(asdict(c)) for c in graph.calls],
        "imports": [_filter_none(asdict(i)) for i in graph.imports],
        "routes": [_filter_none(asdict(r)) for r in graph.routes],
        "env_reads": [_filter_none(asdict(e)) for e in graph.env_reads],
        "dependencies": [_filter_none(asdict(d)) for d in graph.dependencies],
        "test_edges": [_filter_none(asdict(t)) for t in graph.test_edges],
        "implements": [_filter_none(asdict(i)) for i in graph.implements],
        "mutations": [_filter_none(asdict(m)) for m in graph.mutations],
        "errors": [_filter_none(asdict(e)) for e in graph.errors],
        "blueprints": [_filter_none(asdict(b)) for b in graph.blueprints],
        "blueprint_registrations": [_filter_none(asdict(r)) for r in graph.blueprint_registrations],
        "template_refs": [_filter_none(asdict(t)) for t in graph.template_refs],
        "extensions": [_filter_none(asdict(e)) for e in graph.extensions],
        "http_calls": [_filter_none(asdict(h)) for h in graph.http_calls],
    })


def _dict_to_symbol(data: dict[str, Any]) -> SymbolNode:
    fields = data.copy()
    fields.setdefault("decorators", [])
    fields.setdefault("bases", [])
    fields.setdefault("struct_fields", [])
    fields.setdefault("embedded_types", [])
    raw_struct_fields = fields.get("struct_fields", [])
    fields["struct_fields"] = [
        StructField(**sf) if isinstance(sf, dict) else sf
        for sf in raw_struct_fields
    ]
    return SymbolNode(**{k: v for k, v in fields.items() if v is not None})


def dict_to_graph(data: dict[str, Any]) -> Graph:
    return Graph(
        schema_version=data["schema_version"],
        generated_at=data["generated_at"],
        project_root=data["project_root"],
        packages=[PackageNode(**p) for p in data["packages"]],
        files=[FileNode(**f) for f in data["files"]],
        symbols=[_dict_to_symbol(s) for s in data["symbols"]],
        calls=[CallEdge(**c) for c in data["calls"]],
        imports=[ImportEdge(**i) for i in data["imports"]],
        routes=[HTTPRoute(**r) for r in data["routes"]],
        env_reads=[EnvRead(**e) for e in data["env_reads"]],
        dependencies=[Dependency(**d) for d in data["dependencies"]],
        test_edges=[TestEdge(**t) for t in data["test_edges"]],
        implements=[ImplementsEdge(**im) for im in data["implements"]],
        mutations=[MutationEdge(**mu) for mu in data["mutations"]],
        errors=[ErrorEdge(**er) for er in data["errors"]],
        blueprints=[BlueprintDef(**b) for b in data.get("blueprints", [])],
        blueprint_registrations=[
            BlueprintRegistration(**r) for r in data.get("blueprint_registrations", [])
        ],
        template_refs=[TemplateRef(**t) for t in data.get("template_refs", [])],
        extensions=[ExtensionUsage(**e) for e in data.get("extensions", [])],
        http_calls=[HttpCallEdge(**h) for h in data.get("http_calls", [])],
    )


def serialize(graph: Graph) -> str:
    if graph.schema_version != SCHEMA_VERSION:
        msg = f"Graph version mismatch: expected {SCHEMA_VERSION}, got {graph.schema_version}"
        raise ValueError(msg)
    return json.dumps(graph_to_dict(graph), indent=2)


def _ensure_fields(parsed: dict[str, Any]) -> None:
    for field_name in REQUIRED_FIELDS:
        if field_name not in parsed:
            msg = f"Missing required field: {field_name}"
            raise ValueError(msg)
    for field_name in ARRAY_FIELDS:
        if not isinstance(parsed[field_name], list):
            msg = f"Field '{field_name}' must be a list"
            raise ValueError(msg)


def deserialize(json_str: str) -> Graph:
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON: {e}"
        raise ValueError(msg) from e

    if not isinstance(parsed, dict):
        msg = "Invalid graph structure: expected a JSON object"
        raise ValueError(msg)

    _ensure_fields(parsed)

    if parsed["schema_version"] != SCHEMA_VERSION:
        msg = (
            f"Graph version mismatch: expected {SCHEMA_VERSION}, "
            f"got {parsed['schema_version']}"
        )
        raise ValueError(msg)

    return dict_to_graph(parsed)


def write_graph(graph: Graph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(serialize(graph))


def read_graph(path: Path) -> Graph:
    with open(path) as f:
        return deserialize(f.read())
