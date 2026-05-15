# imessage-bridge

The "batteries-included" CLI for [`imessage-mcp`](https://pypi.org/project/imessage-mcp/): adds account management, a stable broker URL, and one-command tunneling.

If you just want a local MCP server with no third-party service, install [`imessage-mcp`](https://pypi.org/project/imessage-mcp/) instead. This package wraps it.

## What you get

- **Account-managed API keys.** Sign up once, mint and revoke keys from the CLI.
- **Stable broker URL.** `https://imessage-cli.vercel.app/api/mcp` — works in any MCP client (Claude Desktop, Cursor, Poke). Survives cloudflared restarts because the CLI re-registers automatically.
- **All of `imessage-mcp`.** `setup`, `token`, and `serve` all live in this binary too.

## Install

Read-only (just `read_messages`):

```bash
brew install cloudflared
uv tool install imessage-bridge
```

**Read + send** (also exposes the `send_message` MCP tool):

```bash
brew install cloudflared
uv tool install 'imessage-bridge[send]'
```

The `[send]` extra pulls in [`imessage-mcp-send`](https://pypi.org/project/imessage-mcp-send/) into the same tool environment. Without it, `imessage-bridge serve --send` will error and ask you to install it. You can always upgrade later with `uv tool install 'imessage-bridge[send]' --force`.

## Quickstart

```bash
imessage-bridge setup                # macOS Full Disk Access pane
imessage-bridge signup               # create account, save API key locally
imessage-bridge serve --public       # tunnel + register with broker
                                     # prints the URL + token to paste into your MCP client
```

If you installed the `[send]` extra, `serve` will prompt whether to enable the `send_message` tool — or pass `--send` / `--no-send` to skip the prompt.

## Commands

| | |
|---|---|
| `signup` | Create account, save API key |
| `new-key` | Mint a new API key (asks for email + password) |
| `logout` | Forget local API key |
| `whoami` | Show current account |
| `keys list` | List all API keys on your account |
| `keys revoke <id>` | Revoke a key by ID |
| `serve [--public] [--send/--no-send]` | Run the MCP server. `--public` tunnels + registers with the broker. `--send` requires `imessage-bridge[send]` |
| `setup` | Open macOS Full Disk Access pane |
| `token [--rotate]` | Print/rotate the local bearer token |

## Configuration

The default broker is the public one at `https://imessage-cli.vercel.app`. Override for local dev or a self-hosted broker via either:

**Environment variable** (preferred, scoped per shell):

```bash
export IMESSAGE_BRIDGE_BACKEND_URL=http://localhost:3000
```

**`.env` file** — loaded automatically from either of:

- `~/.config/imessage-bridge/.env` — persists across shell sessions
- `./.env` — for local dev (loaded from the current working directory)

See `.env.example` for the available keys. Values already in the shell environment take precedence over `.env` files.

## License

MIT
