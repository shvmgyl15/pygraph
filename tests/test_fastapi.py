from __future__ import annotations

from pygraph.extractors.fastapi import extract_fastapi, _unpack_response_models


class TestUnpackResponseModels:
    def test_bare_name(self) -> None:
        assert _unpack_response_models("UserResponse") == ["UserResponse"]

    def test_list_wrapper(self) -> None:
        assert _unpack_response_models("list[UserResponse]") == ["UserResponse"]

    def test_optional_wrapper(self) -> None:
        assert _unpack_response_models("Optional[UserResponse]") == ["UserResponse"]

    def test_union_multi(self) -> None:
        res = _unpack_response_models("Union[UserResponse, ErrorResponse]")
        assert res == ["UserResponse", "ErrorResponse"]

    def test_nested_generics(self) -> None:
        res = _unpack_response_models("Optional[Union[UserResponse, ErrorResponse]]")
        assert res == ["UserResponse", "ErrorResponse"]

    def test_skip_container_types(self) -> None:
        res = _unpack_response_models("Optional[list[UserResponse]]")
        assert res == ["UserResponse"]

    def test_deduplicate(self) -> None:
        res = _unpack_response_models("Union[UserResponse, UserResponse]")
        assert res == ["UserResponse"]

    def test_invalid_syntax(self) -> None:
        assert _unpack_response_models("") == []
        assert _unpack_response_models("[[[") == []


