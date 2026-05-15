"""Typer CLI for imessage-bridge.

Strategy: this binary subsumes imessage-mcp's commands so users only need
one tool. We:
  1. Import imessage-mcp's Typer app
  2. Replace its `serve` with our broker-aware version
  3. Add signup / new-key / whoami / logout / keys subcommands

Users installing only `imessage-mcp` see the local-only commands. Users
installing `imessage-bridge` get everything in one binary.
"""

from __future__ import annotations

import subprocess
from typing import Annotated
from urllib.parse import urlparse

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from imessage_mcp._imessage import CHAT_DB
from imessage_mcp.cli import app as mcp_app
from imessage_mcp.config import load_or_create_token
from imessage_mcp.server import allow_tunnel_host, serve_mcp
from imessage_mcp.tunnel import print_config_panel, spawn_cloudflared

# Optional dependency: if imessage-mcp-send is also installed, importing it
# registers the `send_message` tool on the shared FastMCP instance. Bridge
# users who want send via the broker just `uv tool install imessage-mcp-send`
# alongside this package — no flag, no reconfiguration.
try:
    import imessage_mcp_send  # noqa: F401 — side effect: registers tool
    _HAS_SEND = True
except ImportError:
    _HAS_SEND = False

from imessage_bridge._account import (
    API_KEY_FILE,
    API_KEY_FILE as _API_KEY_FILE_UNUSED,
    DEFAULT_BACKEND_URL,
    USER_ID_FILE,
    load_account,
    prompt_credentials,
    require_account,
    save_account,
)
from imessage_bridge._broker import (
    call_broker,
    print_broker_panel,
    register_tunnel,
)

out = Console()
err = Console(stderr=True)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

# ---------- Build the bridge Typer app ----------
#
# We start with imessage-mcp's app (which already has `setup` and `token`)
# and REPLACE its `serve` with our broker-aware variant. Typer stores
# commands in `app.registered_commands`; rewriting that list is the
# cleanest way to override.

app = mcp_app
app.info.help = (
    "Connected CLI for imessage-mcp — stable broker URL, account-managed keys."
)
# Drop the standalone `serve` so we can re-register the broker-aware one.
app.registered_commands = [
    c for c in app.registered_commands if c.name != "serve"
]


@app.command()
def serve(
    host: Annotated[
        str, typer.Option(help="Bind address. Keep 127.0.0.1 unless you know why.")
    ] = DEFAULT_HOST,
    port: Annotated[int, typer.Option(help="TCP port.")] = DEFAULT_PORT,
    public: Annotated[
        bool,
        typer.Option(
            "--public",
            help="Tunnel via cloudflared and (if logged in) register with the broker.",
        ),
    ] = False,
    rotate_token: Annotated[
        bool, typer.Option("--rotate-token", help="Generate a fresh local bearer token first.")
    ] = False,
    backend_url: Annotated[
        str,
        typer.Option(
            envvar="IMESSAGE_BRIDGE_BACKEND_URL",
            help="Broker URL (override for staging/prod).",
        ),
    ] = DEFAULT_BACKEND_URL,
) -> None:
    """Run the MCP server; with --public also tunnel + register with the broker."""
    if not CHAT_DB.exists():
        err.print(f"[red]chat.db not found at {CHAT_DB}[/red]")
        err.print("Run [cyan]imessage-bridge setup[/cyan] first.")
        raise typer.Exit(code=1)

    token = load_or_create_token(rotate=rotate_token)
    local_url = f"http://{host}:{port}"
    print_config_panel(local_url, token, public=False)
    if _HAS_SEND:
        out.print(
            "[yellow]send_message tool is registered "
            "(imessage-mcp-send detected).[/yellow]"
        )

    tunnel_proc: subprocess.Popen | None = None
    if public:
        account = load_account()  # captured by closure

        def on_url(url: str) -> None:
            allow_tunnel_host(urlparse(url).netloc, url)
            if account is not None:
                api_key, _user_id = account
                if register_tunnel(backend_url, api_key, url, token):
                    print_broker_panel(backend_url, api_key)
                    return
                # Registration failed — fall back to direct cloudflare URL.
                print_config_panel(url, token, public=True)
            else:
                print_config_panel(url, token, public=True)
                out.print(
                    "[dim]Tip: run `imessage-bridge signup` to also share "
                    "this via a stable broker URL.[/dim]"
                )

        tunnel_proc = spawn_cloudflared(local_url, on_url=on_url)
        out.print("[dim]Waiting for cloudflared to establish the tunnel...[/dim]")

    try:
        serve_mcp(host=host, port=port, token=token)
    finally:
        if tunnel_proc is not None and tunnel_proc.poll() is None:
            tunnel_proc.terminate()
            try:
                tunnel_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                tunnel_proc.kill()


# ---------- account commands ----------


