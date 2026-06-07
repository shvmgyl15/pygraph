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
        assert all(c.caller_name == "Service.run" for c in calls)
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


class TestExtractFlask:
    def test_route_detection(self) -> None:
        src = """
@view.route('/users')
def list_users():
    pass

@view.route('/users/<int:id>', methods=['GET', 'POST'])
def get_user(id):
    pass
"""
        from pygraph.extractors.flask import extract_flask

        result = extract_flask(src, "views.py")
        assert len(result["routes"]) == 3
        assert result["routes"][0].path == "/users"
        assert result["routes"][0].method == "GET"
        assert result["routes"][0].handler == "views.py::list_users"
        assert result["routes"][1].method == "GET"
        assert result["routes"][1].path == "/users/<int:id>"
        assert result["routes"][2].method == "POST"
        assert result["routes"][2].path == "/users/<int:id>"

    def test_route_default_method(self) -> None:
        src = "@bp.route('/')\ndef index(): pass\n"
        from pygraph.extractors.flask import extract_flask

        result = extract_flask(src, "routes.py")
        assert len(result["routes"]) == 1
        assert result["routes"][0].method == "GET"
        assert result["routes"][0].path == "/"

    def test_blueprint_detection(self) -> None:
        src = """
bp = Blueprint('admin', __name__)
api = Blueprint('api', 'api_module')
"""
        from pygraph.extractors.flask import extract_flask

        result = extract_flask(src, "blueprints.py")
        assert len(result["blueprints"]) == 2
        assert result["blueprints"][0].name == "admin"
        assert result["blueprints"][0].import_name == ""
        assert result["blueprints"][1].name == "api"
        assert result["blueprints"][1].import_name == "api_module"

    def test_blueprint_registration(self) -> None:
        src = """
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(api_bp)
"""
        from pygraph.extractors.flask import extract_flask

        result = extract_flask(src, "app.py")
        assert len(result["blueprint_registrations"]) == 2
        reg = result["blueprint_registrations"][0]
        assert reg.app_var == "app"
        assert reg.blueprint_var == "admin_bp"
        assert reg.url_prefix == "/admin"
        reg2 = result["blueprint_registrations"][1]
        assert reg2.blueprint_var == "api_bp"
        assert reg2.url_prefix == ""

    def test_template_rendering(self) -> None:
        src = """
def dashboard():
    return render_template('dashboard.html', user=user)

def email():
    return render_template_string('<p>Hello</p>')
"""
        from pygraph.extractors.flask import extract_flask

        result = extract_flask(src, "views.py")
        assert len(result["template_refs"]) == 2
        assert result["template_refs"][0].template_path == "dashboard.html"
        assert result["template_refs"][0].function_name == "dashboard"
        assert result["template_refs"][1].template_path == "<p>Hello</p>"
        assert result["template_refs"][1].function_name == "email"

    def test_error_handler(self) -> None:
        src = """
@app.errorhandler(404)
def not_found(error):
    return 'Not Found', 404

@app.errorhandler(Exception)
def server_error(error):
    return 'Server Error', 500
"""
        from pygraph.extractors.flask import extract_flask

        result = extract_flask(src, "app.py")
        assert len(result["error_handlers"]) == 2
        assert result["error_handlers"][0].method == "ERRORHANDLER"
        assert result["error_handlers"][0].path == "404"
        assert result["error_handlers"][0].handler == "app.py::not_found"
        assert result["error_handlers"][1].path == "Exception"

    def test_cli_command(self) -> None:
        src = """
@app.cli.command('seed-db')
def seed_database():
    pass

@app.cli.command()
def cleanup():
    pass
"""
        from pygraph.extractors.flask import extract_flask

        result = extract_flask(src, "app.py")
        assert len(result["cli_commands"]) == 2
        assert result["cli_commands"][0].method == "CLI"
        assert result["cli_commands"][0].path == "seed-db"
        assert result["cli_commands"][0].handler == "app.py::seed_database"
        assert result["cli_commands"][1].path == "cleanup"

    def test_extension_detection(self) -> None:
        src = """
from flask_sqlalchemy import SQLAlchemy
import flask_migrate
from flask_login import LoginManager

db = SQLAlchemy()
db.init_app(app)
migrate.init_app(app)
"""
        from pygraph.extractors.flask import extract_flask

        result = extract_flask(src, "app.py")
        names = {e.name for e in result["extensions"]}
        assert "flask_sqlalchemy" in names
        assert "flask_migrate" in names
        assert "flask_login" in names

    def test_syntax_error_returns_empty(self) -> None:
        from pygraph.extractors.flask import extract_flask

        result = extract_flask("def foo( pass\n", "bad.py")
        assert result["routes"] == []
        assert result["blueprints"] == []
        assert result["template_refs"] == []

    def test_flask_restful_add_resource_single_path(self) -> None:
        src = """
from flask_restful import Resource, Api

api = Api(app)

class UserResource(Resource):
    def get(self, id):
        pass
    def post(self):
        pass

api.add_resource(UserResource, '/users/<id>')
"""
        from pygraph.extractors.flask import extract_flask

        result = extract_flask(src, "app.py")
        routes = [r for r in result["routes"] if r.method == "WRAPPER" or r.method in ("GET", "POST", "PUT", "DELETE")]
        matching = [r for r in routes if r.path == "/users/<id>"]
        assert len(matching) == 2
        methods = {r.method for r in matching}
        assert methods == {"GET", "POST"}
        assert all(r.handler == "app.py::UserResource" for r in matching)

    def test_flask_restful_add_resource_multi_path(self) -> None:
        src = """
from flask_restful import Resource, Api

api = Api(app)

class ItemResource(Resource):
    def get(self):
        pass
    def delete(self):
        pass

api.add_resource(ItemResource, '/items', '/items/<id>')
"""
        from pygraph.extractors.flask import extract_flask

        result = extract_flask(src, "app.py")
        matching = [r for r in result["routes"] if "ItemResource" in r.handler]
        assert len(matching) == 4  # 2 paths × 2 methods
        paths = {r.path for r in matching}
        assert paths == {"/items", "/items/<id>"}
        methods = {r.method for r in matching}
        assert methods == {"GET", "DELETE"}

    def test_flask_restful_no_methods_no_crash(self) -> None:
        src = """
api = Api(app)
api.add_resource(PlainClass, '/plain')
"""
        from pygraph.extractors.flask import extract_flask

        result = extract_flask(src, "app.py")
        matching = [r for r in result["routes"] if r.path == "/plain"]
        assert len(matching) == 1
        assert matching[0].method == "GET"

    def test_flask_restful_not_add_resource_not_detected(self) -> None:
        src = """
api.add_url_rule('/regular', view_func=handler)
"""
        from pygraph.extractors.flask import extract_flask

        result = extract_flask(src, "app.py")
        assert len(result["routes"]) == 1
        assert result["routes"][0].path == "/regular"


