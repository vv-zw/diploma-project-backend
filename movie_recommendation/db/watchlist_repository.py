from typing import Dict, List, Optional

from config import Config
from .connection import get_db_connection, is_database_enabled


def _normalize_item_data(item_id: str, item_type: str, item_data: Optional[dict]) -> Dict:
    item_data = item_data or {}
    genres = item_data.get("genres")
    if not isinstance(genres, str):
        genres = ", ".join(item_data.get("genres", []) or item_data.get("selectedElements", []) or [])

    return {
        "content_id": str(item_id).strip(),
        "content_type": str(item_type).strip().lower(),
        "title": str(item_data.get("title") or item_data.get("name") or item_id).strip(),
        "genres": genres or "",
        "rating": item_data.get("rating", 0) or 0,
        "cover_url": item_data.get("cover_url") or item_data.get("coverUrl") or "",
        "year": item_data.get("year") or None,
        "director": item_data.get("director") or "",
    }


def get_watchlist_items(user_id: str = "user_default", content_type: Optional[str] = None) -> List[dict]:
    """Return watchlist records from PostgreSQL."""
    if not is_database_enabled():
        return []

    where_sql = "WHERE user_id = %(user_id)s"
    params = {"user_id": user_id}
    if content_type:
        where_sql += " AND content_type = %(content_type)s"
        params["content_type"] = str(content_type).strip().lower()

    sql = f"""
    SELECT content_id, content_type, title, genres, rating, cover_url, year, director, added_at
    FROM {Config.PGSCHEMA}.watchlist_items
    {where_sql}
    ORDER BY added_at DESC
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
    except Exception as exc:
        print(f"[WARN] Failed to load watchlist items from PostgreSQL: {exc}")
        return []

    return [
        {
            "id": str(row[0]).strip(),
            "type": str(row[1]).strip().lower(),
            "data": {
                "id": str(row[0]).strip(),
                "type": str(row[1]).strip().lower(),
                "title": row[2] or "",
                "name": row[2] or "",
                "genres": row[3] or "",
                "rating": float(row[4] or 0),
                "cover_url": row[5] or "",
                "coverUrl": row[5] or "",
                "year": row[6],
                "director": row[7] or "",
            },
            "added_at": row[8].strftime("%Y-%m-%d %H:%M:%S") if row[8] else "",
        }
        for row in rows
    ]


def add_watchlist_item(
    item_id: str,
    item_type: str,
    item_data: Optional[dict] = None,
    user_id: str = "user_default",
) -> Dict:
    """Insert one watchlist item into PostgreSQL if it does not already exist."""
    if not is_database_enabled():
        return {"status": "db_unavailable", "message": "database_unavailable"}

    payload = _normalize_item_data(item_id, item_type, item_data)
    check_sql = f"""
    SELECT 1
    FROM {Config.PGSCHEMA}.watchlist_items
    WHERE user_id = %(user_id)s AND content_id = %(content_id)s AND content_type = %(content_type)s
    LIMIT 1
    """
    insert_sql = f"""
    INSERT INTO {Config.PGSCHEMA}.watchlist_items (
        user_id, content_id, content_type, title, genres, rating, cover_url, year, director
    ) VALUES (
        %(user_id)s, %(content_id)s, %(content_type)s, %(title)s, %(genres)s, %(rating)s,
        %(cover_url)s, %(year)s, %(director)s
    )
    """

    params = {"user_id": user_id, **payload}

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(check_sql, params)
                if cur.fetchone():
                    return {"status": "exists", "message": "已在想看清单中"}
                cur.execute(insert_sql, params)
            conn.commit()
        return {"status": "success", "message": "已添加到想看清单"}
    except Exception as exc:
        print(f"[WARN] Failed to add watchlist item into PostgreSQL: {exc}")
        return {"status": "db_error", "message": "database_error"}


def remove_watchlist_item(item_id: str, item_type: str, user_id: str = "user_default") -> Dict:
    """Remove one watchlist item from PostgreSQL."""
    if not is_database_enabled():
        return {"status": "db_unavailable", "message": "database_unavailable"}

    sql = f"""
    DELETE FROM {Config.PGSCHEMA}.watchlist_items
    WHERE user_id = %(user_id)s AND content_id = %(content_id)s AND content_type = %(content_type)s
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    {
                        "user_id": user_id,
                        "content_id": str(item_id).strip(),
                        "content_type": str(item_type).strip().lower(),
                    },
                )
            conn.commit()
        return {"status": "success", "message": "已从想看清单移除"}
    except Exception as exc:
        print(f"[WARN] Failed to remove watchlist item from PostgreSQL: {exc}")
        return {"status": "db_error", "message": "database_error"}
