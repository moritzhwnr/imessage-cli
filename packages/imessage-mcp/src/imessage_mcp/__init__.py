"""imessage-mcp — MCP server exposing local iMessage queries.

Public API for downstream packages (like imessage-bridge) to import:
  - `app`              — the Typer CLI app, extendable with @app.command()
  - `mcp`              — the FastMCP instance with our tools registered
  - `serve_mcp(...)`   — start the HTTP server (lower level, used by serve cmd)
  - `spawn_cloudflared(...)` — start a Quick Tunnel subprocess
  - `print_config_panel(...)` — render the Claude-Desktop-style JSON
  - `CONFIG_DIR`, `TOKEN_FILE`
  - `load_or_create_token(...)`
"""

from imessage_mcp.cli import app, main
from imessage_mcp.config import CONFIG_DIR, TOKEN_FILE, load_or_create_token
from imessage_mcp.server import mcp, serve_mcp
from imessage_mcp.tunnel import print_config_panel, spawn_cloudflared

__all__ = [
    "app",
    "main",
    "mcp",
    "serve_mcp",
    "spawn_cloudflared",
    "print_config_panel",
    "CONFIG_DIR",
    "TOKEN_FILE",
    "load_or_create_token",
]
