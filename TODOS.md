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
- [ ] Route detection (`@app.route`, method, URL params)
- [ ] Blueprint detection and registration
- [ ] Template rendering detection (`render_template`)
- [ ] Error handler detection (`@app.errorhandler`)
- [ ] CLI command detection (`@app.cli.command`)
- [ ] Flask extension detection and usage
- [ ] Write extractor tests

## Phase 6: Analysis Commands
- [ ] complexity (McCabe / cyclomatic)
- [ ] hotspot / coupling / deps
- [ ] Write analysis tests

## Phase 7: Graph Traversal
- [ ] impact (BFS downstream blast radius)
- [ ] path (BFS shortest path between symbols)
- [ ] orphans (dead code detection via reachability from entry points)
- [ ] trace / errorflow (reverse BFS from string literal)
- [ ] Write traversal tests

## Phase 8: MCP Server
- [ ] MCP stdio server wrapping all query tools
- [ ] Tool definition for each search/query command
- [ ] MCP integration test
- [ ] `--root` flag for running MCP server against any project

## Phase 9: Advanced Features
- [ ] boundaries (architecture enforcement via .pygraph/boundaries.json)
- [ ] changes / stale (git-aware incremental analysis)
- [ ] plan / review (change planning reports)
- [ ] add-opencode-plugin (auto-configure opencode MCP + agent)
- [ ] Enhanced GRAPH_REPORT.md (hotspots, boundaries, coupling, stale)
- [ ] Incremental builds (file mtime tracking, skip rebuild when unchanged)
