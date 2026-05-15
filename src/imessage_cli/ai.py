"""imessage-ai — interactive AI chat that can read iMessages and draft replies.

How it fits together:
  1. First launch: no config file → prompt for provider (Claude/OpenAI) + API key,
     save to ~/.config/imessage-ai/config.env, load it as environment variables.
  2. REPL loop: user types a line.
       - Lines starting with "/" are SLASH COMMANDS — handled locally (no LLM).
       - Anything else is sent to the LLM with a system prompt + tool definitions.
  3. The LLM has TOOLS it can call:
       - list_chats, read_messages, draft_reply, send_message
     We provide one schema (tool dict) but translate it per-provider, because
     Anthropic and OpenAI use different tool-calling shapes.
  4. The agentic LOOP keeps calling the model until it stops asking for tools.
     Each tool result feeds back into the model's context.

The interesting CLI-learning content is in the comments, not the docstrings.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable

import questionary
import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

# Reuse the helpers we already built in __init__.py. The single underscore
# prefix is the Python "internal but importable" convention — fine for a
# sibling module in the same package.
from imessage_cli import (
    APPLE_EPOCH,
    CHAT_DB,
    _apple_ts_to_dt,
    _open_db,
    _send_to_handle,
)

out = Console()
err = Console(stderr=True)

# Config file location follows the XDG-ish convention. A real ~/.config dir
# works on macOS even though Apple doesn't formally use XDG, because we just
# create it ourselves.
CONFIG_DIR = Path.home() / ".config" / "imessage-ai"
CONFIG_FILE = CONFIG_DIR / "config.env"


# =============================================================================
# CONFIG — first-run setup + load
# =============================================================================


def _load_or_setup_config() -> dict[str, str]:
    """Load config from disk, or run the interactive setup if missing/empty."""
    if CONFIG_FILE.exists():
        # load_dotenv mutates os.environ. That means the SDK clients
        # (anthropic.Anthropic(), openai.OpenAI()) pick up the keys for free —
        # they read ANTHROPIC_API_KEY / OPENAI_API_KEY from the environment.
        load_dotenv(CONFIG_FILE, override=False)
        cfg = {
            "provider": os.environ.get("IMESSAGE_AI_PROVIDER", ""),
            "anthropic_key": os.environ.get("ANTHROPIC_API_KEY", ""),
            "openai_key": os.environ.get("OPENAI_API_KEY", ""),
        }
        if cfg["provider"] in ("claude", "openai"):
            return cfg

    return _run_setup()


def _run_setup() -> dict[str, str]:
    """Interactive first-run setup. Writes config to disk, returns it."""
    out.print(
        Panel.fit(
            "Welcome to [bold]imessage-ai[/bold].\n"
            "Let's pick an LLM provider and save your API key.",
            border_style="cyan",
        )
    )
    # questionary.select renders an arrow-key picker (↑/↓ + Enter, or j/k).
    # Returning None means the user hit Ctrl-C in the picker — treat that as
    # "cancel setup" and bail cleanly.
    provider = questionary.select(
        "Choose your LLM provider",
        choices=[
            questionary.Choice("Claude (Anthropic)", value="claude"),
            questionary.Choice("OpenAI (GPT)", value="openai"),
        ],
        default="claude",
        instruction="(use arrow keys, enter to select)",
    ).ask()
    if provider is None:
        out.print("[yellow]Setup canceled. Goodbye![/yellow]")
        raise typer.Exit(code=0)

    # typer.prompt with hide_input=True turns off echo, like password fields.
    # The key never gets written to your shell history this way.
    key_var = "ANTHROPIC_API_KEY" if provider == "claude" else "OPENAI_API_KEY"
    key = typer.prompt(f"Paste your {key_var}", hide_input=True).strip()

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Write the env file ourselves rather than calling python-dotenv's writer —
    # the format is just KEY=VALUE per line. Quote the value so spaces don't
    # break parsing.
    CONFIG_FILE.write_text(
        f"IMESSAGE_AI_PROVIDER={provider}\n"
        f'{key_var}="{key}"\n'
    )
    # chmod 600 — only the owner can read. Same convention as ~/.ssh keys.
    CONFIG_FILE.chmod(0o600)

    out.print(f"[green]Saved to {CONFIG_FILE}[/green]")
    # Re-load so the rest of the process sees the new env vars.
    load_dotenv(CONFIG_FILE, override=True)
    return {
        "provider": provider,
        "anthropic_key": os.environ.get("ANTHROPIC_API_KEY", ""),
        "openai_key": os.environ.get("OPENAI_API_KEY", ""),
    }


# =============================================================================
# TOOLS — what the AI can do on your behalf
# =============================================================================
#
# We define tools in a provider-neutral way (name, description, JSON schema)
# and convert to each provider's format below. The actual Python functions
# that execute them live in TOOL_IMPLS.


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "list_chats",
        "description": "List the user's most recent iMessage conversations. "
        "Returns each chat's ID, the other party, and when the last message "
        "was sent. Use this before reading messages or sending replies.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "How many recent chats to return.",
                    "default": 10,
                }
            },
        },
    },
    {
        "name": "read_messages",
        "description": "Read the latest messages from a specific chat. "
        "Use this to understand context before drafting a reply.",
        "input_schema": {
            "type": "object",
            "properties": {
                "chat_id": {
                    "type": "integer",
                    "description": "The chat ID from list_chats.",
                },
                "limit": {
                    "type": "integer",
                    "description": "How many recent messages to return.",
                    "default": 20,
                },
            },
            "required": ["chat_id"],
        },
    },
    {
        "name": "send_message",
        "description": "Send an iMessage to a recipient. The user will be "
        "asked to confirm before the message is actually sent. Provide either "
        "a chat_id (for an existing conversation) OR a recipient (phone/email).",
        "input_schema": {
            "type": "object",
            "properties": {
                "chat_id": {
                    "type": "integer",
                    "description": "ID of an existing chat to reply to.",
                },
                "recipient": {
                    "type": "string",
                    "description": "Phone (E.164) or iMessage email if not using chat_id.",
                },
                "text": {
                    "type": "string",
                    "description": "The exact message text to send.",
                },
            },
            "required": ["text"],
        },
    },
]


def _tool_list_chats(limit: int = 10) -> list[dict[str, Any]]:
    conn = _open_db()
    rows = conn.execute(
        """
        SELECT c.ROWID, COALESCE(NULLIF(c.display_name, ''), h.id, '?'), MAX(m.date)
        FROM chat c
        JOIN chat_message_join cmj ON cmj.chat_id = c.ROWID
        JOIN message m ON m.ROWID = cmj.message_id
        LEFT JOIN chat_handle_join chj ON chj.chat_id = c.ROWID
        LEFT JOIN handle h ON h.ROWID = chj.handle_id
        GROUP BY c.ROWID ORDER BY MAX(m.date) DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "chat_id": cid,
            "who": who,
            "last_message_at": _apple_ts_to_dt(ts).astimezone().isoformat(),
        }
        for cid, who, ts in rows
    ]


