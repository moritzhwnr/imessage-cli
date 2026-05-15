"""cloudflared subprocess + the config-panel renderer.

Exported so imessage-bridge can reuse both: spawn the same tunnel, then
print its own broker-aware config panel instead of the local one.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
from typing import Callable

import typer
from rich.console import Console
from rich.panel import Panel

out = Console()
err = Console(stderr=True)

# Cloudflare Quick Tunnel hostnames look like https://<slug>.trycloudflare.com .
TRYCLOUDFLARE_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def spawn_cloudflared(
    local_url: str, on_url: Callable[[str], None]
) -> subprocess.Popen:
    """Start `cloudflared tunnel` and call `on_url(public_url)` once detected.

    Notes:
      - `cloudflared` must be on PATH. shutil.which() is the portable way.
      - cloudflared logs to stderr → merge with stdout so we read one stream.
      - bufsize=1 = line-buffered (Python's 4KB default would delay 30s).
      - The watcher is a daemon thread, so it dies with the process.
    """
    if shutil.which("cloudflared") is None:
        err.print("[red]cloudflared not found on PATH.[/red]")
        err.print("Install it: [cyan]brew install cloudflared[/cyan]")
        raise typer.Exit(code=1)

    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", local_url, "--no-autoupdate"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    def watch() -> None:
        seen = False
        assert proc.stdout is not None
        for line in iter(proc.stdout.readline, ""):
            if not seen:
                m = TRYCLOUDFLARE_URL_RE.search(line)
                if m:
                    seen = True
                    on_url(m.group(0))

    threading.Thread(target=watch, daemon=True).start()
    return proc


def print_config_panel(public_url: str, token: str, *, public: bool) -> None:
    """Render the copy-pasteable Claude Desktop config block.

    `public=True` styles the panel as a public tunnel warning (yellow + a
    "rotate if you leak it" reminder). `public=False` is cyan/local-only.
    """
    config_snippet = json.dumps(
        {
            "mcpServers": {
                "imessage": {
                    "url": f"{public_url}/mcp",
                    "headers": {"Authorization": f"Bearer {token}"},
                }
            }
        },
        indent=2,
    )
    title = "imessage-mcp (PUBLIC via cloudflared)" if public else "imessage-mcp"
    border = "yellow" if public else "cyan"
    warning = (
        "\n[yellow]⚠ Anyone with this URL + token can read your messages. "
        "Rotate the token if you leak it.[/yellow]\n"
        if public
        else ""
    )
    out.print(
        Panel(
            f"[bold]{public_url}/mcp[/bold]\n"
            f"[dim]Token saved to ~/.config/imessage-mcp/token[/dim]\n"
            f"{warning}\n"
            "Add to Claude Desktop's [cyan]claude_desktop_config.json[/cyan]:\n"
            f"[green]{config_snippet}[/green]",
            title=title,
            border_style=border,
        )
    )
