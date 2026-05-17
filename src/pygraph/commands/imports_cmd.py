from __future__ import annotations

from pygraph.query import GraphQuery


def run(query: GraphQuery, file_path: str) -> None:
    imports = query.get_imports(file_path)
    if not imports:
        print(f"No imports found for '{file_path}'")
        return
    for imp in imports:
        alias = f" as {imp.alias}" if imp.alias else ""
        print(f"{imp.import_path}{alias}")
