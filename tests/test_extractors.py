from __future__ import annotations

from pathlib import Path

from pygraph.extractors.calls import extract_calls
from pygraph.extractors.imports import extract_dependencies, extract_imports
from pygraph.extractors.symbols import extract_symbols


def _normalize_id(symbol_id: str) -> str:
    return symbol_id.split("::", 1)[-1]


class TestExtractSymbols:
    def test_function(self) -> None:
        src = "def foo(a, b): pass\n"
        symbols = extract_symbols(src, "test.py", "pkg")
        names = {s.name: s for s in symbols}
        assert "foo" in names
        s = names["foo"]
        assert s.kind == "function"
        assert s.is_exported is True
        assert s.arity == 2
        assert s.line == 1
        assert s.end_line == 1

    def test_async_function(self) -> None:
        src = "async def fetch(): pass\n"
        symbols = extract_symbols(src, "test.py", "pkg")
        s = symbols[0]
        assert s.name == "fetch"
        assert s.is_async is True
        assert s.kind == "function"

    def test_generator(self) -> None:
        src = "def gen(): yield 1\n"
        symbols = extract_symbols(src, "test.py", "pkg")
        s = symbols[0]
        assert s.is_generator is True

    def test_class_with_methods(self) -> None:
        src = """
class User:
    def __init__(self, name): pass
    @classmethod
    def create(cls): pass
    @staticmethod
    def validate(): pass
    @property
    def full_name(self): pass
"""
        symbols = extract_symbols(src, "test.py", "pkg")
        names = {s.name: s for s in symbols}
        assert "User" in names
        assert names["User"].kind == "class"
        assert "User" in names
        assert names["User"].struct_fields == []

        assert "__init__" in names
        assert names["__init__"].receiver == "User"
        assert names["__init__"].kind == "method"

        assert "create" in names
        assert names["create"].is_classmethod is True
        assert names["create"].receiver == "User"

        assert "validate" in names
        assert names["validate"].is_staticmethod is True

        assert "full_name" in names
        assert names["full_name"].is_property is True

    def test_decorators(self) -> None:
        src = """
@cache
@app.route('/')
def handler(): pass
"""
        symbols = extract_symbols(src, "test.py", "pkg")
        s = symbols[0]
        assert "cache" in s.decorators
        assert "app.route" in s.decorators

    def test_module_level_vars(self) -> None:
        src = """
NAME = "pygraph"
count: int = 0
_hidden = True
"""
        symbols = extract_symbols(src, "test.py", "pkg")
        names = {s.name: s for s in symbols}
        assert "NAME" in names
        assert names["NAME"].kind == "constant"
        assert names["NAME"].is_exported is True

        assert "count" in names
        assert names["count"].kind == "variable"
        assert names["count"].is_exported is True
        assert names["count"].type_annotation == "int"

        assert "_hidden" in names
        assert names["_hidden"].is_exported is False

    def test_exported_via_all(self) -> None:
        src = """
__all__ = ["helper"]
def helper(): pass
def _internal(): pass
"""
        symbols = extract_symbols(src, "test.py", "pkg")
        names = {s.name: s for s in symbols}
        assert names["helper"].is_exported is True
        assert names["_internal"].is_exported is False

    def test_syntax_error_returns_empty(self) -> None:
        src = "def foo( pass\n"
        symbols = extract_symbols(src, "test.py", "pkg")
        assert symbols == []

    def test_class_struct_fields(self) -> None:
        src = """
class User:
    name: str
    age: int
"""
        symbols = extract_symbols(src, "test.py", "pkg")
        s = next(s for s in symbols if s.name == "User")
        fields = s.struct_fields
        assert len(fields) == 2
        assert fields[0].name == "name"
        assert fields[0].type == "str"
        assert fields[1].name == "age"
        assert fields[1].type == "int"


class TestExtractCalls:
    def test_function_calls(self) -> None:
        src = """
def foo():
    bar()
    baz(1, 2)
"""
        calls = extract_calls(src, "test.py")
        assert len(calls) == 2
        assert all(c.caller_name == "foo" for c in calls)
        assert calls[0].callee_raw == "bar"
        assert calls[1].callee_raw == "baz"

    def test_method_calls(self) -> None:
        src = """
class Service:
    def run(self):
        self.prepare()
        self.execute(1)
"""
        calls = extract_calls(src, "test.py")
        assert len(calls) == 2
        assert all(c.caller_name == "run" for c in calls)
        assert calls[0].callee_raw == "self.prepare"

    def test_async_function_calls(self) -> None:
        src = """
async def fetch():
    await load()
    return result
"""
        calls = extract_calls(src, "test.py")
        assert len(calls) == 1
        assert calls[0].callee_raw == "load"


class TestExtractImports:
    def test_standard_import(self) -> None:
        src = "import os\nimport json as jsonmod\n"
        imports = extract_imports(src, "test.py", "pkg")
        paths = {i.import_path: i for i in imports}
        assert "os" in paths
        assert paths["os"].from_file == "test.py"

    def test_from_import(self) -> None:
        src = "from pathlib import Path\n"
        imports = extract_imports(src, "test.py", "pkg")
        assert len(imports) == 1
        assert imports[0].import_path == "pathlib.Path"

    def test_relative_import_skipped(self) -> None:
        src = "from . import sibling\nfrom .. import parent\n"
        imports = extract_imports(src, "test.py", "pkg")
        assert imports == []


class TestExtractDependencies:
    def test_requirements_txt(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text(
            "flask==3.0\nrequests>=2.28\n"
        )
        deps = extract_dependencies(str(tmp_path))
        modules = {d.module: d.version for d in deps}
        assert modules.get("flask") == "3.0"
        assert modules.get("requests") == "2.28"

    def test_pyproject_toml(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\ndependencies = ["typer>=0.12", "pydantic==2.0"]\n'
        )
        deps = extract_dependencies(str(tmp_path))
        assert len(deps) == 2

    def test_no_deps_file(self, tmp_path: Path) -> None:
        deps = extract_dependencies(str(tmp_path))
        assert deps == []
