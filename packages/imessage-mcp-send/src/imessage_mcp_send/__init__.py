"""imessage-mcp-send — adds a send_message tool to the imessage-mcp server.

Importing this package has a SIDE EFFECT: it registers `send_message` on
the shared FastMCP instance (`imessage_mcp.server.mcp`). Both binaries —
`imessage-mcp-send` (this package) and `imessage-bridge` (when installed
alongside) — pick up the tool automatically by importing `tools`.
"""

# Side-effect import: registers send_message on the shared mcp instance.
from imessage_mcp_send import tools as tools  # noqa: F401
