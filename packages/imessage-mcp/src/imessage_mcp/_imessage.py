"""macOS iMessage database access. Read-only, internal to the package.

The chat.db file is a SQLite database macOS uses for Messages.app. We open
it read-only (uri=mode=ro) to be safe against accidental writes. Timestamps
in the DB are "Apple epoch" — nanoseconds since 2001-01-01 UTC.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

CHAT_DB = Path.home() / "Library" / "Messages" / "chat.db"
APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)


def open_db() -> sqlite3.Connection:
    """Open chat.db read-only. Caller handles the FileNotFoundError / permission error."""
    if not CHAT_DB.exists():
        raise FileNotFoundError(f"chat.db not found at {CHAT_DB}")
    return sqlite3.connect(f"file:{CHAT_DB}?mode=ro", uri=True)


def apple_ts_to_dt(ts: int) -> datetime:
    """Apple's nanosecond timestamp → datetime."""
    return APPLE_EPOCH + timedelta(seconds=ts / 1_000_000_000)
