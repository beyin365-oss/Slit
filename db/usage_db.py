"""
Usage tracking: files and rows processed per user per month.
"""

from __future__ import annotations

from datetime import datetime
from db.connection import get_db, IS_POSTGRES


def _ym() -> str:
    return datetime.now().strftime("%Y-%m")


def get_usage(user_id: int, year_month: str | None = None) -> dict:
    """Return {files_processed, rows_processed} for the given month (default current)."""
    ym   = year_month or _ym()
    conn = get_db()
    row  = conn.execute(
        "SELECT files_processed, rows_processed FROM usage_logs "
        "WHERE user_id=? AND year_month=?",
        (user_id, ym),
    ).fetchone()
    if row:
        return {
            "files_processed": row["files_processed"],
            "rows_processed":  row["rows_processed"],
            "year_month":      ym,
        }
    return {"files_processed": 0, "rows_processed": 0, "year_month": ym}


def increment_usage(user_id: int, files_delta: int = 1, rows_delta: int = 0) -> None:
    """Atomically increment monthly usage counters (works for both SQLite and PG)."""
    ym  = _ym()
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_db()

    if IS_POSTGRES:
        # PostgreSQL upsert
        conn.execute(
            """INSERT INTO usage_logs (user_id, year_month, files_processed, rows_processed, last_updated)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_id, year_month) DO UPDATE SET
                   files_processed = usage_logs.files_processed + EXCLUDED.files_processed,
                   rows_processed  = usage_logs.rows_processed  + EXCLUDED.rows_processed,
                   last_updated    = EXCLUDED.last_updated""",
            (user_id, ym, files_delta, rows_delta, now),
        )
    else:
        # SQLite upsert (excluded.* lowercase)
        conn.execute(
            """INSERT INTO usage_logs (user_id, year_month, files_processed, rows_processed, last_updated)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_id, year_month) DO UPDATE SET
                   files_processed = files_processed + excluded.files_processed,
                   rows_processed  = rows_processed  + excluded.rows_processed,
                   last_updated    = excluded.last_updated""",
            (user_id, ym, files_delta, rows_delta, now),
        )
    conn.commit()


def get_all_time_usage(user_id: int) -> dict:
    """Return cumulative totals across all months."""
    conn = get_db()
    row  = conn.execute(
        "SELECT SUM(files_processed) as tf, SUM(rows_processed) as tr "
        "FROM usage_logs WHERE user_id=?",
        (user_id,),
    ).fetchone()
    return {"total_files": row["tf"] or 0, "total_rows": row["tr"] or 0}


def get_platform_usage() -> list[dict]:
    """Admin: usage summary per user."""
    conn = get_db()
    # NULLS LAST is supported by both SQLite ≥ 3.30 and PostgreSQL
    rows = conn.execute(
        "SELECT u.email, u.full_name, COALESCE(s.tier,'free') as tier, "
        "       SUM(ul.files_processed) as total_files, SUM(ul.rows_processed) as total_rows "
        "FROM users u "
        "LEFT JOIN subscriptions s ON s.user_id=u.id AND s.status='active' "
        "LEFT JOIN usage_logs ul ON ul.user_id=u.id "
        "GROUP BY u.id, u.email, u.full_name, s.tier "
        "ORDER BY total_files DESC NULLS LAST"
    ).fetchall()
    return [dict(r) for r in rows]
