"""FastMCP server + tools + bearer auth.

This is the actual MCP service. The `serve_mcp` helper is the lower-level
entry point that downstream packages (imessage-bridge) reuse — the Typer
`serve` command just calls it.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import typer
import uvicorn
from mcp.server.fastmcp import FastMCP
from rich.console import Console
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from imessage_mcp._imessage import apple_ts_to_dt, open_db

out = Console()
err = Console(stderr=True)

mcp = FastMCP("imessage")


# ---------- bearer auth middleware ----------


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that 401s anything without `Authorization: Bearer <token>`."""

    def __init__(self, app, token: str) -> None:
        super().__init__(app)
        self._expected = f"Bearer {token}"

    async def dispatch(self, request, call_next):
        if request.headers.get("Authorization") != self._expected:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


# ---------- helper for tool error handling ----------


def _safe_open_db() -> sqlite3.Connection:
    """Translate DB access errors into MCP-friendly errors."""
    try:
        return open_db()
    except FileNotFoundError as e:
        raise RuntimeError(str(e)) from e
    except sqlite3.OperationalError as e:
        raise RuntimeError(
            f"Cannot open chat.db: {e}. The process running imessage-mcp "
            "probably lacks Full Disk Access. Run `imessage-mcp setup`."
        ) from e


# ---------- MCP tools ----------


@mcp.tool()
def list_chats(limit: int = 20) -> list[dict]:
    """List the most recent iMessage conversations.

    Args:
        limit: How many chats to return (default 20).

    Returns: list of {chat_id, who, last_message_at}, newest first.
    """
    conn = _safe_open_db()
    rows = conn.execute(
        """
        SELECT c.ROWID, COALESCE(NULLIF(c.display_name, ''), h.id, '?'), MAX(m.date)
        FROM chat c
        JOIN chat_message_join cmj ON cmj.chat_id = c.ROWID
        JOIN message m ON m.ROWID = cmj.message_id
        LEFT JOIN chat_handle_join chj ON chj.chat_id = c.ROWID
        LEFT JOIN handle h ON h.ROWID = chj.handle_id
        GROUP BY c.ROWID ORDER BY MAX(m.date) DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "chat_id": cid,
            "who": who,
            "last_message_at": apple_ts_to_dt(ts).astimezone().isoformat(),
        }
        for cid, who, ts in rows
    ]


@mcp.tool()
def read_messages(chat_id: int, limit: int = 30) -> list[dict]:
    """Read recent messages from a specific chat, oldest first.

    Args:
        chat_id: The chat ID (from list_chats).
        limit: How many recent messages (default 30).
    """
    conn = _safe_open_db()
    rows = conn.execute(
        """
        SELECT m.date, m.is_from_me, COALESCE(m.text, '')
        FROM message m
        JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
        WHERE cmj.chat_id = ?
        ORDER BY m.date DESC LIMIT ?
        """,
        (chat_id, limit),
    ).fetchall()
    return [
        {
            "at": apple_ts_to_dt(ts).astimezone().isoformat(),
            "from": "me" if is_me else "them",
            "text": text,
        }
        for ts, is_me, text in reversed(rows)
    ]


@mcp.tool()
def search_messages(query: str, limit: int = 30) -> list[dict]:
    """Substring-search message text across all chats (case-insensitive).

    Args:
        query: The substring to search for.
        limit: Max matches (default 30).
    """
    conn = _safe_open_db()
    rows = conn.execute(
        """
        SELECT m.date, m.is_from_me, COALESCE(m.text, ''), cmj.chat_id,
               COALESCE(NULLIF(c.display_name, ''), h.id, '?')
        FROM message m
        JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
        JOIN chat c ON c.ROWID = cmj.chat_id
        LEFT JOIN chat_handle_join chj ON chj.chat_id = c.ROWID
        LEFT JOIN handle h ON h.ROWID = chj.handle_id
        WHERE m.text LIKE ? COLLATE NOCASE
        ORDER BY m.date DESC LIMIT ?
        """,
        (f"%{query}%", limit),
    ).fetchall()
    return [
        {
            "at": apple_ts_to_dt(ts).astimezone().isoformat(),
            "from": "me" if is_me else "them",
            "text": text,
            "chat_id": cid,
            "who": who,
        }
        for ts, is_me, text, cid, who in rows
    ]


# ---------- server runner ----------


def serve_mcp(host: str, port: int, token: str) -> None:
    """Start the FastMCP HTTP server with bearer auth (blocks until stopped).

    Extracted so downstream packages can run the same server while wrapping
    the orchestration around it (e.g. broker registration in imessage-bridge).
    """
    asgi_app = mcp.streamable_http_app()
    asgi_app.add_middleware(BearerAuthMiddleware, token=token)
    uvicorn.run(asgi_app, host=host, port=port, log_level="info")


def allow_tunnel_host(host: str, origin_url: str) -> None:
    """Allow a runtime-discovered host through FastMCP's DNS rebinding check.

    Used by the tunnel watcher when cloudflared comes up. The settings list
    is read per-request, so adding to it at runtime takes effect immediately.
    """
    mcp.settings.transport_security.allowed_hosts.append(host)
    mcp.settings.transport_security.allowed_origins.append(origin_url)
