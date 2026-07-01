"""
Database initialisation and schema management.

Supports SQLite (default) and PostgreSQL (when DATABASE_URL env var is set).
Call init_db() once at startup to create all tables and seed the admin account.
"""

from __future__ import annotations

from db.connection import get_db, IS_POSTGRES

__all__ = ["get_db", "init_db", "IS_POSTGRES"]


def init_db() -> None:
    """Create all tables (idempotent) and seed the default admin account."""
    conn = get_db()
    schema = _SCHEMA_PG if IS_POSTGRES else _SCHEMA_SQLITE
    conn.executescript(schema)
    conn.commit()
    _seed_admin(conn)


# ── SQLite schema ─────────────────────────────────────────────────────────────

_SCHEMA_SQLITE = """
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

# ── PostgreSQL schema ─────────────────────────────────────────────────────────
# Uses SERIAL, NOW(), and TEXT for ISO-8601 timestamps (same as SQLite version).

_SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         TEXT    UNIQUE NOT NULL,
    password_hash TEXT    NOT NULL,
    full_name     TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'user',
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL DEFAULT (TO_CHAR(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS')),
    last_login    TEXT
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id             SERIAL PRIMARY KEY,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tier           TEXT    NOT NULL DEFAULT 'free',
    status         TEXT    NOT NULL DEFAULT 'active',
    paystack_ref   TEXT,
    amount_ngn     INTEGER DEFAULT 0,
    start_date     TEXT    NOT NULL DEFAULT (TO_CHAR(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS')),
    end_date       TEXT,
    cancelled_at   TEXT,
    created_at     TEXT    NOT NULL DEFAULT (TO_CHAR(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS'))
);

CREATE TABLE IF NOT EXISTS usage_logs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    year_month      TEXT    NOT NULL,
    files_processed INTEGER NOT NULL DEFAULT 0,
    rows_processed  INTEGER NOT NULL DEFAULT 0,
    last_updated    TEXT    NOT NULL DEFAULT (TO_CHAR(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS')),
    UNIQUE(user_id, year_month)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id                SERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    audit_id          TEXT    NOT NULL,
    timestamp         TEXT    NOT NULL DEFAULT (TO_CHAR(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS')),
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
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,
    config_json TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (TO_CHAR(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS')),
    UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS password_resets (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token      TEXT    NOT NULL UNIQUE,
    expires_at TEXT    NOT NULL,
    used       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL DEFAULT (TO_CHAR(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS'))
);
"""


# ── Admin seed ────────────────────────────────────────────────────────────────

def _seed_admin(conn) -> None:
    """Create the default admin account if no admin exists."""
    from db.auth_db import hash_password

    row = conn.execute("SELECT id FROM users WHERE role='admin' LIMIT 1").fetchone()
    if row:
        return

    ph  = hash_password("NDPR_Admin_2024!")
    now = __import__("datetime").datetime.now().isoformat(timespec="seconds")

    if IS_POSTGRES:
        # Use RETURNING id to get the new row's id without last_insert_rowid()
        result = conn.execute(
            "INSERT INTO users (email, password_hash, full_name, role, created_at) "
            "VALUES (?,?,?,?,?) ON CONFLICT (email) DO NOTHING RETURNING id",
            ("admin@ndpr.local", ph, "System Admin", "admin", now),
        ).fetchone()
        if result is None:
            # Row already existed (race); fetch its id
            result = conn.execute(
                "SELECT id FROM users WHERE email=?", ("admin@ndpr.local",)
            ).fetchone()
        uid = result["id"]
        conn.execute(
            "INSERT INTO subscriptions (user_id, tier, status, start_date, created_at) "
            "VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING",
            (uid, "elite", "active", now, now),
        )
    else:
        conn.execute(
            "INSERT OR IGNORE INTO users "
            "(email, password_hash, full_name, role, created_at) VALUES (?,?,?,?,?)",
            ("admin@ndpr.local", ph, "System Admin", "admin", now),
        )
        uid = conn.execute(
            "SELECT id FROM users WHERE email='admin@ndpr.local'"
        ).fetchone()["id"]
        conn.execute(
            "INSERT OR IGNORE INTO subscriptions (user_id, tier, status) VALUES (?,?,?)",
            (uid, "elite", "active"),
        )

    conn.commit()