def _tool_read_messages(chat_id: int, limit: int = 20) -> list[dict[str, Any]]:
    conn = _open_db()
    rows = conn.execute(
        """
        SELECT m.date, m.is_from_me, COALESCE(m.text, '')
        FROM message m
        JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
        WHERE cmj.chat_id = ?
        ORDER BY m.date DESC LIMIT ?
        """,
        (chat_id, limit),
    ).fetchall()
    return [
        {
            "at": _apple_ts_to_dt(ts).astimezone().isoformat(),
            "from": "me" if is_me else "them",
            "text": text,
        }
        for ts, is_me, text in reversed(rows)
    ]


def _tool_send_message(
    text: str, chat_id: int | None = None, recipient: str | None = None
) -> str:
    """Send a message, but ALWAYS ask the user to confirm first."""
    # Resolve chat_id -> recipient handle for 1:1 chats.
    if chat_id is not None and recipient is None:
        conn = _open_db()
        handles = conn.execute(
            """
            SELECT h.id FROM chat_handle_join chj
            JOIN handle h ON h.ROWID = chj.handle_id
            WHERE chj.chat_id = ?
            """,
            (chat_id,),
        ).fetchall()
        if not handles:
            return f"ERROR: no handles found for chat {chat_id}"
        if len(handles) > 1:
            return f"ERROR: chat {chat_id} is a group ({len(handles)} people); not supported"
        recipient = handles[0][0]

    if not recipient:
        return "ERROR: need either chat_id or recipient"

    # Human-in-the-loop gate. The AI cannot send anything without an explicit
    # "y" from the user — this is the same agentic-design pattern used for any
    # irreversible action (delete, post, transfer, etc.).
    out.print(Panel(f"[bold]Send to {recipient}:[/bold]\n{text}", border_style="yellow"))
    if not typer.confirm("Send this message?", default=False):
        return "USER_CANCELED: the user declined to send the message."

    try:
        _send_to_handle(recipient, text)
        return f"SENT to {recipient}"
    except typer.Exit:
        # _send_to_handle raises typer.Exit on failure; swallow it so the loop
        # continues and the AI sees the error.
        return f"ERROR: send to {recipient} failed"


