"""
Redaction preset management (per-user, stored in SQLite as JSON blobs).
"""

import json
from db import get_db


def save_preset(user_id: int, name: str, config: dict) -> tuple[bool, str]:
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO presets (user_id, name, config_json)
               VALUES (?,?,?)
               ON CONFLICT(user_id, name) DO UPDATE SET config_json=excluded.config_json""",
            (user_id, name.strip(), json.dumps(config)),
        )
        conn.commit()
        return True, f"Preset '{name}' saved."
    except Exception as e:
        return False, str(e)


def load_preset(user_id: int, name: str) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT config_json FROM presets WHERE user_id=? AND name=?", (user_id, name)
    ).fetchone()
    if row:
        return json.loads(row["config_json"])
    return None


def list_presets(user_id: int) -> list[str]:
    conn = get_db()
    rows = conn.execute(
        "SELECT name FROM presets WHERE user_id=? ORDER BY name", (user_id,)
    ).fetchall()
    return [r["name"] for r in rows]


def delete_preset(user_id: int, name: str) -> bool:
    conn = get_db()
    conn.execute("DELETE FROM presets WHERE user_id=? AND name=?", (user_id, name))
    conn.commit()
    return True


def count_presets(user_id: int) -> int:
    conn = get_db()
    return conn.execute(
        "SELECT COUNT(*) FROM presets WHERE user_id=?", (user_id,)
    ).fetchone()[0]
