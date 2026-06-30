"""
Subscription management: tier changes, Paystack verification, revenue reporting.
"""

from datetime import datetime, timedelta
from db import get_db


def get_subscription(user_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM subscriptions WHERE user_id=? AND status='active' "
        "ORDER BY created_at DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def set_subscription(user_id: int, tier: str, paystack_ref: str = "",
                     amount_ngn: int = 0) -> None:
    """Deactivate current subscription and create a new active one."""
    conn = get_db()
    now = datetime.now().isoformat(timespec="seconds")
    end = (datetime.now() + timedelta(days=30)).isoformat(timespec="seconds")

    conn.execute(
        "UPDATE subscriptions SET status='cancelled', cancelled_at=? "
        "WHERE user_id=? AND status='active'",
        (now, user_id),
    )
    conn.execute(
        "INSERT INTO subscriptions "
        "(user_id, tier, status, paystack_ref, amount_ngn, start_date, end_date) "
        "VALUES (?,?,?,?,?,?,?)",
        (user_id, tier, "active", paystack_ref, amount_ngn, now, end),
    )
    conn.commit()


def cancel_subscription(user_id: int) -> None:
    conn = get_db()
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE subscriptions SET status='cancelled', cancelled_at=? "
        "WHERE user_id=? AND status='active'",
        (now, user_id),
    )
    conn.execute(
        "INSERT INTO subscriptions (user_id, tier, status) VALUES (?,?,?)",
        (user_id, "free", "active"),
    )
    conn.commit()


def revenue_summary() -> dict:
    """Admin: total revenue by tier."""
    conn = get_db()
    rows = conn.execute(
        "SELECT tier, COUNT(*) as count, SUM(amount_ngn) as total_ngn "
        "FROM subscriptions WHERE status='active' GROUP BY tier"
    ).fetchall()
    return {r["tier"]: {"count": r["count"], "total_ngn": r["total_ngn"] or 0}
            for r in rows}


def subscription_history(user_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM subscriptions WHERE user_id=? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]
