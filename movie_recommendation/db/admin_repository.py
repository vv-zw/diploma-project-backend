from typing import Optional

from config import Config
from .connection import get_db_connection, is_database_enabled


def admin_exists() -> bool:
    """Return whether at least one admin account exists."""
    if not is_database_enabled():
        return False

    sql = f"SELECT 1 FROM {Config.PGSCHEMA}.admin_users LIMIT 1"
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                return cur.fetchone() is not None
    except Exception as exc:
        print(f"[WARN] Failed to check admin existence: {exc}")
        return False


def get_admin_by_username(username: str) -> Optional[dict]:
    """Return one admin row by username."""
    if not is_database_enabled():
        return None

    normalized_username = str(username or "").strip()
    if not normalized_username:
        return None

    sql = f"""
    SELECT id, username, password_hash, display_name, status, created_at, updated_at, last_login_at
    FROM {Config.PGSCHEMA}.admin_users
    WHERE username = %(username)s
    LIMIT 1
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"username": normalized_username})
                row = cur.fetchone()
        if not row:
            return None
        return {
            "id": int(row[0]),
            "username": row[1] or "",
            "password_hash": row[2] or "",
            "display_name": row[3] or "",
            "status": row[4] or "",
            "created_at": row[5].strftime("%Y-%m-%d %H:%M:%S") if row[5] else "",
            "updated_at": row[6].strftime("%Y-%m-%d %H:%M:%S") if row[6] else "",
            "last_login_at": row[7].strftime("%Y-%m-%d %H:%M:%S") if row[7] else "",
        }
    except Exception as exc:
        print(f"[WARN] Failed to load admin by username: {exc}")
        return None


def create_admin_user(username: str, password_hash: str, display_name: str = "") -> bool:
    """Create one admin user."""
    if not is_database_enabled():
        return False

    normalized_username = str(username or "").strip()
    normalized_hash = str(password_hash or "").strip()
    if not normalized_username or not normalized_hash:
        return False

    sql = f"""
    INSERT INTO {Config.PGSCHEMA}.admin_users (
        username, password_hash, display_name, status
    ) VALUES (
        %(username)s, %(password_hash)s, %(display_name)s, %(status)s
    )
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    {
                        "username": normalized_username,
                        "password_hash": normalized_hash,
                        "display_name": str(display_name or "").strip() or normalized_username,
                        "status": "active",
                    },
                )
            conn.commit()
        return True
    except Exception as exc:
        print(f"[WARN] Failed to create admin user: {exc}")
        return False


def update_admin_last_login(username: str) -> bool:
    """Update last login timestamp for one admin user."""
    if not is_database_enabled():
        return False

    normalized_username = str(username or "").strip()
    if not normalized_username:
        return False

    sql = f"""
    UPDATE {Config.PGSCHEMA}.admin_users
    SET last_login_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    WHERE username = %(username)s
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"username": normalized_username})
            conn.commit()
        return True
    except Exception as exc:
        print(f"[WARN] Failed to update admin last login: {exc}")
        return False
