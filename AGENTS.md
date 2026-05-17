# pygraph — Project DNA

## Vision
A fast, local-only CLI tool that indexes Python / Flask codebases using AST parsing
into a queryable graph.json for AI coding agents. Equivalent to gograph / tsgraph but for Python.
Output is Markdown + JSON. No network calls, no telemetry, no SaaS backend.

## Design Philosophy (Go/TS → Python Adaptation)
pygraph is inspired by gograph (Go) and tsgraph (TypeScript) but adapted for Python / Flask.
Key language-driven differences:
- **Export model**: Python uses `__all__` and `_name` convention (private by underscore); `isExported` maps to `not name.startswith('_')` or `name in __all__`
- **No goroutines/channels or async/promise** — Python has `asyncio`, threads, and generators
- **No struct tags** — Python has no native equivalent; use `dataclass` fields or type annotations
- **Router detection** is Flask route decorators (`@app.route`), Blueprints (`register_blueprint`), not Gin/mux or Next.js
- **Flask components** are tracked: views, Blueprints, CLI commands (`@app.cli.command`), template rendering, error handlers
- **Decorator support** — Python decorators are first-class; tracked as edges in the graph
- **Interface satisfaction** — Python uses `ABC` / `Protocol` (PEP 544) structural subtyping
- **Module-level code** — Python modules execute on import; side effects are tracked
- **Class methods / static methods / properties** — `@classmethod`, `@staticmethod`, `@property` tracked distinctly
- Go-specific concepts (structs with fields+tests, `MutationEdge`, `StructField.tags`) are replaced by Python equivalents (dataclass fields, test functions matching `test_*`)

## Tech Stack
- Runtime: Python 3.11+
- Package manager: `uv`
- AST: `ast` (stdlib) + `astroid` for enhanced traversal
- CLI: `typer`
- MCP: `mcp` Python SDK
- Testing: `pytest` + `pytest-cov`
- Linting: `ruff`
- Type checking: `mypy` (strict mode)

## Agent Rules

### Task Management
- READ TODOS.md at session start to know what's done and what's next
- UPDATE TODOS.md when you start/finish a task (`[.]` in-progress, `[x]` done)
- Work in phase order unless a task has no blockers
- After a phase completes (all items `[x]`), run `git init` if not yet done, then commit: `git add -A && git commit -m "phase N: <title>"`

### Orchestration
- This is a single-orchestrator project. When a task has multiple independent
  sub-tasks, delegate via the `task` tool (`subagent_type: general`) rather
  than doing them sequentially.
- For each delegated sub-task, specify:
  1. Exact files the sub-agent may modify
  2. Which phase from TODOS.md it belongs to
  3. What to return (never let sub-agents commit or merge)
- After all sub-tasks complete, run `uv run pytest && uv run mypy src && uv run ruff check` and fix any issues directly. Do NOT re-delegate broken builds.

### Quality
- Run `uv run pytest`, `uv run mypy src`, and `uv run ruff check` after every task completion
- Fix all failures before marking `[x]`
- If the project is already broken when you start, note it in TODOS.md and fix it first

### Research
- Use webfetch when unsure about an API — check Python `ast` docs, Flask docs,
  or reference tsgraph source or gograph Go source
- DO NOT guess API signatures

### Code Style
- No comments in source files unless logic is non-obvious
- Type annotations everywhere, avoid `Any`
- Follow patterns from adjacent files in the codebase
- No emojis in source code or commit messages
- Follow PEP 8 conventions (enforced by ruff)

### Communication
- Be concise. Use TODOS.md for status, respond with only what's needed.
- If stuck, explain the blocker clearly rather than overthinking.