@app.command()
def signup(
    backend_url: Annotated[
        str, typer.Option(envvar="IMESSAGE_BRIDGE_BACKEND_URL")
    ] = DEFAULT_BACKEND_URL,
) -> None:
    """Create a new account on the broker and save your API key."""
    if load_account() is not None:
        err.print(
            "[yellow]You're already logged in.[/yellow] "
            "Run [cyan]imessage-bridge logout[/cyan] first."
        )
        raise typer.Exit(code=1)

    out.print(Panel.fit("Create a new account", border_style="cyan"))
    email, password = prompt_credentials(confirm_password=True)
    data = call_broker(
        backend_url, "/api/auth/signup", {"email": email, "password": password}
    )
    save_account(data["api_key"], data["user_id"])

    out.print(f"\n[green]Account created.[/green]")
    out.print(f"User ID: [cyan]{data['user_id']}[/cyan]")
    out.print(f"API key saved to [dim]{API_KEY_FILE}[/dim]")
    out.print(
        "\nNext: [cyan]imessage-bridge serve --public[/cyan] to register your tunnel."
    )


@app.command("new-key")
def new_key(
    backend_url: Annotated[
        str, typer.Option(envvar="IMESSAGE_BRIDGE_BACKEND_URL")
    ] = DEFAULT_BACKEND_URL,
) -> None:
    """Mint a fresh API key for your account (asks for email + password)."""
    out.print(Panel.fit("Mint a new API key", border_style="cyan"))
    email, password = prompt_credentials(confirm_password=False)
    data = call_broker(
        backend_url, "/api/auth/login", {"email": email, "password": password}
    )
    save_account(data["api_key"], data["user_id"])
    out.print(f"\n[green]New API key saved.[/green]")
    out.print(f"User ID: [cyan]{data['user_id']}[/cyan]")


@app.command()
def logout() -> None:
    """Forget the local API key + user ID. (The key stays valid server-side.)"""
    removed = []
    for p in (API_KEY_FILE, USER_ID_FILE):
        if p.exists():
            p.unlink()
            removed.append(p.name)
    if not removed:
        out.print("[yellow]Nothing to log out from.[/yellow]")
        return
    out.print(f"[green]Logged out.[/green] Removed: {', '.join(removed)}")
    out.print("[dim]The API key is still valid server-side until you revoke it.[/dim]")


@app.command()
def whoami() -> None:
    """Show the currently logged-in user (if any)."""
    account = load_account()
    if account is None:
        out.print(
            "[yellow]Not logged in.[/yellow] "
            "Run [cyan]imessage-bridge signup[/cyan] or [cyan]new-key[/cyan]."
        )
        raise typer.Exit(code=1)
    api_key, user_id = account
    out.print(f"User ID: [cyan]{user_id}[/cyan]")
    out.print(f"API key: [dim]{api_key[:8]}…[/dim] (loaded from {API_KEY_FILE})")


# ---------- API key management subcommand group ----------

keys_app = typer.Typer(help="List and revoke your API keys.")
app.add_typer(keys_app, name="keys")


@keys_app.command("list")
def keys_list(
    backend_url: Annotated[
        str, typer.Option(envvar="IMESSAGE_BRIDGE_BACKEND_URL")
    ] = DEFAULT_BACKEND_URL,
) -> None:
    """List all API keys on your account. (Current key marked with ●.)"""
    api_key, _ = require_account()
    try:
        resp = httpx.get(
            f"{backend_url}/api/keys",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
    except httpx.HTTPError as e:
        err.print(f"[red]Network error:[/red] {e}")
        raise typer.Exit(code=1)
    if resp.status_code != 200:
        err.print(f"[red]{resp.status_code}:[/red] {resp.text}")
        raise typer.Exit(code=1)

    table = Table(title="API keys")
    table.add_column("", width=2)
    table.add_column("ID", style="cyan")
    table.add_column("Created", style="dim")
    table.add_column("Last used", style="dim")
    for k in resp.json():
        marker = "[green]●[/green]" if k["current"] else " "
        last = k["last_used_at"][:19].replace("T", " ") if k["last_used_at"] else "—"
        created = k["created_at"][:19].replace("T", " ")
        table.add_row(marker, k["id"], created, last)
    out.print(table)
    out.print("[dim]Revoke with:[/dim] [cyan]imessage-bridge keys revoke <ID>[/cyan]")


@keys_app.command("revoke")
def keys_revoke(
    key_id: Annotated[str, typer.Argument(help="Key UUID from `keys list`.")],
    backend_url: Annotated[
        str, typer.Option(envvar="IMESSAGE_BRIDGE_BACKEND_URL")
    ] = DEFAULT_BACKEND_URL,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Skip the confirmation prompt.")
    ] = False,
) -> None:
    """Revoke an API key by ID."""
    api_key, _ = require_account()
    if not yes and not typer.confirm(f"Revoke key {key_id}?", default=False):
        out.print("[yellow]Canceled.[/yellow]")
        raise typer.Exit(code=0)
    try:
        resp = httpx.delete(
            f"{backend_url}/api/keys/{key_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
    except httpx.HTTPError as e:
        err.print(f"[red]Network error:[/red] {e}")
        raise typer.Exit(code=1)
    if resp.status_code == 204:
        out.print(f"[green]Revoked[/green] {key_id}")
        return
    if resp.status_code == 404:
        err.print(f"[red]No such key on your account.[/red]")
        raise typer.Exit(code=1)
    err.print(f"[red]{resp.status_code}:[/red] {resp.text}")
    raise typer.Exit(code=1)


def main() -> None:
    app()
