"""
Unified database connection layer.

- No DATABASE_URL  →  SQLite (WAL mode, perfect for development and small deployments)
- DATABASE_URL set →  PostgreSQL via psycopg2 (Render, Railway, Supabase, Neon, etc.)

Import get_db() from here instead of from db/__init__.py:

    from db.connection import get_db, IS_POSTGRES
"""

from __future__ import annotations

import os
import threading

# ── Backend detection ─────────────────────────────────────────────────────────

DATABASE_URL: str | None = os.getenv("DATABASE_URL")
IS_POSTGRES: bool        = bool(DATABASE_URL)

# ── PostgreSQL backend ────────────────────────────────────────────────────────

if IS_POSTGRES:
    try:
        import psycopg2                                    # type: ignore[import]
        import psycopg2.extras                             # type: ignore[import]
        from psycopg2.pool import ThreadedConnectionPool   # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "DATABASE_URL is set but psycopg2 is not installed. "
            "Add 'psycopg2-binary' to requirements.txt and reinstall."
        ) from exc

    _pool: "ThreadedConnectionPool | None" = None
    _pool_lock = threading.Lock()

    def _get_pool() -> "ThreadedConnectionPool":
        global _pool
        if _pool is None:
            with _pool_lock:
                if _pool is None:
                    _pool = ThreadedConnectionPool(2, 20, DATABASE_URL)
        return _pool

    class _PgCursor:
        """Wraps a psycopg2 cursor so callers can use the sqlite3-style API."""

        def __init__(self, raw: "psycopg2.extensions.cursor") -> None:
            self._c = raw

        def fetchone(self):
            return self._c.fetchone()   # RealDictRow — supports row["col"]

        def fetchall(self):
            return self._c.fetchall()  # list[RealDictRow]

        def __getitem__(self, key):
            row = self._c.fetchone()
            return row[key] if row else None

    class _PgConn:
        """Makes a psycopg2 connection look like our sqlite3 interface."""

        def __init__(self) -> None:
            self._raw = _get_pool().getconn()
            self._raw.autocommit = False

        # ── core API ──────────────────────────────────────────────────────────

        def execute(self, sql: str, params=()):
            sql = _pg_adapt(sql)
            cur = self._raw.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql, params or None)
            return _PgCursor(cur)

        def executemany(self, sql: str, params_seq):
            sql = _pg_adapt(sql)
            cur = self._raw.cursor()
            cur.executemany(sql, params_seq)

        def executescript(self, sql: str) -> None:
            """Execute a multi-statement SQL string (DDL only, used by init_db)."""
            cur = self._raw.cursor()
            for stmt in sql.split(";"):
                stmt = stmt.strip()
                if stmt and not stmt.startswith("--"):
                    cur.execute(stmt)

        def commit(self) -> None:
            self._raw.commit()

        def rollback(self) -> None:
            self._raw.rollback()

        def release(self) -> None:
            """Return connection to pool. Called on Streamlit session end."""
            _get_pool().putconn(self._raw)

    _local_pg = threading.local()

    def get_db() -> "_PgConn":                            # type: ignore[misc]
        conn = getattr(_local_pg, "conn", None)
        if conn is None:
            conn = _PgConn()
            _local_pg.conn = conn
        return conn

# ── SQLite backend (default) ──────────────────────────────────────────────────

else:
    import sqlite3
    from pathlib import Path

    _SQLITE_PATH = os.getenv("SQLITE_PATH") or os.getenv("DB_PATH", "ndpr_redactor.db")

    _local_sq = threading.local()

    def get_db() -> "sqlite3.Connection":                  # type: ignore[misc]
        conn = getattr(_local_sq, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                _SQLITE_PATH, check_same_thread=False, timeout=10
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            _local_sq.conn = conn
        return conn


# ── SQL dialect adapter ───────────────────────────────────────────────────────

def _pg_adapt(sql: str) -> str:
    """Translate SQLite-style SQL to PostgreSQL dialect on the fly."""
    # Positional placeholder
    sql = sql.replace("?", "%s")
    # Case-insensitive collation (emails already stored lowercase)
    sql = sql.replace(" COLLATE NOCASE", "")
    # INSERT OR IGNORE → INSERT … ON CONFLICT DO NOTHING
    if "INSERT OR IGNORE INTO" in sql:
        sql = sql.replace("INSERT OR IGNORE INTO", "INSERT INTO")
        # Append ON CONFLICT clause at the end
        sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return sql
