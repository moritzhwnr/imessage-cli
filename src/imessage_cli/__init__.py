"""imessage-cli — a small CLI for reading and sending iMessages on macOS.

How the CLI wiring works:
  1. We build a Typer "app" object and attach commands to it with @app.command().
  2. Typer reads each command's type-hinted parameters and turns them into
     CLI arguments/options automatically (no manual argparse setup).
  3. `main()` runs the app. pyproject.toml's [project.scripts] points the
     shell command `imessage-cli` at this `main`, so after `uv sync` you can
     run `uv run imessage-cli ...` and Typer dispatches to the right command.
"""

from __future__ import annotations

import sqlite3
import subprocess
from datetime import datetime
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

# These primitives now live in the published imessage-mcp package. Importing
# from there keeps a single source of truth for chat.db access.
from imessage_mcp._imessage import (
    APPLE_EPOCH,
    CHAT_DB,
    apple_ts_to_dt as _apple_ts_to_dt_impl,
    open_db as _open_db_impl,
)

# A Typer app is just a registry of commands. `no_args_is_help=True` makes
# running `imessage-cli` with no args print --help instead of doing nothing,
# which is the friendlier convention.
app = typer.Typer(
    no_args_is_help=True,
    help="Read and send iMessages from the command line.",
)

# `rich` Console writes to stderr here so command output stays clean for piping.
# Convention: data goes to stdout, status/errors go to stderr.
err = Console(stderr=True)
out = Console()

# Re-export so existing imports from `imessage_cli` still work.
# (Both CHAT_DB and APPLE_EPOCH come from imessage_mcp._imessage now.)


def _open_db() -> sqlite3.Connection:
    """Open chat.db read-only with CLI-friendly errors.

    Delegates to imessage_mcp.open_db, then converts its exceptions into
    typer.Exit(1) + a colorized hint for the user. The library throws;
    the CLI translates.
    """
    try:
        return _open_db_impl()
    except FileNotFoundError as e:
        err.print(f"[red]{e}[/red]")
        err.print("Run [cyan]uv run imessage-cli setup[/cyan] to grant Full Disk Access.")
        raise typer.Exit(code=1) from e
    except sqlite3.OperationalError as e:
        err.print(f"[red]Cannot open chat.db:[/red] {e}")
        err.print(
            "Your terminal probably lacks [bold]Full Disk Access[/bold]. Fix:\n"
            "  1. Run [cyan]uv run imessage-cli setup[/cyan]\n"
            "  2. Add your terminal app and toggle it on\n"
            "  3. [bold]Fully quit[/bold] the terminal (Cmd+Q) and reopen it"
        )
        raise typer.Exit(code=1) from e


def _apple_ts_to_dt(ts: int) -> datetime:
    """Compat shim — delegates to imessage_mcp."""
    return _apple_ts_to_dt_impl(ts)


# ---------- commands ----------
#
# Each @app.command() function becomes a subcommand. Function parameters
# become CLI inputs:
#   - parameters with NO default  -> positional ARGUMENTS  (required)
#   - parameters WITH a default   -> --options             (optional)
# Use `Annotated[T, typer.Option/Argument(...)]` to attach help text, short
# flags, etc. without losing the type hint.