class TestExtractFastAPI:
    def test_app_get_route(self) -> None:
        src = """
from fastapi import FastAPI

app = FastAPI()

@app.get("/users")
def list_users():
    pass
"""
        result = extract_fastapi(src, "main.py")
        assert len(result["routes"]) == 1
        r = result["routes"][0]
        assert r.method == "GET"
        assert r.path == "/users"
        assert r.handler == "main.py::list_users"
        assert r.response_model is None

    def test_app_post_with_response_model(self) -> None:
        src = """
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class UserResponse(BaseModel):
    id: int
    name: str

@app.post("/users", response_model=UserResponse)
def create_user():
    pass
"""
        result = extract_fastapi(src, "main.py")
        assert len(result["routes"]) == 1
        r = result["routes"][0]
        assert r.method == "POST"
        assert r.path == "/users"
        assert r.response_model == "UserResponse"

    def test_router_with_prefix(self) -> None:
        src = """
from fastapi import APIRouter, FastAPI

app = FastAPI()
router = APIRouter()

@router.get("/items")
def list_items():
    pass

app.include_router(router, prefix="/api")
"""
        result = extract_fastapi(src, "main.py")
        assert len(result["routes"]) == 1
        r = result["routes"][0]
        assert r.path == "/api/items"
        assert r.method == "GET"

    def test_tags_extracted(self) -> None:
        src = """
from fastapi import FastAPI

app = FastAPI()

@app.get("/health", tags=["health", "monitoring"])
def health():
    pass
"""
        result = extract_fastapi(src, "main.py")
        assert len(result["routes"]) == 1
        r = result["routes"][0]
        assert r.tags == ["health", "monitoring"]

    def test_websocket_method(self) -> None:
        src = """
from fastapi import FastAPI

app = FastAPI()

@app.websocket("/ws")
def websocket_endpoint():
    pass
"""
        result = extract_fastapi(src, "main.py")
        assert len(result["routes"]) == 1
        assert result["routes"][0].method == "WS"
        assert result["routes"][0].path == "/ws"

    def test_no_fastapi_app_returns_empty(self) -> None:
        src = "x = 1"
        result = extract_fastapi(src, "empty.py")
        assert len(result["routes"]) == 0
        assert len(result["response_model_refs"]) == 0

    def test_response_model_refs_created(self) -> None:
        src = """
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class UserResponse(BaseModel):
    id: int
    name: str

@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int):
    pass
"""
        from pygraph.extractors.symbols import extract_symbols

        symbols = extract_symbols(src, "main.py", "test")

        result = extract_fastapi(src, "main.py", symbols)
        assert len(result["response_model_refs"]) == 1
        ref = result["response_model_refs"][0]
        assert ref.model_name == "UserResponse"
        assert ref.method == "GET"
        assert ref.route_path == "/users/{user_id}"
        assert ref.wrapper is None

    def test_response_model_refs_list_wrapper(self) -> None:
        src = """
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class UserResponse(BaseModel):
    id: int

@app.get("/users", response_model=list[UserResponse])
def list_users():
    pass
"""
        from pygraph.extractors.symbols import extract_symbols

        symbols = extract_symbols(src, "main.py", "test")

        result = extract_fastapi(src, "main.py", symbols)
        assert len(result["response_model_refs"]) == 1
        ref = result["response_model_refs"][0]
        assert ref.model_name == "UserResponse"
        assert ref.wrapper == "List"

    def test_response_model_refs_optional_wrapper(self) -> None:
        src = """
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class UserResponse(BaseModel):
    id: int

@app.get("/users/{user_id}", response_model=Optional[UserResponse])
def get_user(user_id: int):
    pass
"""
        from pygraph.extractors.symbols import extract_symbols

        symbols = extract_symbols(src, "main.py", "test")

        result = extract_fastapi(src, "main.py", symbols)
        assert len(result["response_model_refs"]) == 1
        ref = result["response_model_refs"][0]
        assert ref.model_name == "UserResponse"
        assert ref.wrapper == "Optional"

    def test_no_ref_when_symbol_missing(self) -> None:
        src = """
from fastapi import FastAPI

app = FastAPI()

@app.get("/users", response_model=MissingModel)
def get_users():
    pass
"""
        result = extract_fastapi(src, "main.py")
        assert len(result["response_model_refs"]) == 0

    def test_include_router_prefix_joining(self) -> None:
        src = """
from fastapi import APIRouter, FastAPI

app = FastAPI()
router = APIRouter()

@router.get("/{item_id}")
def get_item(item_id: int):
    pass

app.include_router(router, prefix="/api/items")
"""
        result = extract_fastapi(src, "main.py")
        assert len(result["routes"]) == 1
        r = result["routes"][0]
        assert r.path == "/api/items/{item_id}"

    def test_multiple_http_methods(self) -> None:
        src = """
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def index(): pass

@app.post("/")
def create(): pass

@app.put("/{id}")
def update(id: int): pass

@app.delete("/{id}")
def delete(id: int): pass

@app.patch("/{id}")
def patch(id: int): pass
"""
        result = extract_fastapi(src, "main.py")
        methods = {r.method for r in result["routes"]}
        assert methods == {"GET", "POST", "PUT", "DELETE", "PATCH"}

    def test_router_separate_file_no_include_router(self) -> None:
        """Routes on a router in a separate file (no include_router) should still
        be extracted. The prefix will be empty since include_router is not in this file.
        This simulates the common pattern where main.py has app.include_router() and
        routes/users.py defines @router.get()."""
        src = """
from fastapi import APIRouter

router = APIRouter()

@router.get("/users")
def list_users():
    pass

@router.post("/users")
def create_user():
    pass
"""
        result = extract_fastapi(src, "routes/users.py")
        assert len(result["routes"]) == 2, \
            f"Expected 2 routes for separate-file router, got {len(result['routes'])}"
        paths = {r.path for r in result["routes"]}
        assert paths == {"/users"}, f"Expected paths {{'/users'}}, got {paths}"
        methods = {r.method for r in result["routes"]}
        assert methods == {"GET", "POST"}

    def test_add_api_route_basic(self) -> None:
        """Imperative app.add_api_route() should be detected."""
        src = """
from fastapi import FastAPI

app = FastAPI()

def health_handler():
    pass

app.add_api_route("/health", health_handler)
"""
        result = extract_fastapi(src, "main.py")
        assert len(result["routes"]) == 1, \
            f"Expected 1 route from add_api_route, got {len(result['routes'])}"
        r = result["routes"][0]
        assert r.method == "GET", f"Expected GET, got {r.method}"
        assert r.path == "/health"
        assert r.handler == "health_handler"

    def test_add_api_route_with_methods(self) -> None:
        """app.add_api_route() with explicit methods keyword."""
        src = """
from fastapi import FastAPI

app = FastAPI()

def handler():
    pass

app.add_api_route("/users", handler, methods=["POST", "PUT"])
"""
        result = extract_fastapi(src, "main.py")
        assert len(result["routes"]) == 2
        methods = {r.method for r in result["routes"]}
        assert methods == {"POST", "PUT"}
        assert all(r.path == "/users" for r in result["routes"])

    def test_add_api_route_with_response_model(self) -> None:
        """app.add_api_route() with response_model keyword."""
        src = """
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class ItemResponse(BaseModel):
    id: int

def get_item():
    pass

app.add_api_route("/items/{id}", get_item, response_model=ItemResponse)
"""
        result = extract_fastapi(src, "main.py")
        assert len(result["routes"]) == 1
        r = result["routes"][0]
        assert r.path == "/items/{id}"
        assert r.response_model == "ItemResponse"

    def test_add_websocket_route(self) -> None:
        """app.add_websocket_route() should produce WS method."""
        src = """
from fastapi import FastAPI

app = FastAPI()

def ws_handler():
    pass

app.add_websocket_route("/ws", ws_handler)
"""
        result = extract_fastapi(src, "main.py")
        assert len(result["routes"]) == 1
        r = result["routes"][0]
        assert r.method == "WS"
        assert r.path == "/ws"

    def test_add_api_route_on_router_with_prefix(self) -> None:
        """router.add_api_route() should apply include_router prefix."""
        src = """
from fastapi import APIRouter, FastAPI

app = FastAPI()
router = APIRouter()

def list_items():
    pass

router.add_api_route("/items", list_items)
app.include_router(router, prefix="/api/v1")
"""
        result = extract_fastapi(src, "main.py")
        assert len(result["routes"]) == 1
        r = result["routes"][0]
        assert r.path == "/api/v1/items"

    def test_add_api_route_on_router_no_prefix(self) -> None:
        """router.add_api_route() without include_router prefix should keep path as-is."""
        src = """
from fastapi import APIRouter

router = APIRouter()

def handler():
    pass

router.add_api_route("/data", handler)
"""
        result = extract_fastapi(src, "routes/data.py")
        assert len(result["routes"]) == 1
        r = result["routes"][0]
        assert r.path == "/data"
        assert r.method == "GET"
