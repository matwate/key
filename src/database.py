import sqlite3
from datetime import datetime, timezone

DB_PATH = "key.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = _get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def get_user_by_email(email: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT id, email, hashed_password, name, created_at FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def create_user(email: str, hashed_password: str, name: str) -> dict:
    conn = _get_conn()
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO users (email, hashed_password, name, created_at) VALUES (?, ?, ?, ?)",
        (email, hashed_password, name, now),
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"id": user_id, "email": email, "name": name, "created_at": now}