TOOL_IMPLS: dict[str, Callable[..., Any]] = {
    "list_chats": _tool_list_chats,
    "read_messages": _tool_read_messages,
    "send_message": _tool_send_message,
}


def _run_tool(name: str, args: dict[str, Any]) -> str:
    """Dispatch + serialize the result for the model."""
    fn = TOOL_IMPLS.get(name)
    if fn is None:
        return f"ERROR: unknown tool {name!r}"
    try:
        result = fn(**args)
    except (sqlite3.Error, TypeError, ValueError) as e:
        return f"ERROR: {type(e).__name__}: {e}"
    # Tools must return JSON strings to the model — that's the contract.
    return json.dumps(result, default=str)


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

SYSTEM_PROMPT = """You are an iMessage assistant running inside a CLI on the user's Mac.

You help the user understand and reply to iMessages. You have tools to list
conversations, read message history, and send messages.

Guidelines:
- When asked to draft or send a reply, FIRST read recent messages in the chat
  to understand context, THEN compose a reply that matches the user's tone.
- Show the user the draft and ask if they want to refine it before sending.
- The send_message tool always asks the user to confirm — you can call it,
  but you don't bypass that confirmation.
- Keep responses short. The user is in a terminal; long markdown walls are
  annoying.
- Never invent message content or fabricate participants. If you don't know,
  call a tool.
"""


# =============================================================================
# CLAUDE BACKEND
# =============================================================================


def _claude_tools() -> list[dict[str, Any]]:
    # Anthropic uses {name, description, input_schema}. Our TOOL_SCHEMAS
    # already match — just pass through.
    return TOOL_SCHEMAS


def _claude_turn(client: Any, messages: list[dict[str, Any]]) -> str:
    """One user-visible turn = one or more API calls (agentic loop)."""
    while True:
        # Opus 4.7 with adaptive thinking — recommended in the API skill.
        # cache_control on system caches the system prompt + tool defs, so
        # repeated turns in the same REPL only pay for the new messages.
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=_claude_tools(),
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            # Pull the final text out of the content blocks.
            text = "".join(b.text for b in response.content if b.type == "text")
            messages.append({"role": "assistant", "content": response.content})
            return text

        if response.stop_reason == "tool_use":
            # Append the assistant's response (including tool_use blocks)
            # BEFORE running tools. Order matters: assistant's tool_use →
            # user's tool_result must be adjacent.
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result_str = _run_tool(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    }
                )
            messages.append({"role": "user", "content": tool_results})
            continue  # loop again — model now sees the tool results

        # Anything else (refusal, pause_turn, max_tokens) — surface it.
        return f"[stopped: {response.stop_reason}]"


# =============================================================================
# OPENAI BACKEND
# =============================================================================


def _openai_tools() -> list[dict[str, Any]]:
    # OpenAI's shape: {type: "function", function: {name, description, parameters}}
    # `parameters` is what we called `input_schema`.
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in TOOL_SCHEMAS
    ]


def _openai_turn(client: Any, messages: list[dict[str, Any]]) -> str:
    while True:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=_openai_tools(),
        )
        msg = response.choices[0].message

        if msg.tool_calls:
            # OpenAI requires the assistant message to be appended verbatim,
            # then one "tool" role message per tool_call_id.
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                result_str = _run_tool(tc.function.name, args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_str,
                    }
                )
            continue

        # No tool calls — final text.
        text = msg.content or ""
        messages.append({"role": "assistant", "content": text})
        return text


# =============================================================================
# REPL — slash commands + LLM chat
# =============================================================================


def _print_help() -> None:
    out.print(
        Panel(
            "[bold]Slash commands[/bold]\n"
            "  /help            Show this help\n"
            "  /setup           Reconfigure provider / API key\n"
            "  /clear           Clear conversation history\n"
            "  /chats [N]       List recent chats (no AI)\n"
            "  /messages ID [N] Read messages in a chat (no AI)\n"
            "  /quit, /exit     Leave\n\n"
            "Anything else is sent to the AI. The AI can use tools to read\n"
            "your iMessages and draft/send replies (with your confirmation).",
            title="imessage-ai",
            border_style="cyan",
        )
    )


