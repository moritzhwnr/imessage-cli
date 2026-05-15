"""HTTP calls to the broker.

Two call shapes:
  - `call_broker(...)` — auth flows. Raises typer.Exit on failure with a
    clean message (the user is interactive; failing hard is right).
  - `register_tunnel(...)` — runtime side-effect. Returns bool, prints a
    yellow warning on failure. Broker downtime must not kill the local
    server; the cloudflare URL still works directly.
"""

from __future__ import annotations

import json

import httpx
import typer
from rich.console import Console
from rich.panel import Panel

out = Console()
err = Console(stderr=True)


def call_broker(
    backend_url: str, path: str, payload: dict, *, api_key: str | None = None
) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        resp = httpx.post(
            f"{backend_url}{path}", json=payload, headers=headers, timeout=10.0
        )
    except httpx.ConnectError:
        err.print(
            f"[red]Cannot reach broker at {backend_url}[/red]\n"
            f"Is it running? (Set IMESSAGE_BRIDGE_BACKEND_URL or "
            f"start the broker locally.)"
        )
        raise typer.Exit(code=1)
    except httpx.HTTPError as e:
        err.print(f"[red]Network error:[/red] {type(e).__name__}: {e}")
        raise typer.Exit(code=1)

    if resp.status_code >= 400:
        try:
            msg = resp.json().get("error", resp.text)
        except ValueError:
            msg = resp.text or "<empty body>"
        err.print(f"[red]{resp.status_code} from {path}:[/red] {msg}")
        raise typer.Exit(code=1)

    return resp.json() if resp.content else {}


def register_tunnel(
    backend_url: str, api_key: str, url: str, tunnel_token: str
) -> bool:
    """Returns True on success, False on any failure (logged + soft-failed)."""
    try:
        resp = httpx.post(
            f"{backend_url}/api/tunnels/register",
            json={"url": url, "tunnel_token": tunnel_token},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
    except httpx.HTTPError as e:
        err.print(
            f"[yellow]Broker registration failed ({type(e).__name__}). "
            f"Tunnel still usable directly.[/yellow]"
        )
        return False
    if resp.status_code >= 400:
        try:
            msg = resp.json().get("error", resp.text)
        except ValueError:
            msg = resp.text or "<empty body>"
        err.print(
            f"[yellow]Broker rejected registration ({resp.status_code}): {msg}[/yellow]"
        )
        return False
    return True


def print_broker_panel(backend_url: str, api_key: str) -> None:
    """Green panel — the broker URL is the 'preferred' connection point.

    The URL is identical for every user; the API key identifies who's
    calling. This is the shape Poke/Claude Desktop/Cursor expect.
    """
    public_url = f"{backend_url.rstrip('/')}/api/mcp"
    config_snippet = json.dumps(
        {
            "mcpServers": {
                "imessage": {
                    "url": public_url,
                    "headers": {"Authorization": f"Bearer {api_key}"},
                }
            }
        },
        indent=2,
    )
    out.print(
        Panel(
            f"[bold]{public_url}[/bold]\n"
            "[dim]Stable URL — survives cloudflared restarts as long as this "
            "CLI re-registers.[/dim]\n\n"
            "Add to your MCP client config:\n"
            f"[green]{config_snippet}[/green]",
            title="imessage-bridge (BROKER)",
            border_style="green",
        )
    )
