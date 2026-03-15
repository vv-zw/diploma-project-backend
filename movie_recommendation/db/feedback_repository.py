from typing import List, Optional, Set

from config import Config
from .connection import get_db_connection, is_database_enabled


def add_negative_feedback_record(
    user_id: str,
    content_id: str,
    content_type: str,
    reason: str = "",
    expire_at: Optional[str] = None,
) -> bool:
    """Insert or refresh one negative feedback record in PostgreSQL."""
    if not is_database_enabled():
        return False

    sql = f"""
    INSERT INTO {Config.PGSCHEMA}.negative_feedback (
        user_id, content_id, content_type, reason, expire_at
    ) VALUES (
        %(user_id)s, %(content_id)s, %(content_type)s, %(reason)s, %(expire_at)s
    )
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    {
                        "user_id": user_id,
                        "content_id": str(content_id).strip(),
                        "content_type": str(content_type).strip().lower(),
                        "reason": reason or None,
                        "expire_at": expire_at,
                    },
                )
            conn.commit()
        return True
    except Exception as exc:
        print(f"[WARN] Failed to insert negative feedback into PostgreSQL: {exc}")
        return False


def get_negative_feedback_ids(user_id: str = "user_default", content_type: Optional[str] = None) -> Set[str]:
    """Return disliked content ids from PostgreSQL for one user."""
    if not is_database_enabled():
        return set()

    where_sql = "WHERE user_id = %(user_id)s"
    params = {"user_id": user_id}

    if content_type:
        where_sql += " AND content_type = %(content_type)s"
        params["content_type"] = str(content_type).strip().lower()

    sql = f"""
    SELECT content_id
    FROM {Config.PGSCHEMA}.negative_feedback
    {where_sql}
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        return {str(row[0]).strip() for row in rows if row and str(row[0]).strip()}
    except Exception as exc:
        print(f"[WARN] Failed to load negative feedback ids from PostgreSQL: {exc}")
        return set()


def get_negative_feedback_records(user_id: str = "user_default", content_type: Optional[str] = None) -> List[dict]:
    """Return negative feedback rows from PostgreSQL."""
    if not is_database_enabled():
        return []

    where_sql = "WHERE user_id = %(user_id)s"
    params = {"user_id": user_id}
    if content_type:
        where_sql += " AND content_type = %(content_type)s"
        params["content_type"] = str(content_type).strip().lower()

    sql = f"""
    SELECT content_id, content_type, reason, created_at
    FROM {Config.PGSCHEMA}.negative_feedback
    {where_sql}
    ORDER BY created_at DESC
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        return [
            {
                "id": str(row[0]).strip(),
                "item_type": str(row[1]).strip().lower(),
                "reason": row[2] or "",
                "timestamp": row[3].strftime("%Y-%m-%d %H:%M:%S") if row[3] else "",
            }
            for row in rows
            if row and str(row[0]).strip()
        ]
    except Exception as exc:
        print(f"[WARN] Failed to load negative feedback records from PostgreSQL: {exc}")
        return []
