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
