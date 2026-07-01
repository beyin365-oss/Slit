"""
Audit log database persistence (per-user, searchable).
"""

from __future__ import annotations

from db.connection import get_db


def save_audit_entry(user_id: int, entry: dict) -> None:
    """Persist an audit entry dict to the database."""
    conn = get_db()
    conn.execute(
        """INSERT INTO audit_logs
           (user_id, audit_id, timestamp, original_filename, file_format,
            rows_processed, columns_total, columns_redacted, values_redacted,
            file_sha256, redaction_summary, user_note, ndpr_note)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            user_id,
            entry.get("audit_id", ""),
            entry.get("timestamp", ""),
            entry.get("original_filename", ""),
            entry.get("file_format", ""),
            entry.get("rows_processed", 0),
            entry.get("columns_total", 0),
            entry.get("columns_redacted", 0),
            entry.get("values_redacted_total", 0),
            entry.get("file_sha256", ""),
            entry.get("redaction_summary", ""),
            entry.get("user_note", ""),
            entry.get("ndpr_compliance", ""),
        ),
    )
    conn.commit()


def get_user_audit_log(user_id: int, limit: int = 200) -> list[dict]:
    """Retrieve audit entries for a specific user, newest first."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM audit_logs WHERE user_id=? ORDER BY timestamp DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_audit_log(limit: int = 500) -> list[dict]:
    """Admin: retrieve all audit entries across all users."""
    conn = get_db()
    rows = conn.execute(
        "SELECT al.*, u.email, u.full_name "
        "FROM audit_logs al JOIN users u ON u.id=al.user_id "
        "ORDER BY al.timestamp DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def count_audit_entries() -> int:
    conn = get_db()
    # Use named alias so RealDictCursor (PG) and sqlite3.Row both support key access
    return conn.execute("SELECT COUNT(*) AS cnt FROM audit_logs").fetchone()["cnt"]
