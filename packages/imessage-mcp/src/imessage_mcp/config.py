"""Config paths + local bearer token management."""

from __future__ import annotations

import secrets
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "imessage-mcp"
TOKEN_FILE = CONFIG_DIR / "token"


def load_or_create_token(rotate: bool = False) -> str:
    """Return the local bearer token, generating it on first run.

    `secrets.token_urlsafe` gives 32 bytes of entropy as URL-safe base64 —
    plenty for a personal API. chmod 600 = owner-only, ~/.ssh convention.
    """
    if TOKEN_FILE.exists() and not rotate:
        return TOKEN_FILE.read_text().strip()
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(token)
    TOKEN_FILE.chmod(0o600)
    return token
