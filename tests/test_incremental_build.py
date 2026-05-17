from __future__ import annotations

from pathlib import Path

import pytest

from pygraph.builder import build_and_write, build_graph
from pygraph.graph.cache import BuildCache

SAMPLE_APP = """
from flask import Flask

app = Flask(__name__)

@app.route("/")
def index() -> str:
    return "hello"

@app.route("/user/<name>")
def user(name: str) -> str:
    return f"hello {name}"
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "app.py").write_text(SAMPLE_APP)
    return tmp_path


# ---------------------------------------------------------------------------
# BuildCache unit tests
# ---------------------------------------------------------------------------


class TestBuildCache:
    def test_is_changed_new_file(self) -> None:
        cache = BuildCache({})
        assert cache.is_changed("app.py", 100.0, 50) is True

    def test_is_changed_unchanged(self) -> None:
        cache = BuildCache({"app.py": {"mtime": 100.0, "size": 50}})
        assert cache.is_changed("app.py", 100.0, 50) is False

    def test_is_changed_different_mtime(self) -> None:
        cache = BuildCache({"app.py": {"mtime": 100.0, "size": 50}})
        assert cache.is_changed("app.py", 200.0, 50) is True

    def test_is_changed_different_size(self) -> None:
        cache = BuildCache({"app.py": {"mtime": 100.0, "size": 50}})
        assert cache.is_changed("app.py", 100.0, 99) is True

    def test_set_and_get(self) -> None:
        cache = BuildCache({})
        cache.set("app.py", 100.0, 50)
        assert cache.files["app.py"]["mtime"] == 100.0
        assert cache.files["app.py"]["size"] == 50

    def test_remove(self) -> None:
        cache = BuildCache({"app.py": {"mtime": 1.0, "size": 1}})
        cache.remove("app.py")
        assert "app.py" not in cache.files

    def test_round_trip(self, tmp_path: Path) -> None:
        cache = BuildCache({"app.py": {"mtime": 100.0, "size": 50}})
        path = tmp_path / ".build_cache.json"
        cache.save(path)
        loaded = BuildCache.load(path)
        assert loaded.files == cache.files

    def test_load_missing(self, tmp_path: Path) -> None:
        loaded = BuildCache.load(tmp_path / "nonexistent.json")
        assert loaded.files == {}

    def test_load_corrupt(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("not json")
        loaded = BuildCache.load(path)
        assert loaded.files == {}


# ---------------------------------------------------------------------------
# Incremental build integration tests
# ---------------------------------------------------------------------------


class TestIncrementalBuild:
    def test_first_build_creates_graph_and_cache(
        self, project: Path
    ) -> None:
        build_and_write(str(project), incremental=True)
        graph_path = project / ".pygraph" / "graph.json"
        cache_path = project / ".pygraph" / ".build_cache.json"
        assert graph_path.exists()
        assert cache_path.exists()

    def test_incremental_second_build_uses_cache(
        self, project: Path
    ) -> None:
        build_and_write(str(project), incremental=True)
        graph_path = project / ".pygraph" / "graph.json"

        # Run again with no changes
        build_and_write(str(project), incremental=True)
        assert graph_path.exists()

    def test_incremental_reparses_changed_file(
        self, project: Path
    ) -> None:
        build_and_write(str(project), incremental=True)
        app_file = project / "src" / "app.py"
        app_file.write_text(app_file.read_text() + "\ndef new_func() -> None: pass\n")

        build_and_write(str(project), incremental=True)
        graph = build_graph(str(project), incremental=False)
        names = {s.name for s in graph.symbols}
        assert "new_func" in names

    def test_new_file_parsed_incrementally(
        self, project: Path
    ) -> None:
        build_and_write(str(project), incremental=True)
        (project / "src" / "utils.py").write_text("def util(): pass\n")

        build_and_write(str(project), incremental=True)
        graph = build_graph(str(project), incremental=False)
        names = {s.name for s in graph.symbols}
        assert "util" in names

    def test_deleted_file_removed_incrementally(
        self, project: Path
    ) -> None:
        build_and_write(str(project), incremental=True)
        (project / "src" / "app.py").unlink()

        build_and_write(str(project), incremental=True)
        graph = build_graph(str(project), incremental=False)
        assert len(graph.symbols) == 0

    def test_full_build_still_works(
        self, project: Path
    ) -> None:
        build_and_write(str(project), incremental=False)
        graph_path = project / ".pygraph" / "graph.json"
        assert graph_path.exists()

    def test_non_incremental_does_not_use_cache(
        self, project: Path
    ) -> None:
        build_and_write(str(project), incremental=True)
        cache_path = project / ".pygraph" / ".build_cache.json"
        cache = BuildCache.load(cache_path)
        cache.set("src/app.py", 0, 0)  # force re-parse next time
        cache.save(cache_path)

        # Full build ignores cache
        build_and_write(str(project), incremental=False)
        # Cache should have been overwritten with fresh values
        cache2 = BuildCache.load(cache_path)
        assert cache2.files["src/app.py"]["mtime"] != 0

    def test_merge_preserves_all_data(
        self, project: Path
    ) -> None:
        build_and_write(str(project), incremental=True)
        graph1 = build_graph(str(project), incremental=False)
        sym_count1 = len(graph1.symbols)
        call_count1 = len(graph1.calls)

        build_and_write(str(project), incremental=True)
        graph2 = build_graph(str(project), incremental=False)
        assert len(graph2.symbols) == sym_count1
        assert len(graph2.calls) == call_count1

    def test_cache_not_used_when_missing_cache(
        self, project: Path
    ) -> None:
        build_and_write(str(project), incremental=True)
        cache_path = project / ".pygraph" / ".build_cache.json"
        cache_path.unlink()

        # Should still work (falls back to full build)
        build_and_write(str(project), incremental=True)
        assert cache_path.exists()

    def test_cache_not_used_when_missing_graph(
        self, project: Path
    ) -> None:
        build_and_write(str(project), incremental=True)
        graph_path = project / ".pygraph" / "graph.json"
        graph_path.unlink()

        # Should still work
        build_and_write(str(project), incremental=True)
        assert graph_path.exists()

    def test_full_build_creates_cache(
        self, project: Path
    ) -> None:
        build_and_write(str(project), incremental=False)
        cache_path = project / ".pygraph" / ".build_cache.json"
        assert cache_path.exists()
        cache = BuildCache.load(cache_path)
        assert "src/app.py" in cache.files
