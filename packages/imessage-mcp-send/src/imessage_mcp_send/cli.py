"""Binary `imessage-mcp-send` — same Typer app as `imessage-mcp`, but with
the `send_message` tool registered on the shared FastMCP instance.

We don't add new Typer commands here. The capability the user installs this
package for is exposed via the MCP protocol, not the CLI. `serve` from
imessage-mcp picks up the additional tool automatically because we import
`imessage_mcp_send` (which triggers `tools` registration) before `app()`
runs.
"""

from __future__ import annotations

# Side-effect import: registers send_message on imessage_mcp.server.mcp.
import imessage_mcp_send  # noqa: F401
from imessage_mcp.cli import app

# Reflect the upgraded capability in --help.
app.info.help = "MCP server exposing iMessage (read AND send, local-only)."


def main() -> None:
    app()
