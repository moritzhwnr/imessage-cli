"""The send_message MCP tool. Side-effect: registers on import.

Sending is irreversible. The MCP client (Claude Desktop, etc.) is expected
to surface tool calls to the user for confirmation — we don't add our own
confirmation here because there's no human in the MCP request loop. If
your client doesn't gate tool use, that's a client issue, not a tool one.
"""

from __future__ import annotations

import subprocess

# Importing the singleton `mcp` from imessage-mcp's server lets the
# @mcp.tool() decorator below register on the SAME instance the read-only
# server already uses. When the server starts, all 4 tools are exposed.
from imessage_mcp._imessage import open_db
from imessage_mcp.server import mcp


def _send_via_applescript(recipient: str, text: str) -> str:
    """Run AppleScript to ask Messages.app to send. Returns a result string."""
    # Pass recipient + text as positional args (not interpolated into the
    # script source) so a maliciously-crafted message body can't break out
    # of string literals and inject AppleScript.
    script = """
    on run argv
        set theBuddy to item 1 of argv
        set theText  to item 2 of argv
        tell application "Messages"
            set targetService to 1st service whose service type = iMessage
            set theBuddy to buddy theBuddy of targetService
            send theText to theBuddy
        end tell
    end run
    """
    result = subprocess.run(
        ["osascript", "-e", script, recipient, text],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return f"ERROR: send failed — {result.stderr.strip() or 'unknown'}"
    return f"sent to {recipient}"


@mcp.tool()
def send_message(
    text: str,
    recipient: str | None = None,
    chat_id: int | None = None,
) -> str:
    """Send an iMessage via Messages.app.

    IRREVERSIBLE side effect. Provide EXACTLY ONE of `recipient` or `chat_id`.
    Group chats are not currently supported.

    Args:
        text: The message body to send.
        recipient: E.164 phone number (e.g. "+491234567890") or iMessage email.
        chat_id: A chat ID from list_chats. Must be a 1:1 chat.

    Returns: A status string starting with "sent" on success or "ERROR" on failure.
    """
    if (recipient is None) == (chat_id is None):
        return "ERROR: provide exactly one of `recipient` or `chat_id`."

    if chat_id is not None:
        # Resolve a chat_id to a single handle. AppleScript can technically
        # address group chats via `text chat id`, but it's unreliable on
        # modern macOS — better to refuse than half-work.
        try:
            conn = open_db()
        except FileNotFoundError as e:
            return f"ERROR: {e}"
        handles = conn.execute(
            """
            SELECT h.id FROM chat_handle_join chj
            JOIN handle h ON h.ROWID = chj.handle_id
            WHERE chj.chat_id = ?
            """,
            (chat_id,),
        ).fetchall()
        if not handles:
            return f"ERROR: no handles found for chat {chat_id}"
        if len(handles) > 1:
            return (
                f"ERROR: chat {chat_id} is a group ({len(handles)} participants); "
                "group sending is not supported."
            )
        recipient = handles[0][0]

    assert recipient is not None  # guaranteed by the XOR check above
    return _send_via_applescript(recipient, text)