@app.command()
def chats(
    limit: Annotated[
        int, typer.Option("--limit", "-n", help="How many chats to show.")
    ] = 20,
) -> None:
    """List your most recent iMessage conversations."""
    conn = _open_db()
    # Each chat's most recent message time, joined to the chat's display name
    # or the handle (phone/email) of the other party.
    rows = conn.execute(
        """
        SELECT
            c.ROWID                                         AS chat_id,
            COALESCE(NULLIF(c.display_name, ''), h.id, '?') AS who,
            MAX(m.date)                                     AS last_ts
        FROM chat c
        JOIN chat_message_join cmj ON cmj.chat_id = c.ROWID
        JOIN message m             ON m.ROWID = cmj.message_id
        LEFT JOIN chat_handle_join chj ON chj.chat_id = c.ROWID
        LEFT JOIN handle h             ON h.ROWID = chj.handle_id
        GROUP BY c.ROWID
        ORDER BY last_ts DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    table = Table(title=f"Recent chats (top {limit})")
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Who")
    table.add_column("Last message", style="dim")
    for chat_id, who, last_ts in rows:
        when = _apple_ts_to_dt(last_ts).astimezone().strftime("%Y-%m-%d %H:%M")
        table.add_row(str(chat_id), who, when)
    out.print(table)


@app.command()
def messages(
    chat_id: Annotated[int, typer.Argument(help="Chat ID (see `chats` command).")],
    limit: Annotated[
        int, typer.Option("--limit", "-n", help="How many messages to show.")
    ] = 20,
) -> None:
    """Show the latest messages in a chat."""
    conn = _open_db()
    rows = conn.execute(
        """
        SELECT m.date, m.is_from_me, COALESCE(m.text, '')
        FROM message m
        JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
        WHERE cmj.chat_id = ?
        ORDER BY m.date DESC
        LIMIT ?
        """,
        (chat_id, limit),
    ).fetchall()

    # We fetched newest-first for the LIMIT, but want to print oldest-first.
    for ts, is_from_me, text in reversed(rows):
        when = _apple_ts_to_dt(ts).astimezone().strftime("%H:%M")
        who = "[green]me[/green]" if is_from_me else "[blue]them[/blue]"
        out.print(f"[dim]{when}[/dim] {who}: {text}")


@app.command()
def setup(
    ping: Annotated[
        str | None,
        typer.Option(
            "--ping",
            help="Your own iMessage handle. Sends a test message to trigger "
            "the Messages.app Automation permission prompt.",
        ),
    ] = None,
) -> None:
    """Grant macOS permissions: opens Full Disk Access, then optionally pings yourself."""
    # macOS exposes Settings panes via x-apple.systempreferences:// URLs.
    # `open` is the macOS equivalent of xdg-open; it routes the URL to the
    # right app (here: System Settings).
    pane = "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
    subprocess.run(["open", pane], check=True)
    out.print("[bold]Full Disk Access[/bold] pane opened.")
    out.print("1. Click [cyan]+[/cyan] and add your terminal app.")
    out.print("2. Toggle it [green]on[/green].")
    out.print("3. Fully quit your terminal (Cmd+Q) and reopen it.\n")

    # If --ping wasn't passed, prompt interactively. typer.prompt() is just a
    # wrapper around input() that integrates nicely with the Typer UX. Pressing
    # Enter accepts the empty default and skips the ping step.
    if ping is None:
        ping = typer.prompt(
            "Send a test iMessage to yourself now to trigger the Messages "
            "automation prompt?\nEnter your handle (or press Enter to skip)",
            default="",
            show_default=False,
        )

    if not ping:
        out.print(
            "Skipped ping. When you first run [cyan]send[/cyan] or "
            "[cyan]reply[/cyan], macOS will ask permission to control Messages."
        )
        return

    out.print(f"\nSending test message to [bold]{ping}[/bold]...")
    # Reuse the same send path the real `send` command uses. macOS will pop up
    # the Automation prompt the first time osascript talks to Messages.app.
    _send_to_handle(ping, "imessage-cli setup test ✓")


def _send_to_handle(recipient: str, text: str) -> None:
    """Send an iMessage to a handle (phone/email). Shared by `send` and `reply`."""
    # AppleScript is the simplest way to send: ask Messages.app to do it for us.
    # We pass `recipient` and `text` as positional args to the script (not
    # interpolated into the source) so a user can't break quoting or inject
    # AppleScript code via the message body.
    script = """
    on run argv
        set theBuddy to item 1 of argv
        set theText  to item 2 of argv
        tell application "Messages"
            set targetService to 1st service whose service type = iMessage
            set theBuddy to buddy theBuddy of targetService
            send theText to theBuddy
        end tell
    end run
    """
    result = subprocess.run(
        ["osascript", "-e", script, recipient, text],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        err.print(f"[red]Send failed:[/red] {result.stderr.strip()}")
        raise typer.Exit(code=1)
    out.print(f"[green]Sent[/green] to {recipient}")


@app.command()
def send(
    recipient: Annotated[
        str, typer.Argument(help="Phone number (E.164) or iMessage email.")
    ],
    text: Annotated[str, typer.Argument(help="Message text to send.")],
) -> None:
    """Send an iMessage to a phone number or email."""
    _send_to_handle(recipient, text)


@app.command()
def reply(
    chat_id: Annotated[
        int, typer.Argument(help="Chat ID to reply to (see `chats` command).")
    ],
    text: Annotated[str, typer.Argument(help="Message text to send.")],
) -> None:
    """Reply to a chat by its ID. 1:1 chats only for now."""
    conn = _open_db()
    handles = conn.execute(
        """
        SELECT h.id
        FROM chat_handle_join chj
        JOIN handle h ON h.ROWID = chj.handle_id
        WHERE chj.chat_id = ?
        """,
        (chat_id,),
    ).fetchall()

    if not handles:
        err.print(f"[red]No participants found for chat {chat_id}.[/red]")
        raise typer.Exit(code=1)
    if len(handles) > 1:
        # Group chats need AppleScript's `text chat id` API with the chat's
        # GUID, which is flaky on modern macOS. Skipping for now.
        err.print(
            f"[red]Chat {chat_id} is a group ({len(handles)} participants); "
            "group replies aren't supported yet.[/red]"
        )
        raise typer.Exit(code=1)

    _send_to_handle(handles[0][0], text)


def main() -> None:
    """Entry point referenced by pyproject.toml's [project.scripts]."""
    app()
