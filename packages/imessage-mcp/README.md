# imessage-mcp

A read-only [MCP](https://modelcontextprotocol.io) server exposing your macOS iMessage history to any MCP-capable AI (Claude Desktop, Cursor, Poke, etc.).

**100% local.** Your messages never leave your Mac. This package has zero external dependencies — no signup, no hosted service. Just install, grant Full Disk Access, run.

## Install

```bash
uv tool install imessage-mcp
```

(Requires Python 3.13+ and `uv`. Install `uv` from <https://docs.astral.sh/uv/>.)

## Quickstart

```bash
imessage-mcp setup           # opens the macOS Full Disk Access pane
imessage-mcp serve           # MCP server on http://127.0.0.1:8765/mcp
```

Or expose it over the internet via a [Cloudflare Quick Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/):

```bash
brew install cloudflared
imessage-mcp serve --public  # prints a *.trycloudflare.com URL + bearer token
```

The bearer token lives at `~/.config/imessage-mcp/token` (chmod 600). Rotate with `imessage-mcp token --rotate`.

## Tools exposed via MCP

| Tool | Purpose |
|---|---|
| `list_chats(limit)` | Most recent conversations |
| `read_messages(chat_id, limit)` | Messages in a chat, oldest first |
| `search_messages(query, limit)` | Substring search across all chats |

## Want a stable broker URL across restarts?

Cloudflare Quick Tunnels get a new hostname on every launch. If you want a stable URL (and an account-style flow with signup/login), install [`imessage-bridge`](https://pypi.org/project/imessage-bridge/) — a separate package that adds those features on top of this one via a hosted broker.

## License

MIT
