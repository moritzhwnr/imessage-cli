# imessage-cli

A monorepo of three Python packages and a Next.js broker that turn your local iMessage history into something an MCP-capable AI (Claude, Cursor, Poke, …) can read — and optionally reply through — without your messages ever leaving your Mac.

## Packages (published to PyPI)

| Package | Install | What it does |
|---|---|---|
| [`imessage-mcp`](https://pypi.org/project/imessage-mcp/) | `uv tool install imessage-mcp` | Read-only MCP server for your iMessage DB. No hosted service. |
| [`imessage-mcp-send`](https://pypi.org/project/imessage-mcp-send/) | `uv tool install imessage-mcp-send` | Adds a `send_message` tool. **Irreversible writes.** |
| [`imessage-bridge`](https://pypi.org/project/imessage-bridge/) | `uv tool install imessage-bridge` | Connected CLI with account-managed API keys and a stable broker URL. |

Each package has its own README inside `packages/<name>/`.

## Architecture

```
                Claude / Poke / Cursor  (MCP client)
                          │
                          │  Bearer <api_key>
                          ▼
              Next.js broker (backend/)      ◀── Supabase auth + Postgres
                          │  Bearer <tunnel_token>
                          ▼
              *.trycloudflare.com tunnel
                          │
                          ▼
              imessage-mcp on your Mac        ◀── chat.db (read-only)
```

The broker is plumbing — your messages never leave your Mac.

## Repository layout

```
packages/imessage-mcp/         ← published: read-only MCP server
packages/imessage-mcp-send/    ← published: optional send_message tool
packages/imessage-bridge/      ← published: connected CLI for the broker
backend/                       ← Next.js + Supabase broker (not published)
src/imessage_cli/              ← legacy local-only tools (imessage-cli, imessage-ai)
```

The workspace is a [`uv`](https://docs.astral.sh/uv/) workspace; packages share a single venv during dev.

## Development setup

```bash
git clone https://github.com/moritzhwnr/imessage-cli
cd imessage-cli
uv sync                                 # installs all three packages + legacy CLIs in editable mode
uv run imessage-mcp --help
uv run imessage-bridge --help
```

For the broker:

```bash
cd backend
cp .env.local.example .env.local        # fill in Supabase URL + service-role key + encryption key
npm install
npm run dev                             # http://localhost:3000
```

See `backend/supabase/migrations/0001_init.sql` for the database schema and `backend/.env.local.example` for the required env vars.

## License

MIT — see [`LICENSE`](LICENSE).
