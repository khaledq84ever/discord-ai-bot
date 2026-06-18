"""Live SQLite store: per-server settings + per-channel conversation history.

This is the "real-time database" the bot reads from. Every message a user
sends in an AI room is written here immediately and the recent rows are read
back to give the model context. Survives restarts when DB_PATH is on a volume.
"""
import sqlite3
import threading
import time
from typing import List, Dict, Optional

import config

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def init() -> None:
    global _conn
    _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    _conn.execute("PRAGMA journal_mode=WAL;")
    _conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id   INTEGER PRIMARY KEY,
            model      TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ai_channels (
            channel_id INTEGER PRIMARY KEY,
            guild_id   INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL,
            role       TEXT NOT NULL,      -- 'user' or 'assistant'
            author     TEXT,               -- display name (for context)
            content    TEXT NOT NULL,
            ts         REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_msg_channel ON messages(channel_id, id);
        CREATE TABLE IF NOT EXISTS meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS user_api_keys (
            user_id    INTEGER NOT NULL,
            provider   TEXT NOT NULL,   -- 'openai' / 'google' / 'anthropic'
            api_key    TEXT NOT NULL,
            PRIMARY KEY (user_id, provider)
        );
        """
    )
    _conn.commit()


# ---- generic key/value (bot-level flags, e.g. avatar hash) -----------------

def get_meta(key: str) -> Optional[str]:
    with _lock:
        row = _conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def set_meta(key: str, value: str) -> None:
    with _lock:
        _conn.execute(
            "INSERT INTO meta(key, value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        _conn.commit()


# ---- guild model selection -------------------------------------------------

def get_model(guild_id: int) -> str:
    with _lock:
        row = _conn.execute(
            "SELECT model FROM guild_settings WHERE guild_id=?", (guild_id,)
        ).fetchone()
    return row[0] if row else config.DEFAULT_MODEL


def set_model(guild_id: int, model: str) -> None:
    with _lock:
        _conn.execute(
            "INSERT INTO guild_settings(guild_id, model) VALUES(?,?) "
            "ON CONFLICT(guild_id) DO UPDATE SET model=excluded.model",
            (guild_id, model),
        )
        _conn.commit()


# ---- AI chat rooms ---------------------------------------------------------

def add_channel(channel_id: int, guild_id: int) -> None:
    with _lock:
        _conn.execute(
            "INSERT OR IGNORE INTO ai_channels(channel_id, guild_id) VALUES(?,?)",
            (channel_id, guild_id),
        )
        _conn.commit()


def remove_channel(channel_id: int) -> None:
    with _lock:
        _conn.execute("DELETE FROM ai_channels WHERE channel_id=?", (channel_id,))
        _conn.commit()


def is_ai_channel(channel_id: int) -> bool:
    with _lock:
        row = _conn.execute(
            "SELECT 1 FROM ai_channels WHERE channel_id=?", (channel_id,)
        ).fetchone()
    return row is not None


# ---- conversation history --------------------------------------------------

def add_message(channel_id: int, role: str, content: str, author: str = "") -> None:
    with _lock:
        _conn.execute(
            "INSERT INTO messages(channel_id, role, author, content, ts) "
            "VALUES(?,?,?,?,?)",
            (channel_id, role, author, content, time.time()),
        )
        _conn.commit()


def get_history(channel_id: int, limit: int = None) -> List[Dict[str, str]]:
    """Return the last `limit` messages oldest->newest as {role, content}."""
    limit = limit or config.HISTORY_LIMIT
    with _lock:
        rows = _conn.execute(
            "SELECT role, content FROM messages WHERE channel_id=? "
            "ORDER BY id DESC LIMIT ?",
            (channel_id, limit),
        ).fetchall()
    rows.reverse()
    return [{"role": r, "content": c} for r, c in rows]


def clear_history(channel_id: int) -> None:
    with _lock:
        _conn.execute("DELETE FROM messages WHERE channel_id=?", (channel_id,))
        _conn.commit()


# ---- per-user API keys ----------------------------------------------------

def get_user_api_key(user_id: int, provider: str) -> Optional[str]:
    with _lock:
        row = _conn.execute(
            "SELECT api_key FROM user_api_keys WHERE user_id=? AND provider=?",
            (user_id, provider),
        ).fetchone()
    return row[0] if row else None


def set_user_api_key(user_id: int, provider: str, api_key: str) -> None:
    with _lock:
        _conn.execute(
            "INSERT INTO user_api_keys(user_id, provider, api_key) VALUES(?,?,?) "
            "ON CONFLICT(user_id, provider) DO UPDATE SET api_key=excluded.api_key",
            (user_id, provider, api_key),
        )
        _conn.commit()


def remove_user_api_key(user_id: int, provider: str) -> None:
    with _lock:
        _conn.execute(
            "DELETE FROM user_api_keys WHERE user_id=? AND provider=?",
            (user_id, provider),
        )
        _conn.commit()


# ---- SteamRIP posted game tracking ---------------------------------------

def init_steamrip() -> None:
    with _lock:
        _conn.execute(
            "CREATE TABLE IF NOT EXISTS steamrip_posted ("
            "  guild_id INTEGER NOT NULL,"
            "  title    TEXT NOT NULL,"
            "  posted_at REAL NOT NULL,"
            "  PRIMARY KEY (guild_id, title)"
            ")"
        )
        _conn.commit()


def is_steamrip_posted(guild_id: int, title: str) -> bool:
    with _lock:
        row = _conn.execute(
            "SELECT 1 FROM steamrip_posted WHERE guild_id=? AND title=?",
            (guild_id, title),
        ).fetchone()
    return row is not None


def mark_steamrip_posted(guild_id: int, title: str) -> None:
    with _lock:
        _conn.execute(
            "INSERT OR IGNORE INTO steamrip_posted(guild_id, title, posted_at) "
            "VALUES(?,?,?)",
            (guild_id, title, time.time()),
        )
        _conn.commit()
