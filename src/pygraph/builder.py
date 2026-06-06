from __future__ import annotations

import importlib.util
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

from pygraph.config import get_plugins
from pygraph.extractors.calls import extract_calls
from pygraph.extractors.env import extract_env_reads
from pygraph.extractors.errors import extract_errors
from pygraph.extractors.flask import extract_flask
from pygraph.extractors.http_calls import extract_http_calls
from pygraph.extractors.implements import extract_implements
from pygraph.extractors.imports import extract_dependencies, extract_imports
from pygraph.extractors.symbols import extract_symbols
from pygraph.extractors.tests import extract_test_edges
from pygraph.graph.cache import BuildCache
from pygraph.graph.serialize import read_graph, write_graph
from pygraph.graph.types import (
    BlueprintDef,
    BlueprintRegistration,
    CallEdge,
    EnvRead,
    ErrorEdge,
    ExtensionUsage,
    FileNode,
    Graph,
    HttpCallEdge,
    HTTPRoute,
    ImplementsEdge,
    ImportEdge,
    SymbolNode,
    TemplateRef,
    TestEdge,
    make_graph,
    make_package_node,
)
from pygraph.scanner.walker import ScannedFile, ScanResult, scan_files


def _get_file_mtime_size(path: str) -> tuple[float, int]:
    p = Path(path)
    stat = p.stat()
    return stat.st_mtime_ns, stat.st_size


_ParseResult = tuple[
    list[SymbolNode],
    list[CallEdge],
    list[ImportEdge],
    list[HTTPRoute],
    list[HTTPRoute],
    list[HTTPRoute],
    list[BlueprintDef],
    list[BlueprintRegistration],
    list[TemplateRef],
    list[ExtensionUsage],
    list[EnvRead],
    list[ErrorEdge],
    list[TestEdge],
    list[ImplementsEdge],
    list[HttpCallEdge],
    FileNode,
]


def _parse_source(
    source: str, relative_path: str, pkg_name: str
) -> _ParseResult:
    symbols = extract_symbols(source, relative_path, pkg_name)
    calls = extract_calls(source, relative_path)
    imports = extract_imports(source, relative_path, pkg_name)
    flask = extract_flask(source, relative_path)
    env_reads = extract_env_reads(source, relative_path)
    errors = extract_errors(source, relative_path)
    test_edges = extract_test_edges(source, relative_path)
    implements = extract_implements(source, relative_path)
    http_calls = extract_http_calls(source, relative_path)

    file_node = FileNode(
        id=relative_path,
        path=relative_path,
        package_name=pkg_name,
        lines=len(source.split("\n")),
        generated=False,
    )

    return (
        symbols,
        calls,
        imports,
        flask["routes"],
        flask["error_handlers"],
        flask["cli_commands"],
        flask["blueprints"],
        flask["blueprint_registrations"],
        flask["template_refs"],
        flask["extensions"],
        env_reads,
        errors,
        test_edges,
        implements,
        http_calls,
        file_node,
    )


def _parse_file(
    sf: ScannedFile, pkg_name: str
) -> _ParseResult:
    source = Path(sf.path).read_text()
    result = _parse_source(source, sf.relative_path, pkg_name)
    result[-1].generated = sf.is_generated
    return result


def _build_full(root: str, scan_result: ScanResult) -> Graph:
    root_path = Path(root).resolve()
    pkg_name = root_path.name
    py_files = [f for f in scan_result.files if f.kind == "py"]

    all_symbols: list[SymbolNode] = []
    all_calls: list[CallEdge] = []
    all_imports: list[ImportEdge] = []
    all_routes: list[HTTPRoute] = []
    all_error_handlers: list[HTTPRoute] = []
    all_cli_commands: list[HTTPRoute] = []
    all_blueprints: list[BlueprintDef] = []
    all_blueprint_registrations: list[BlueprintRegistration] = []
    all_template_refs: list[TemplateRef] = []
    all_extensions: list[ExtensionUsage] = []
    all_env_reads: list[EnvRead] = []
    all_errors: list[ErrorEdge] = []
    all_test_edges: list[TestEdge] = []
    all_implements: list[ImplementsEdge] = []
    all_http_calls: list[HttpCallEdge] = []
    file_nodes: list[FileNode] = []

    for sf in py_files:
        try:
            result = _parse_file(sf, pkg_name)
        except Exception:
            continue

        (
            symbols,
            calls,
            imports,
            routes,
            error_handlers,
            cli_commands,
            blueprints,
            blueprint_registrations,
            template_refs,
            extensions,
            env_reads,
            errors,
            test_edges,
            implements,
            http_calls,
            file_node,
        ) = result

        all_symbols.extend(symbols)
        all_calls.extend(calls)
        all_imports.extend(imports)
        all_routes.extend(routes)
        all_error_handlers.extend(error_handlers)
        all_cli_commands.extend(cli_commands)
        all_blueprints.extend(blueprints)
        all_blueprint_registrations.extend(blueprint_registrations)
        all_template_refs.extend(template_refs)
        all_extensions.extend(extensions)
        all_env_reads.extend(env_reads)
        all_errors.extend(errors)
        all_test_edges.extend(test_edges)
        all_implements.extend(implements)
        all_http_calls.extend(http_calls)
        file_nodes.append(file_node)

    all_routes.extend(all_error_handlers)
    all_routes.extend(all_cli_commands)

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
    graph.routes = all_routes
    graph.blueprints = all_blueprints
    graph.blueprint_registrations = all_blueprint_registrations
    graph.template_refs = all_template_refs
    graph.extensions = all_extensions
    graph.env_reads = all_env_reads
    graph.errors = all_errors
    graph.test_edges = all_test_edges
    graph.implements = all_implements
    graph.http_calls = all_http_calls

    return graph


