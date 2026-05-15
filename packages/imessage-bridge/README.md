# imessage-bridge

The "batteries-included" CLI for [`imessage-mcp`](https://pypi.org/project/imessage-mcp/): adds account management, a stable broker URL, and one-command tunneling.

If you just want a local MCP server with no third-party service, install [`imessage-mcp`](https://pypi.org/project/imessage-mcp/) instead. This package wraps it.

## What you get

- **Account-managed API keys.** Sign up once, mint and revoke keys from the CLI.
- **Stable broker URL.** `https://imessage-bridge.example.com/api/mcp` — works in any MCP client (Claude Desktop, Cursor, Poke). Survives cloudflared restarts because the CLI re-registers automatically.
- **All of `imessage-mcp`.** `setup`, `token`, and `serve` all live in this binary too.

## Install

```bash
brew install cloudflared
uv tool install imessage-bridge
```

## Quickstart

```bash
imessage-bridge setup                # macOS Full Disk Access pane
imessage-bridge signup               # create account, save API key locally
imessage-bridge serve --public       # tunnel + register with broker
                                     # prints the URL + token to paste into your MCP client
```

## Commands

| | |
|---|---|
| `signup` | Create account, save API key |
| `new-key` | Mint a new API key (asks for email + password) |
| `logout` | Forget local API key |
| `whoami` | Show current account |
| `keys list` | List all API keys on your account |
| `keys revoke <id>` | Revoke a key by ID |
| `serve [--public]` | Run the MCP server, optionally tunneling + registering |
| `setup` | Open macOS Full Disk Access pane |
| `token [--rotate]` | Print/rotate the local bearer token |

## License

MIT
