from __future__ import annotations

from pathlib import Path

from pygraph.extractors.calls import extract_calls
from pygraph.extractors.imports import extract_dependencies, extract_imports
from pygraph.extractors.symbols import extract_symbols
from pygraph.graph.serialize import write_graph
from pygraph.graph.types import (
    CallEdge,
    FileNode,
    Graph,
    ImportEdge,
    SymbolNode,
    make_graph,
    make_package_node,
)
from pygraph.scanner.walker import scan_files


def build_graph(root: str) -> Graph:
    root_path = Path(root).resolve()
    scan_result = scan_files(root)

    pkg_name = root_path.name
    py_files = [f for f in scan_result.files if f.kind == "py"]

    file_nodes: list[FileNode] = []
    all_symbols: list[SymbolNode] = []
    all_calls: list[CallEdge] = []
    all_imports: list[ImportEdge] = []

    for sf in py_files:
        try:
            source = Path(sf.path).read_text()
        except OSError:
            continue

        symbols = extract_symbols(source, sf.relative_path, pkg_name)
        calls = extract_calls(source, sf.relative_path)
        imports = extract_imports(source, sf.relative_path, pkg_name)

        all_symbols.extend(symbols)
        all_calls.extend(calls)
        all_imports.extend(imports)

        file_nodes.append(
            FileNode(
                id=sf.relative_path,
                path=sf.relative_path,
                package_name=pkg_name,
                lines=len(source.split("\n")),
                generated=sf.is_generated,
            )
        )

    package = make_package_node(
        name=pkg_name,
        import_path_best_effort=pkg_name,
        dir=str(root_path),
        files=[sf.relative_path for sf in scan_result.files],
    )

    dependencies = extract_dependencies(root)

    graph = make_graph(project_root=str(root_path))
    graph.packages = [package]
    graph.files = file_nodes
    graph.symbols = all_symbols
    graph.calls = all_calls
    graph.imports = all_imports
    graph.dependencies = dependencies

    return graph


def build_and_write(root: str) -> Path:
    graph = build_graph(root)
    out_path = Path(root) / ".pygraph" / "graph.json"
    write_graph(graph, out_path)
    return out_path
