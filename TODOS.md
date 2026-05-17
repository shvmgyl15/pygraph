# pygraph — Implementation Plan

## Phase 1: Project Scaffold
- [x] Update opencode.json with AGENTS.md reference
- [x] Create AGENTS.md with project DNA
- [x] Create TODOS.md (this file)
- [.] Git init + Phase 1 commit
- [x] Initialize pyproject.toml with dependencies (typer, astroid, mcp, pytest, mypy, ruff)
- [x] Configure mypy (strict mode)
- [x] Configure ruff (PEP 8, import sorting)
- [x] Create src/pygraph directory structure (commands/, scanner/, graph/, extractors/)
- [x] Setup pytest config (conftest.py, test fixtures)

## Phase 2: Core Data Model
- [ ] Define graph types (Graph, PackageNode, FileNode, SymbolNode, Edge, etc.)
- [ ] Add JSON serialization / deserialization (pydantic or dataclasses)
- [ ] Write unit tests for graph types

## Phase 3: Scanner + Parser Core
- [ ] Implement file scanner (walk tree, gitignore support, file classification)
- [ ] Implement symbol extractor (astroid: functions, classes, methods, variables, constants)
- [ ] Implement call expression extractor
- [ ] Implement import edge + dependency extractor (importlib.metadata or requirements)
- [ ] Implement decorator tracking
- [ ] Wire up `build` command end-to-end
- [ ] Write parser/scanner unit tests

## Phase 4: Query Commands
- [ ] callers / callees
- [ ] node / source / query
- [ ] context (bundle — node + source + callers + callees + tests)
- [ ] imports / public / focus
- [ ] impact / path / orphans / trace (CLI commands)
- [ ] query regex support (fallback to substring)
- [ ] Write query command tests

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
