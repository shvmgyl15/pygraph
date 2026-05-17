from __future__ import annotations

import json
from pathlib import Path

from pygraph.query import GraphQuery


def run(query: GraphQuery, root: str = ".") -> None:
    root_path = Path(root).resolve()
    config_path = root_path / ".opencode.json"

    config = {
        "$schema": "https://opencode.ai/config.json",
        "mcp_servers": {
            "pygraph": {
                "command": "uv",
                "args": [
                    "run",
                    "pygraph",
                    "mcp",
                    "--root",
                    str(root_path),
                ],
                "env": {},
            },
        },
        "agents": {
            "architect": {
                "model": "opencode-go/deepseek-v4-flash",
                "instructions": [
                    "You are a software architect. Use the pygraph MCP tools to understand the codebase before making changes.",
                    "Query the code graph to find symbols, their callers/callees, and dependencies.",
                    "Check architecture boundaries before suggesting cross-layer changes.",
                    "Use `pygraph boundaries` to verify architectural compliance.",
                    "Use `pygraph plan` to understand the impact of proposed changes.",
                ],
            },
        },
    }

    config_path.write_text(json.dumps(config, indent=2))
    print(f"Created {config_path}")