def _index_by_file(objs: list[Any], file_attr: str) -> dict[str, list[Any]]:
    idx: dict[str, list[Any]] = {}
    for o in objs:
        key = getattr(o, file_attr)
        idx.setdefault(key, []).append(o)
    return idx


def _merge_incremental(
    root_path: Path,
    scan_result: ScanResult,
    old_graph: Graph,
    cache: BuildCache,
    cache_path: Path,
) -> Graph:
    pkg_name = root_path.name
    py_files = [f for f in scan_result.files if f.kind == "py"]
    scanned_paths = {sf.relative_path for sf in py_files}

    old_file_paths = {f.path for f in old_graph.files}

    changed_paths: set[str] = set()
    unchanged_paths: set[str] = set()

    for sf in py_files:
        mtime_ns, size = _get_file_mtime_size(sf.path)
        if cache.is_changed(sf.relative_path, mtime_ns, size):
            changed_paths.add(sf.relative_path)
        else:
            unchanged_paths.add(sf.relative_path)
        cache.set(sf.relative_path, mtime_ns, size)

    deleted_paths = old_file_paths - scanned_paths
    for p in deleted_paths:
        cache.remove(p)

    old_symbols_by_file = _index_by_file(old_graph.symbols, "file")
    old_calls_by_file = _index_by_file(old_graph.calls, "file")
    old_imports_by_file = _index_by_file(old_graph.imports, "from_file")
    old_routes_by_file = _index_by_file(old_graph.routes, "file")
    old_blueprints_by_file = _index_by_file(old_graph.blueprints, "file")
    old_blueprint_regs_by_file = _index_by_file(
        old_graph.blueprint_registrations, "file"
    )
    old_template_refs_by_file = _index_by_file(old_graph.template_refs, "file")
    old_extensions_by_file = _index_by_file(old_graph.extensions, "file")
    old_env_reads_by_file = _index_by_file(old_graph.env_reads, "file")
    old_errors_by_file = _index_by_file(old_graph.errors, "file")
    old_test_edges_by_file = _index_by_file(old_graph.test_edges, "file")
    old_implements_by_file = _index_by_file(old_graph.implements, "file")
    old_http_calls_by_file = _index_by_file(old_graph.http_calls, "source_file")

    all_symbols: list[SymbolNode] = []
    all_calls: list[CallEdge] = []
    all_imports: list[ImportEdge] = []
    all_routes: list[HTTPRoute] = []
    all_blueprints: list[BlueprintDef] = []
    all_blueprint_registrations: list[BlueprintRegistration] = []
    all_template_refs: list[TemplateRef] = []
    all_extensions: list[ExtensionUsage] = []
    all_env_reads: list[EnvRead] = []
    all_errors: list[ErrorEdge] = []
    all_test_edges: list[TestEdge] = []
    all_implements: list[ImplementsEdge] = []
    all_http_calls: list[HttpCallEdge] = []
    file_nodes: list[FileNode] = []

    for sf in py_files:
        rel = sf.relative_path

        if rel in unchanged_paths:
            all_symbols.extend(old_symbols_by_file.get(rel, []))
            all_calls.extend(old_calls_by_file.get(rel, []))
            all_imports.extend(old_imports_by_file.get(rel, []))
            all_routes.extend(old_routes_by_file.get(rel, []))
            all_blueprints.extend(old_blueprints_by_file.get(rel, []))
            all_blueprint_registrations.extend(
                old_blueprint_regs_by_file.get(rel, [])
            )
            all_template_refs.extend(old_template_refs_by_file.get(rel, []))
            all_extensions.extend(old_extensions_by_file.get(rel, []))
            all_env_reads.extend(old_env_reads_by_file.get(rel, []))
            all_errors.extend(old_errors_by_file.get(rel, []))
            all_test_edges.extend(old_test_edges_by_file.get(rel, []))
            all_implements.extend(old_implements_by_file.get(rel, []))
            all_http_calls.extend(old_http_calls_by_file.get(rel, []))
            old_fn = next(
                (f for f in old_graph.files if f.path == rel), None
            )
            if old_fn:
                file_nodes.append(old_fn)
            continue

        try:
            result = _parse_file(sf, pkg_name)
        except Exception:
            continue

        (
            symbols,
            calls,
            imports,
            routes,
            error_handlers,
            cli_commands,
            blueprints,
            blueprint_registrations,
            template_refs,
            extensions,
            env_reads,
            errors,
            test_edges,
            implements,
            http_calls,
            file_node,
        ) = result

        all_symbols.extend(symbols)
        all_calls.extend(calls)
        all_imports.extend(imports)
        all_routes.extend(routes)
        all_routes.extend(error_handlers)
        all_routes.extend(cli_commands)
        all_blueprints.extend(blueprints)
        all_blueprint_registrations.extend(blueprint_registrations)
        all_template_refs.extend(template_refs)
        all_extensions.extend(extensions)
        all_env_reads.extend(env_reads)
        all_errors.extend(errors)
        all_test_edges.extend(test_edges)
        all_implements.extend(implements)
        all_http_calls.extend(http_calls)
        file_nodes.append(file_node)

    package = make_package_node(
        name=pkg_name,
        import_path_best_effort=pkg_name,
        dir=str(root_path),
        files=[sf.relative_path for sf in scan_result.files],
    )

    dependencies = extract_dependencies(str(root_path))

    graph = make_graph(project_root=str(root_path))
    graph.packages = [package]
    graph.files = file_nodes
    graph.symbols = all_symbols
    graph.calls = all_calls
    graph.imports = all_imports
    graph.dependencies = dependencies
    graph.routes = all_routes
    graph.blueprints = all_blueprints
    graph.blueprint_registrations = all_blueprint_registrations
    graph.template_refs = all_template_refs
    graph.extensions = all_extensions
    graph.env_reads = all_env_reads
    graph.errors = all_errors
    graph.test_edges = all_test_edges
    graph.implements = all_implements
    graph.http_calls = all_http_calls

    cache.save(cache_path)
    return graph


