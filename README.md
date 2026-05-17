# pygraph

AST-based Python/Flask codebase indexer for AI coding agents.

`pygraph` parses your Python project into a queryable graph (`graph.json`) using static analysis (AST). It detects Flask routes, blueprints, templates, CLI commands, decorators, dependencies, and more — with **zero network calls** and **no telemetry**.

Designed as a companion tool for AI agents (opencode, Cline, etc.) via MCP, or for direct CLI use during development.

---

## Quick Start

```bash
pip install git+https://github.com/shvmgyl15/pygraph.git

# Or with uv:
uv pip install git+https://github.com/shvmgyl15/pygraph.git
```

Index your project and start querying:

```bash
cd my-python-project
pygraph build
pygraph public
pygraph node "my_function"
pygraph callers "my_function"
```

---

## Commands

| Command | Description |
|---------|-------------|
| `build` | Index project into `.pygraph/graph.json` |
| `node` | Show details of a symbol |
| `callers` | Show who calls the given symbol |
| `callees` | Show what the given symbol calls |
| `source` | Show source code of a file |
| `query` | Search symbols by pattern (regex or substring) |
| `context` | Show symbol with callers, callees, tests, and source |
| `imports` | Show imports of a file |
| `public` | List all exported (public) symbols |
| `focus` | Show JSON detail for a symbol |
| `impact` | Show downstream impact (BFS from symbol) |
| `path` | Show shortest call path between two symbols |
| `orphans` | List uncalled private symbols |
| `trace` | Find error messages and trace their call paths |
| `complexity` | Show McCabe cyclomatic complexity |
| `coupling` | Show afferent/efferent coupling metrics |
| `hotspot` | Show high-risk symbols (complexity x coupling) |
| `deps` | List external dependencies |
| `boundaries` | Check architecture boundary violations |
| `changes` | Show symbol changes since a git ref |
| `stale` | List files not modified in N days |
| `plan` | Generate a change plan report |
| `review` | Generate a Markdown code review report |
| `graph-report` | Generate a Markdown report about the codebase |
| `add-opencode-plugin` | Create `.opencode.json` with pygraph MCP config |
| `mcp` | Start MCP stdio server for AI agent integration |

---

## MCP Integration

Start the MCP server and connect your AI agent:

```bash
pygraph mcp --root /path/to/project
```

All query commands are exposed as MCP tools, making them callable from opencode, Cline, and any MCP-compatible client.

---

## Flask Support

pygraph detects Flask-specific constructs out of the box:

- Route decorators (`@app.route`) with HTTP methods and URL parameters
- Blueprint creation and registration (`register_blueprint`)
- Template rendering (`render_template`, `render_template_string`)
- Error handlers (`@app.errorhandler`)
- CLI commands (`@app.cli.command`)
- Flask extension usage

---

## Architecture Enforcement

Create `.pygraph/boundaries.json`:

```json
{
  "layers": [
    {"name": "views",     "pattern": "src/views/",     "allowed": ["services"]},
    {"name": "services",  "pattern": "src/services/",  "allowed": ["models", "repos"]},
    {"name": "models",    "pattern": "src/models/",    "allowed": []},
    {"name": "repos",     "pattern": "src/repos/",     "allowed": ["models"]}
  ]
}
```

Then run:

```bash
pygraph boundaries
```

---

## Requirements

- Python 3.11+
- `uv` (recommended) or `pip`

---

## Development

```bash
git clone https://github.com/shvmgyl15/pygraph.git
cd pygraph
uv sync
uv run pytest
uv run mypy src
uv run ruff check
```

---

## How It Works

```
┌──────────┐    ┌──────────────┐    ┌───────────┐
│  Scanner  │ → │  Extractors  │ → │   Graph   │
│ (walker)  │   │ (AST, Flask) │   │  (JSON)   │
└──────────┘    └──────────────┘    └───────────┘
                                          ↓
                                   ┌──────────┐
                                   │  Query   │
                                   │  Engine  │
                                   └──────────┘
```

1. **Scan** — walks the project tree, respects `.gitignore`, classifies files
2. **Extract** — parses Python source with `ast`, extracts symbols, calls, imports, Flask decorators, dependencies
3. **Graph** — serializes everything to `.pygraph/graph.json` (incremental builds supported)
4. **Query** — CLI or MCP tools query the graph for callers, callees, impact, paths, orphans, complexity, coupling, etc.

---

## Inspiration

pygraph was inspired by and follows the same design philosophy as:

- [tsgraph](https://github.com/shvmgyl15/tsgraph) — TypeScript codebase indexer
- [gograph](https://github.com/ozgurcd/gograph) — Go codebase indexer

Both projects use AST-based static analysis to create queryable code graphs for AI coding agents. pygraph adapts the same concept to Python and Flask.
