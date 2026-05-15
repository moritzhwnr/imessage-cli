# imessage-mcp-send

Optional add-on for [`imessage-mcp`](https://pypi.org/project/imessage-mcp/) that adds a `send_message` MCP tool. With this installed, your MCP client can also **send** iMessages, not just read them.

**Sending is irreversible.** Install only if you understand and accept that — and only with an MCP client that surfaces tool calls to you for confirmation before executing them.

## Install

```bash
uv tool install imessage-mcp-send
```

This pulls in `imessage-mcp` as a dependency, so you don't need to install it separately.

## Quickstart

```bash
imessage-mcp-send setup        # opens the macOS Full Disk Access pane
imessage-mcp-send serve        # MCP server on http://127.0.0.1:8765/mcp
                               # exposes list_chats, read_messages, search_messages, send_message
```

On first send, macOS will prompt for **Automation** permission for whatever app is running the CLI (Terminal, iTerm, etc.) to control **Messages**. Click Allow.

## With the broker ([`imessage-bridge`](https://pypi.org/project/imessage-bridge/))

Install both:

```bash
uv tool install imessage-mcp-send
uv tool install imessage-bridge
```

`imessage-bridge serve --public` auto-detects this package and exposes send via your broker URL too.

## The new tool

| Tool | Arguments | Purpose |
|---|---|---|
| `send_message` | `text`, `recipient?`, `chat_id?` | Send to a phone/email **or** reply to a 1:1 chat. Group chats not supported. |

## License

MIT