class TestComplexityExtraction:
    def test_base_complexity_one(self) -> None:
        src = "def foo():\n    pass\n"
        symbols = extract_symbols(src, "test.py", "pkg")
        assert symbols[0].complexity == 1

    def test_if_adds_one(self) -> None:
        src = "def foo(x):\n    if x > 0:\n        return x\n"
        symbols = extract_symbols(src, "test.py", "pkg")
        assert symbols[0].complexity == 2

    def test_if_elif_adds_two(self) -> None:
        src = "def foo(x):\n    if x > 0:\n        return 1\n    elif x < 0:\n        return -1\n"
        symbols = extract_symbols(src, "test.py", "pkg")
        assert symbols[0].complexity == 3

    def test_loop_adds_one(self) -> None:
        src = "def foo(items):\n    for i in items:\n        pass\n"
        symbols = extract_symbols(src, "test.py", "pkg")
        assert symbols[0].complexity == 2

    def test_while_adds_one(self) -> None:
        src = "def foo():\n    while True:\n        break\n"
        symbols = extract_symbols(src, "test.py", "pkg")
        assert symbols[0].complexity == 2

    def test_except_adds_one_per_handler(self) -> None:
        src = (
            "def foo():\n"
            "    try:\n"
            "        pass\n"
            "    except ValueError:\n"
            "        pass\n"
            "    except TypeError:\n"
            "        pass\n"
        )
        symbols = extract_symbols(src, "test.py", "pkg")
        assert symbols[0].complexity == 3

    def test_and_or_adds_operators(self) -> None:
        src = "def foo(a, b, c):\n    if a and b or c:\n        pass\n"
        symbols = extract_symbols(src, "test.py", "pkg")
        assert symbols[0].complexity == 4  # 1 base + 1 if + 1 and + 1 or

    def test_assert_adds_one(self) -> None:
        src = "def foo(x):\n    assert x > 0\n"
        symbols = extract_symbols(src, "test.py", "pkg")
        assert symbols[0].complexity == 2

    def test_comprehension_if_adds_one(self) -> None:
        src = "def foo(items):\n    return [x for x in items if x > 0]\n"
        symbols = extract_symbols(src, "test.py", "pkg")
        assert symbols[0].complexity == 2

    def test_class_methods_have_complexity(self) -> None:
        src = """
class Service:
    def simple(self):
        pass
    def complex(self, x):
        if x:
            return 1
        return 0
"""
        symbols = extract_symbols(src, "test.py", "pkg")
        names = {s.name: s for s in symbols}
        assert names.get("simple") is not None
        assert names.get("complex") is not None
        assert names["simple"].complexity == 1
        assert names["complex"].complexity == 2
