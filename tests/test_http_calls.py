from __future__ import annotations

from pygraph.extractors.http_calls import extract_http_calls


class TestExtractHttpCalls:
    def test_requests_get(self) -> None:
        src = """
import requests

def fetch():
    resp = requests.get("https://api.example.com/users")
    return resp.json()
"""
        calls = extract_http_calls(src, "main.py")
        assert len(calls) == 1
        assert calls[0].method == "GET"
        assert calls[0].url == "https://api.example.com/users"
        assert calls[0].function_name == "fetch"

    def test_httpx_client(self) -> None:
        src = """
import httpx

def fetch():
    client = httpx.Client()
    resp = client.get("https://api.example.com/users")
    return resp.json()
"""
        calls = extract_http_calls(src, "main.py")
        assert len(calls) == 1
        assert calls[0].method == "GET"
        assert calls[0].url == "https://api.example.com/users"

    def test_self_client_attribute_chain(self) -> None:
        """Attribute chain like self.client.get(url) should be detected."""
        src = """
import httpx

class APIClient:
    def __init__(self):
        self._client = httpx.Client()

    def fetch_users(self):
        return self._client.get("https://api.example.com/users")
"""
        calls = extract_http_calls(src, "main.py")
        assert len(calls) == 1, f"Expected 1 call, got {len(calls)}"
        assert calls[0].method == "GET"
        assert calls[0].url == "https://api.example.com/users"
        assert calls[0].function_name == "fetch_users"

    def test_self_http_post_attribute_chain(self) -> None:
        """Attribute chain like self.http.post(url) should be detected."""
        src = """
import httpx

class Service:
    def __init__(self):
        self.http = httpx.Client()

    def create_item(self, data):
        return self.http.post("https://api.example.com/items", json=data)
"""
        calls = extract_http_calls(src, "main.py")
        assert len(calls) == 1
        assert calls[0].method == "POST"
        assert calls[0].url == "https://api.example.com/items"
        assert calls[0].function_name == "create_item"

    def test_self_session_put_attribute_chain(self) -> None:
        """Attribute chain like self.session.put(url) should be detected."""
        src = """
import httpx

class Worker:
    def __init__(self):
        self.session = httpx.Client()

    def update(self, item_id):
        return self.session.put(f"https://api.example.com/items/{item_id}")
"""
        calls = extract_http_calls(src, "main.py")
        assert len(calls) == 1
        assert calls[0].method == "PUT"
        assert calls[0].has_dynamic is True
        assert calls[0].function_name == "update"

    def test_async_with_self_session(self) -> None:
        """async with self.session.get(url) should be detected."""
        src = """
import aiohttp

class Worker:
    def __init__(self):
        self.session = aiohttp.ClientSession()

    async def fetch(self):
        async with self.session.get("https://api.example.com/data") as resp:
            return await resp.json()
"""
        calls = extract_http_calls(src, "main.py")
        assert len(calls) == 1
        assert calls[0].method == "GET"
        assert calls[0].function_name == "fetch"

    def test_nested_attribute_chain(self) -> None:
        """Deep attribute chains like self.client.api.get(url) should be detected."""
        src = """
import httpx

class Deep:
    def __init__(self):
        self.client = httpx.Client()

    def fetch(self):
        return self.client.api.get("https://api.example.com/data")
"""
        calls = extract_http_calls(src, "main.py")
        # Note: self.client.api.get(...) produces ast.Attribute(value=ast.Attribute(...), attr='get')
        # The obj is self.client.api which is an Attribute chain. This should match.
        assert len(calls) == 1
        assert calls[0].method == "GET"
        assert calls[0].function_name == "fetch"

    # --- Any-name bare wrapper support (Phase 1 fix) ---

    def test_bare_name_wrapper_standard_method(self) -> None:
        """Any bare-name variable with standard HTTP method should be detected."""
        src = """
class MyAPI:
    pass

api = MyAPI()

def fetch():
    return api.get("https://api.example.com/users")
"""
        calls = extract_http_calls(src, "main.py")
        assert len(calls) == 1, f"Expected 1 call, got {len(calls)}"
        assert calls[0].method == "GET"
        assert calls[0].url == "https://api.example.com/users"
        assert calls[0].function_name == "fetch"

    def test_bare_name_wrapper_post(self) -> None:
        """Any bare-name variable with .post() should be detected."""
        src = """
client = get_client()

def create():
    return client.post("https://api.example.com/items", json={"name": "test"})
"""
        calls = extract_http_calls(src, "main.py")
        assert len(calls) == 1
        assert calls[0].method == "POST"
        assert calls[0].url == "https://api.example.com/items"

    # --- Generic HTTP method support (Phase 1 fix) ---

    def test_generic_request_bare_name(self) -> None:
        """Generic .request('GET', url) on a bare-name wrapper should be detected."""
        src = """
client = MyHTTPClient()

def fetch():
    return client.request("GET", "https://api.example.com/users")
"""
        calls = extract_http_calls(src, "main.py")
        assert len(calls) == 1, f"Expected 1 call, got {len(calls)}"
        assert calls[0].method == "GET"
        assert calls[0].url == "https://api.example.com/users"
        assert calls[0].function_name == "fetch"

    def test_generic_call_attribute_chain(self) -> None:
        """Generic .call('POST', url) on an attribute chain should be detected."""
        src = """
class Service:
    def __init__(self):
        self.client = HTTPClient()

    def create(self):
        return self.client.call("POST", "https://api.example.com/items")
"""
        calls = extract_http_calls(src, "main.py")
        assert len(calls) == 1
        assert calls[0].method == "POST"
        assert calls[0].url == "https://api.example.com/items"
        assert calls[0].function_name == "create"

    def test_generic_request_with_dynamic_url(self) -> None:
        """Generic .request() with an f-string URL should be detected."""
        src = """
api = MyAPI()

def get_item(item_id):
    return api.request("GET", f"https://api.example.com/items/{item_id}")
"""
        calls = extract_http_calls(src, "main.py")
        assert len(calls) == 1
        assert calls[0].method == "GET"
        assert calls[0].has_dynamic is True
        assert calls[0].function_name == "get_item"

    def test_generic_invalid_method_skipped(self) -> None:
        """Generic .request() with a non-HTTP method string should be skipped."""
        src = """
client = MyClient()

def fetch():
    return client.request("INVALID", "https://api.example.com/data")
"""
        calls = extract_http_calls(src, "main.py")
        assert len(calls) == 0, f"Expected 0 calls, got {len(calls)}"

    def test_generic_not_enough_args_skipped(self) -> None:
        """Generic .request() with only one arg should be skipped."""
        src = """
client = MyClient()

def fetch():
    return client.request("https://api.example.com/data")
"""
        calls = extract_http_calls(src, "main.py")
        assert len(calls) == 0, f"Expected 0 calls, got {len(calls)}"

    def test_generic_non_string_first_arg_skipped(self) -> None:
        """Generic .request() with non-string first arg should be skipped."""
        src = """
METHOD = "GET"
client = MyClient()

def fetch():
    return client.request(METHOD, "https://api.example.com/data")
"""
        calls = extract_http_calls(src, "main.py")
        assert len(calls) == 0, f"Expected 0 calls, got {len(calls)}"

    def test_requests_request_generic(self) -> None:
        """requests.request('GET', url) should be detected (generic pattern on known module)."""
        src = """
import requests

def fetch():
    return requests.request("GET", "https://api.example.com/users")
"""
        calls = extract_http_calls(src, "main.py")
        assert len(calls) == 1
        assert calls[0].method == "GET"
        assert calls[0].url == "https://api.example.com/users"
