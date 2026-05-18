# pygraph — Implementation Plan

## Phase 1: Project Scaffold
- [x] Update opencode.json with AGENTS.md reference
- [x] Create AGENTS.md with project DNA
- [x] Create TODOS.md (this file)
- [x] Git init + Phase 1 commit
- [x] Initialize pyproject.toml with dependencies (typer, astroid, mcp, pytest, mypy, ruff)
- [x] Configure mypy (strict mode)
- [x] Configure ruff (PEP 8, import sorting)
- [x] Create src/pygraph directory structure (commands/, scanner/, graph/, extractors/)
- [x] Setup pytest config (conftest.py, test fixtures)

## Phase 2: Core Data Model
- [x] Define graph types (Graph, PackageNode, FileNode, SymbolNode, and all edge types)
- [x] Add JSON serialization / deserialization (dataclasses)
- [x] Write unit tests for graph types (42 tests)

## Phase 3: Scanner + Parser Core
- [x] Implement file scanner (walk tree, gitignore support, file classification)
- [x] Implement symbol extractor (ast: functions, classes, methods, variables, constants)
- [x] Implement call expression extractor
- [x] Implement import edge + dependency extractor (requirements.txt, pyproject.toml)
- [x] Implement decorator tracking (inline in symbol extraction)
- [x] Wire up `build` command end-to-end (builder.py orchestrates scan → parse → write)
- [x] Write parser/scanner unit tests (25 tests for scanner + extractors)

## Phase 4: Query Commands
- [x] GraphQuery engine (query.py) — symbol lookup, callers/callees, imports, regex, context, impact, path, orphans, trace/errorflow
- [x] callers / callees CLI commands
- [x] node / source / query CLI commands
- [x] context (bundle — node + source + callers + callees + tests)
- [x] imports / public / focus CLI commands
- [x] impact / path / orphans / trace CLI commands (basic BFS, refined in Phase 7)
- [x] query regex support (fallback to substring)
- [x] Write query command tests (60 tests)

## Phase 5: Flask-Specific Extractors
- [x] Route detection (`@app.route`, method, URL params)
- [x] Blueprint detection and registration
- [x] Template rendering detection (`render_template`)
- [x] Error handler detection (`@app.errorhandler`)
- [x] CLI command detection (`@app.cli.command`)
- [x] Flask extension detection and usage
- [x] Write extractor tests

## Phase 6: Analysis Commands
- [x] complexity (McCabe / cyclomatic)
- [x] hotspot / coupling / deps
- [x] Write analysis tests

## Phase 7: Graph Traversal
- [x] impact (BFS downstream blast radius with deque, max_depth, transitive)
- [x] path (BFS shortest path with deque, file/line in steps)
- [x] orphans (dead code detection via reachability from entry points)
- [x] trace / errorflow (reverse BFS from string literal through callers)
- [x] Write traversal tests (169 tests, up from 159)

## Phase 8: MCP Server
- [x] MCP stdio server wrapping all query tools (`src/pygraph/server.py`)
- [x] Tool definition for each search/query command (18 tools)
- [x] MCP unit test (30 tests, unit-test style via `_query_override`)
- [x] `--root` flag for running MCP server against any project

## Phase 9: Advanced Features
- [x] boundaries (architecture enforcement via .pygraph/boundaries.json)
- [x] Incremental builds (mtime tracking, merge unchanged data, skip re-parse)
- [x] changes / stale (git-aware incremental analysis)
- [x] plan / review (change planning reports)
- [x] add-opencode-plugin (auto-configure opencode MCP + agent)
- [x] Enhanced GRAPH_REPORT.md (hotspots, boundaries, coupling, stale)

## Phase 10: Query Engine Fixes + Missing Extractors
- [x] Rewrite `_resolve_callee` to parse `ClassName(args).method()` patterns
- [x] Fix `get_callers` to use `_resolve_callee`
- [x] Fix `get_callees` to aggregate calls from class methods
- [x] Fix coupling/hotspot to use qualified names (`ClassName.method`)
- [x] Fix `_callers_by_name` index to also key by receiver
- [x] Fix `get_path` visited tracking redundant check
- [x] Build env_reads extractor (`os.environ.get`, `os.getenv`, `environ[]`)
- [x] Build errors extractor (`raise` / `raise ... from ...`)
- [x] Build test_edges extractor (test functions → called project symbols)
- [x] Build implements extractor (ABC/Protocol subclassing)
- [x] Better error messages for `changes`/`plan`/`review` snapshot misses
- [x] `orphans --all` flag for public uncalled symbols
- [x] `context` structured summary (source behind `--source` flag)
- [x] P0: Fix `caller_symbol_id` mismatch — qualify class.method name in calls.py
- [x] P1: Add `app.add_url_rule()` route extractor in flask.py
- [x] P2: Add Poetry dependency parsing in imports.py
- [x] P4: Auto-build graph from git ref with caching (`._load_git_graph` fallback)
- [x] P4: Update `.gitignore` for `ref-*.json` cache files
- [x] Run `pytest && mypy src && ruff check` — fix all failures

## Phase 11: Post-Build Plugin System
- [x] Add `src/pygraph/config.py` — load `[tool.pygraph]` from `pyproject.toml`
- [x] Add `_run_plugins()` in `builder.py` — import & run each plugin script's `run(graph)`
- [x] Wire into `build_graph()` — plugins run after graph assembly, before return
- [x] Errors, missing scripts, missing `run` function all warn and continue
- [x] Multiple plugins supported in order; failure of one doesn't block the next
- [x] Tests: plugin runs + adds edges, missing plugin, no run function, exception, no plugins, multiple, partial failure

## Phase 12: PyPI Publishing Prep
- [x] Add author, license, readme, classifiers, urls to pyproject.toml
- [x] Add `__version__` to `src/pygraph/__init__.py`
- [x] Update package name to `pygraph-mcp` (pygraph taken on PyPI)
- [x] Update README.md install instructions for PyPI
- [x] Create `.github/workflows/publish.yml` for auto-publishing on tags
- [x] Fix unwanted imports in tests/test_plugins.py
- [x] Verify build, tests, mypy, ruff all pass
