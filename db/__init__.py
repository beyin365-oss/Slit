"""
Database connection singleton and initialisation.
All tables are created on first call to init_db().
"""

import sqlite3
import threading
from pathlib import Path
from config import DB_PATH

_local = threading.local()


def get_db() -> sqlite3.Connection:
    """Return a thread-local SQLite connection with row_factory set."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


def init_db() -> None:
    """Create all tables if they do not exist."""
    conn = get_db()
    conn.executescript(_SCHEMA)
    conn.commit()
    _seed_admin(conn)


# ── Schema ────────────────────────────────────────────────────────────────────
_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT    UNIQUE NOT NULL COLLATE NOCASE,
    password_hash TEXT    NOT NULL,
    full_name     TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'user',
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    last_login    TEXT
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tier           TEXT    NOT NULL DEFAULT 'free',
    status         TEXT    NOT NULL DEFAULT 'active',
    paystack_ref   TEXT,
    amount_ngn     INTEGER DEFAULT 0,
    start_date     TEXT    NOT NULL DEFAULT (datetime('now')),
    end_date       TEXT,
    cancelled_at   TEXT,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS usage_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    year_month      TEXT    NOT NULL,
    files_processed INTEGER NOT NULL DEFAULT 0,
    rows_processed  INTEGER NOT NULL DEFAULT 0,
    last_updated    TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, year_month)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    audit_id          TEXT    NOT NULL,
    timestamp         TEXT    NOT NULL DEFAULT (datetime('now')),
    original_filename TEXT,
    file_format       TEXT,
    rows_processed    INTEGER,
    columns_total     INTEGER,
    columns_redacted  INTEGER,
    values_redacted   INTEGER,
    file_sha256       TEXT,
    redaction_summary TEXT,
    user_note         TEXT,
    ndpr_note         TEXT
);

CREATE TABLE IF NOT EXISTS presets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,
    config_json TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS password_resets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token      TEXT    NOT NULL UNIQUE,
    expires_at TEXT    NOT NULL,
    used       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


def _seed_admin(conn: sqlite3.Connection) -> None:
    """Create a default admin account if no admin exists."""
    from db.auth_db import hash_password
    row = conn.execute("SELECT id FROM users WHERE role='admin' LIMIT 1").fetchone()
    if row:
        return
    ph = hash_password("NDPR_Admin_2024!")
    conn.execute(
        "INSERT OR IGNORE INTO users (email, password_hash, full_name, role) VALUES (?,?,?,?)",
        ("admin@ndpr.local", ph, "System Admin", "admin"),
    )
    uid = conn.execute("SELECT id FROM users WHERE email='admin@ndpr.local'").fetchone()["id"]
    conn.execute(
        "INSERT OR IGNORE INTO subscriptions (user_id, tier, status) VALUES (?,?,?)",
        (uid, "elite", "active"),
    )
    conn.commit()
