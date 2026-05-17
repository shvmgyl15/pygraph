from __future__ import annotations

import ast
from pathlib import Path

from pygraph.graph.types import Dependency, ImportEdge


def _import_edge_from_import(
    node: ast.Import,
    file_path: str,
    package_name: str,
) -> list[ImportEdge]:
    edges: list[ImportEdge] = []
    for alias in node.names:
        edges.append(
            ImportEdge(
                from_file=file_path,
                from_package=package_name,
                import_path=alias.name,
                alias=alias.asname,
                is_default=False,
            )
        )
    return edges


def _import_edge_from_importfrom(
    node: ast.ImportFrom,
    file_path: str,
    package_name: str,
) -> list[ImportEdge]:
    edges: list[ImportEdge] = []
    module = node.module or ""
    for alias in node.names:
        edges.append(
            ImportEdge(
                from_file=file_path,
                from_package=package_name,
                import_path=f"{module}.{alias.name}" if module else alias.name,
                alias=alias.asname,
                is_default=False,
            )
        )
    return edges


def extract_imports(
    source: str,
    file_path: str,
    package_name: str,
) -> list[ImportEdge]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    imports: list[ImportEdge] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(
                _import_edge_from_import(node, file_path, package_name)
            )
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            imports.extend(
                _import_edge_from_importfrom(node, file_path, package_name)
            )
    return imports


def extract_dependencies(root: str) -> list[Dependency]:
    deps: list[Dependency] = []
    root_path = Path(root)

    req_paths = [
        root_path / "requirements.txt",
        root_path / "requirements" / "base.txt",
        root_path / "requirements" / "prod.txt",
    ]

    for req_path in req_paths:
        if req_path.exists():
            try:
                text = req_path.read_text()
                for line in text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith("-"):
                        continue
                    if "==" in line:
                        module, version = line.split("==", 1)
                        deps.append(Dependency(module=module.strip(), version=version.strip()))
                    elif ">=" in line:
                        module, version = line.split(">=", 1)
                        deps.append(Dependency(module=module.strip(), version=version.strip()))
                    else:
                        deps.append(Dependency(module=line, version="*"))
            except OSError:
                pass

    pyproject_toml = root_path / "pyproject.toml"
    if pyproject_toml.exists() and not deps:
        try:
            import tomllib

            data = tomllib.loads(pyproject_toml.read_text())
            project = data.get("project", {})
            raw_deps: list[str] = project.get("dependencies", [])
            _dep_groups: dict[str, list[str]] = data.get("dependency-groups", {})  # noqa: F841
            for raw in raw_deps:
                if "==" in raw:
                    module, version = raw.split("==", 1)
                    deps.append(Dependency(module=module.strip(), version=version.strip()))
                elif ">=" in raw:
                    module, version = raw.split(">=", 1)
                    deps.append(Dependency(module=module.strip(), version=version.strip()))
                elif ">" in raw:
                    module, version = raw.split(">", 1)
                    deps.append(Dependency(module=module.strip(), version=version.strip()))
                else:
                    parts = raw.split()
                    if parts:
                        deps.append(Dependency(module=parts[0], version="*"))
        except (OSError, ImportError):
            pass

    return deps