def _run_plugins(graph: Graph, root: str) -> None:
    plugins = get_plugins(root)
    if not plugins:
        return
    root_path = Path(root).resolve()
    for plugin_rel in plugins:
        plugin_path = (root_path / plugin_rel).resolve()
        if not plugin_path.exists():
            print(f"[pygraph] plugin not found: {plugin_path}", file=sys.stderr)
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                f"_pygraph_plugin_{plugin_path.stem}", plugin_path
            )
            if spec is None or spec.loader is None:
                print(f"[pygraph] failed to load plugin: {plugin_path}", file=sys.stderr)
                continue
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod.__name__] = mod
            spec.loader.exec_module(mod)
            if not hasattr(mod, "run"):
                print(
                    f"[pygraph] plugin {plugin_path} has no run(graph) function",
                    file=sys.stderr,
                )
                continue
            mod.run(graph)
        except Exception:
            print(
                f"[pygraph] plugin {plugin_path} raised an error:",
                file=sys.stderr,
            )
            traceback.print_exc(file=sys.stderr)


def build_graph(root: str, incremental: bool = True) -> Graph:
    root_path = Path(root).resolve()
    scan_result = scan_files(root)

    if incremental:
        graph_path = root_path / ".pygraph" / "graph.json"
        cache_path = root_path / ".pygraph" / ".build_cache.json"

        if graph_path.exists() and cache_path.exists():
            old_graph = read_graph(graph_path)
            old_cache = BuildCache.load(cache_path)
            graph = _merge_incremental(
                root_path, scan_result, old_graph, old_cache, cache_path
            )
            _run_plugins(graph, root)
            return graph

    graph = _build_full(root, scan_result)
    _run_plugins(graph, root)
    return graph


