"""Typer CLI for imessage-mcp — `serve`, `setup`, `token`.

This is the standalone open-core CLI. No broker, no signup. Power users who
don't want a third-party service install just this package.
"""

from __future__ import annotations

import subprocess
from typing import Annotated
from urllib.parse import urlparse

import typer
from rich.console import Console
from rich.panel import Panel

from imessage_mcp._imessage import CHAT_DB
from imessage_mcp.config import TOKEN_FILE, load_or_create_token
from imessage_mcp.server import allow_tunnel_host, serve_mcp
from imessage_mcp.tunnel import print_config_panel, spawn_cloudflared

out = Console()
err = Console(stderr=True)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

app = typer.Typer(
    no_args_is_help=True,
    help="MCP server exposing your local iMessage history (read-only).",
)


@app.command()
def serve(
    host: Annotated[
        str, typer.Option(help="Bind address. Keep 127.0.0.1 unless you know why.")
    ] = DEFAULT_HOST,
    port: Annotated[int, typer.Option(help="TCP port.")] = DEFAULT_PORT,
    public: Annotated[
        bool,
        typer.Option("--public", help="Expose via a cloudflared Quick Tunnel."),
    ] = False,
    rotate_token: Annotated[
        bool, typer.Option("--rotate-token", help="Generate a fresh bearer token first.")
    ] = False,
) -> None:
    """Run the MCP server (locally, or publicly via cloudflared with --public)."""
    if not CHAT_DB.exists():
        err.print(f"[red]chat.db not found at {CHAT_DB}[/red]")
        err.print("Run [cyan]imessage-mcp setup[/cyan] to grant Full Disk Access.")
        raise typer.Exit(code=1)

    token = load_or_create_token(rotate=rotate_token)
    local_url = f"http://{host}:{port}"
    print_config_panel(local_url, token, public=False)

    tunnel_proc: subprocess.Popen | None = None
    if public:
        def on_url(url: str) -> None:
            allow_tunnel_host(urlparse(url).netloc, url)
            print_config_panel(url, token, public=True)

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


@app.command()
def setup() -> None:
    """Open System Settings to grant Full Disk Access to your terminal."""
    pane = "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
    subprocess.run(["open", pane], check=True)
    out.print(
        Panel(
            "[bold]Full Disk Access[/bold] pane opened.\n"
            "1. Click [cyan]+[/cyan] and add your terminal app.\n"
            "2. Toggle it [green]on[/green].\n"
            "3. [bold]Fully quit[/bold] the terminal (Cmd+Q) and reopen it.\n"
            "4. Run [cyan]imessage-mcp serve[/cyan] to verify.",
            border_style="cyan",
        )
    )


@app.command()
def token(
    rotate: Annotated[
        bool, typer.Option("--rotate", help="Generate a new token, replacing the old.")
    ] = False,
) -> None:
    """Print the local bearer token (or rotate it)."""
    t = load_or_create_token(rotate=rotate)
    out.print(t)
    if rotate:
        err.print(
            "[yellow]Rotated — any connected clients will start failing 401.[/yellow]"
        )


def main() -> None:
    app()
