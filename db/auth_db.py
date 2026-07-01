"""
Authentication database operations.
Password hashing via PBKDF2-HMAC-SHA256 (no external deps required).
"""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta

from db.connection import get_db, IS_POSTGRES
from config import PBKDF2_ITERATIONS


# ── Password utilities ────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Return 'salt_hex:key_hex' using PBKDF2-HMAC-SHA256."""
    salt = os.urandom(32)
    key  = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return salt.hex() + ":" + key.hex()


def verify_password(password: str, stored: str) -> bool:
    """Verify a plaintext password against a stored hash."""
    try:
        salt_hex, key_hex = stored.split(":")
        salt = bytes.fromhex(salt_hex)
        key  = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
        return secrets.compare_digest(key.hex(), key_hex)
    except Exception:
        return False


# ── User CRUD ─────────────────────────────────────────────────────────────────

def register_user(email: str, full_name: str, password: str) -> tuple[bool, str]:
    """Create a new user with a Free subscription. Returns (success, message)."""
    conn = get_db()

    # Check for existing account (case-insensitive; emails stored lowercase)
    existing = conn.execute(
        "SELECT id FROM users WHERE LOWER(email)=LOWER(?)", (email.strip(),)
    ).fetchone()
    if existing:
        return False, "An account with this email already exists."

    ph  = hash_password(password)
    now = datetime.now().isoformat(timespec="seconds")

    try:
        if IS_POSTGRES:
            # PostgreSQL: use RETURNING id to retrieve the new row id
            row = conn.execute(
                "INSERT INTO users (email, password_hash, full_name, created_at) "
                "VALUES (?,?,?,?) RETURNING id",
                (email.strip().lower(), ph, full_name.strip(), now),
            ).fetchone()
            uid = row["id"]
        else:
            conn.execute(
                "INSERT INTO users (email, password_hash, full_name, created_at) "
                "VALUES (?,?,?,?)",
                (email.strip().lower(), ph, full_name.strip(), now),
            )
            uid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute(
            "INSERT INTO subscriptions (user_id, tier, status) VALUES (?,?,?)",
            (uid, "free", "active"),
        )
        conn.commit()
        return True, "Account created successfully."
    except Exception as e:
        conn.rollback()
        return False, f"Registration failed: {e}"


def login_user(email: str, password: str) -> tuple[dict | None, str]:
    """Verify credentials. Returns (user_dict, message)."""
    conn = get_db()
    row = conn.execute(
        "SELECT u.*, s.tier, s.status as sub_status "
        "FROM users u "
        "LEFT JOIN subscriptions s ON s.user_id=u.id AND s.status='active' "
        "WHERE LOWER(u.email)=LOWER(?)",
        (email.strip(),),
    ).fetchone()

    if not row:
        return None, "No account found with this email."
    if not row["is_active"]:
        return None, "Your account has been deactivated. Contact support."
    if not verify_password(password, row["password_hash"]):
        return None, "Incorrect password."

    conn.execute(
        "UPDATE users SET last_login=? WHERE id=?",
        (datetime.now().isoformat(timespec="seconds"), row["id"]),
    )
    conn.commit()

    return {
        "id":        row["id"],
        "email":     row["email"],
        "full_name": row["full_name"],
        "role":      row["role"],
        "tier":      row["tier"] or "free",
    }, "Login successful."


def get_user_by_id(user_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT u.*, s.tier, s.status as sub_status "
        "FROM users u "
        "LEFT JOIN subscriptions s ON s.user_id=u.id AND s.status='active' "
        "WHERE u.id=?",
        (user_id,),
    ).fetchone()
    if not row:
        return None
    return dict(row)


def update_password(user_id: int, new_password: str) -> bool:
    conn = get_db()
    ph = hash_password(new_password)
    conn.execute("UPDATE users SET password_hash=? WHERE id=?", (ph, user_id))
    conn.commit()
    return True


def update_profile(user_id: int, full_name: str) -> bool:
    conn = get_db()
    conn.execute("UPDATE users SET full_name=? WHERE id=?", (full_name.strip(), user_id))
    conn.commit()
    return True


def list_all_users() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT u.id, u.email, u.full_name, u.role, u.is_active, u.created_at, u.last_login, "
        "       COALESCE(s.tier,'free') as tier, s.status as sub_status "
        "FROM users u "
        "LEFT JOIN subscriptions s ON s.user_id=u.id AND s.status='active' "
        "ORDER BY u.created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def set_user_active(user_id: int, active: bool) -> None:
    conn = get_db()
    conn.execute("UPDATE users SET is_active=? WHERE id=?", (int(active), user_id))
    conn.commit()


def set_user_tier(user_id: int, tier: str) -> None:
    """Admin: change user tier (cancel current subscription and set new one)."""
    conn = get_db()
    conn.execute(
        "UPDATE subscriptions SET status='cancelled', cancelled_at=? WHERE user_id=? AND status='active'",
        (datetime.now().isoformat(timespec="seconds"), user_id),
    )
    conn.execute(
        "INSERT INTO subscriptions (user_id, tier, status) VALUES (?,?,?)",
        (user_id, tier, "active"),
    )
    conn.commit()