def build_graph_from_ref(ref: str, root: str) -> Graph:
    root_path = Path(root).resolve()
    if not root_path.exists():
        raise ValueError(f"Root path '{root}' does not exist")
    pkg_name = root_path.name

    try:
        result = subprocess.run(
            ["git", "ls-tree", "-r", ref, "--name-only"],
            capture_output=True, text=True, timeout=30,
            cwd=str(root_path),
        )
        if result.returncode != 0:
            raise ValueError(f"Could not list files at ref '{ref}'")
        py_files = [f for f in result.stdout.splitlines() if f.endswith(".py")]
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        raise ValueError(f"Could not list files at ref '{ref}'") from None

    all_symbols: list[SymbolNode] = []
    all_calls: list[CallEdge] = []
    all_imports: list[ImportEdge] = []
    all_routes: list[HTTPRoute] = []
    all_error_handlers: list[HTTPRoute] = []
    all_cli_commands: list[HTTPRoute] = []
    all_blueprints: list[BlueprintDef] = []
    all_blueprint_registrations: list[BlueprintRegistration] = []
    all_template_refs: list[TemplateRef] = []
    all_extensions: list[ExtensionUsage] = []
    all_env_reads: list[EnvRead] = []
    all_errors: list[ErrorEdge] = []
    all_test_edges: list[TestEdge] = []
    all_implements: list[ImplementsEdge] = []
    all_http_calls: list[HttpCallEdge] = []
    file_nodes: list[FileNode] = []

    for rel_path in py_files:
        try:
            content = subprocess.run(
                ["git", "show", f"{ref}:{rel_path}"],
                capture_output=True, text=True, timeout=10,
                cwd=str(root_path),
            )
            if content.returncode != 0 or not content.stdout:
                continue
            source = content.stdout
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            continue

        parsed = _parse_source(source, rel_path, pkg_name)

        (
            symbols, calls, imports,
            routes, error_handlers, cli_commands,
            blueprints, blueprint_registrations, template_refs, extensions,
            env_reads, errors, test_edges, implements, http_calls, file_node,
        ) = parsed

        all_symbols.extend(symbols)
        all_calls.extend(calls)
        all_imports.extend(imports)
        all_routes.extend(routes)
        all_error_handlers.extend(error_handlers)
        all_cli_commands.extend(cli_commands)
        all_blueprints.extend(blueprints)
        all_blueprint_registrations.extend(blueprint_registrations)
        all_template_refs.extend(template_refs)
        all_extensions.extend(extensions)
        all_env_reads.extend(env_reads)
        all_errors.extend(errors)
        all_test_edges.extend(test_edges)
        all_implements.extend(implements)
        all_http_calls.extend(http_calls)
        file_nodes.append(file_node)

    all_routes.extend(all_error_handlers)
    all_routes.extend(all_cli_commands)

    package = make_package_node(
        name=pkg_name,
        import_path_best_effort=pkg_name,
        dir=str(root_path),
        files=py_files,
    )

    graph = make_graph(project_root=str(root_path))
    graph.packages = [package]
    graph.files = file_nodes
    graph.symbols = all_symbols
    graph.calls = all_calls
    graph.imports = all_imports
    graph.routes = all_routes
    graph.blueprints = all_blueprints
    graph.blueprint_registrations = all_blueprint_registrations
    graph.template_refs = all_template_refs
    graph.extensions = all_extensions
    graph.env_reads = all_env_reads
    graph.errors = all_errors
    graph.test_edges = all_test_edges
    graph.implements = all_implements
    graph.http_calls = all_http_calls

    return graph


def resolve_git_ref(ref: str, root: str = "") -> str | None:
    try:
        cwd = root if root and Path(root).exists() else None
        result = subprocess.run(
            ["git", "rev-parse", ref],
            capture_output=True, text=True, timeout=10,
            cwd=cwd,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return None


def build_and_write(root: str, incremental: bool = True) -> Path:
    graph = build_graph(root, incremental)
    out_path = Path(root) / ".pygraph" / "graph.json"
    write_graph(graph, out_path)

    cache_path = Path(root) / ".pygraph" / ".build_cache.json"
    if not incremental or not cache_path.exists():
        cache = BuildCache({})
        try:
            scan_result = scan_files(root)
            for sf in scan_result.files:
                if sf.kind == "py":
                    try:
                        mtime_ns, size = _get_file_mtime_size(sf.path)
                        cache.set(sf.relative_path, mtime_ns, size)
                    except OSError:
                        pass
        except OSError:
            pass
        cache.save(cache_path)

    return out_path