def _handle_slash(line: str) -> bool:
    """Returns True if this was a slash command (so REPL skips the LLM)."""
    parts = line.strip().split()
    cmd, args = parts[0].lower(), parts[1:]

    if cmd in ("/quit", "/exit"):
        out.print("[cyan]Goodbye![/cyan]")
        raise typer.Exit(code=0)
    if cmd == "/help":
        _print_help()
        return True
    if cmd == "/setup":
        _run_setup()
        out.print("[yellow]Reloaded. Restart the chat to pick up changes.[/yellow]")
        raise typer.Exit(code=0)
    if cmd == "/clear":
        return True  # caller resets the history
    if cmd == "/chats":
        limit = int(args[0]) if args else 10
        for c in _tool_list_chats(limit):
            out.print(f"[cyan]{c['chat_id']:>4}[/cyan]  {c['who']:<40}  [dim]{c['last_message_at']}[/dim]")
        return True
    if cmd == "/messages":
        if not args:
            err.print("[red]Usage: /messages CHAT_ID [N][/red]")
            return True
        chat_id = int(args[0])
        limit = int(args[1]) if len(args) > 1 else 20
        for m in _tool_read_messages(chat_id, limit):
            who = "[green]me[/green]" if m["from"] == "me" else "[blue]them[/blue]"
            out.print(f"[dim]{m['at'][11:16]}[/dim] {who}: {m['text']}")
        return True

    err.print(f"[red]Unknown slash command: {cmd}[/red] — try /help")
    return True


def _repl(cfg: dict[str, str]) -> None:
    provider = cfg["provider"]
    if provider == "claude":
        import anthropic

        client: Any = anthropic.Anthropic()
        turn_fn = _claude_turn
    else:
        import openai

        client = openai.OpenAI()
        # OpenAI needs the system prompt as the first message, unlike Anthropic
        # which has a dedicated `system` parameter.
        turn_fn = _openai_turn

    out.print(f"[dim]Provider: {provider}. Type /help for commands, Ctrl-D to quit.[/dim]")
    history: list[dict[str, Any]] = (
        [{"role": "system", "content": SYSTEM_PROMPT}] if provider == "openai" else []
    )

    while True:
        try:
            line = typer.prompt("you", prompt_suffix=" › ").strip()
        except (EOFError, KeyboardInterrupt):
            # Ctrl-D (EOF) or Ctrl-C — friendly exit. The leading print()
            # adds a newline so "Goodbye!" doesn't smash into the ^C.
            out.print()
            out.print("[cyan]Goodbye![/cyan]")
            return

        if not line:
            continue
        if line.startswith("/"):
            # /clear is the one slash command that touches REPL state
            if line.strip().lower() == "/clear":
                history = (
                    [{"role": "system", "content": SYSTEM_PROMPT}]
                    if provider == "openai"
                    else []
                )
                out.print("[yellow]Conversation cleared.[/yellow]")
                continue
            _handle_slash(line)
            continue

        history.append({"role": "user", "content": line})
        try:
            reply = turn_fn(client, history)
        except Exception as e:  # noqa: BLE001 — surface anything to the user
            err.print(f"[red]LLM error:[/red] {type(e).__name__}: {e}")
            # Drop the user message we appended so retry doesn't double it.
            history.pop()
            continue

        out.print()
        out.print(Markdown(reply or "[no response]"))
        out.print()


# =============================================================================
# ENTRY POINT
# =============================================================================


def main() -> None:
    """`imessage-ai` shell command — defined in pyproject.toml [project.scripts]."""
    # We deliberately DON'T use Typer for the AI CLI's top-level — there are
    # no subcommands, just "launch the REPL". A bare function is simpler.
    # We still use typer.prompt() / typer.confirm() / typer.Exit() because
    # they're nice utilities that work fine standalone.
    if not CHAT_DB.exists():
        err.print(f"[red]chat.db not found at {CHAT_DB}[/red]")
        err.print("Run [cyan]uv run imessage-cli setup[/cyan] first.")
        sys.exit(1)
    cfg = _load_or_setup_config()
    _repl(cfg)
