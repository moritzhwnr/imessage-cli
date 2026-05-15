"""Local account state: API key + user ID on disk, password prompts."""

from __future__ import annotations

import os
from pathlib import Path

import questionary
import typer
from rich.console import Console

out = Console()
err = Console(stderr=True)

CONFIG_DIR = Path.home() / ".config" / "imessage-bridge"
API_KEY_FILE = CONFIG_DIR / "api_key"
USER_ID_FILE = CONFIG_DIR / "user_id"

DEFAULT_BACKEND_URL = os.environ.get(
    "IMESSAGE_BRIDGE_BACKEND_URL",
    os.environ.get("IMESSAGE_MCP_BACKEND_URL", "http://localhost:3000"),
)


def save_account(api_key: str, user_id: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    API_KEY_FILE.write_text(api_key)
    API_KEY_FILE.chmod(0o600)
    USER_ID_FILE.write_text(user_id)


def load_account() -> tuple[str, str] | None:
    if not API_KEY_FILE.exists() or not USER_ID_FILE.exists():
        return None
    return API_KEY_FILE.read_text().strip(), USER_ID_FILE.read_text().strip()


def require_account() -> tuple[str, str]:
    account = load_account()
    if account is None:
        err.print(
            "[red]Not logged in.[/red] "
            "Run [cyan]imessage-bridge signup[/cyan] or "
            "[cyan]imessage-bridge new-key[/cyan] first."
        )
        raise typer.Exit(code=1)
    return account


def prompt_credentials(confirm_password: bool) -> tuple[str, str]:
    """Interactive email + password prompt. Returns (email, password)."""
    email = questionary.text("Email:").ask()
    if not email:
        out.print("[yellow]Canceled.[/yellow]")
        raise typer.Exit(code=0)

    password = questionary.password("Password:").ask()
    if not password:
        out.print("[yellow]Canceled.[/yellow]")
        raise typer.Exit(code=0)

    if confirm_password:
        confirm = questionary.password("Confirm password:").ask()
        if confirm != password:
            err.print("[red]Passwords don't match.[/red]")
            raise typer.Exit(code=1)

    return email, password
