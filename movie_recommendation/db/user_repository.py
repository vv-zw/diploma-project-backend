from typing import Dict, List, Optional

from config import Config
from .connection import get_db_connection, is_database_enabled


def _stringify_multi_value(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def get_user_preferences(user_id: str = "user_default", content_type: Optional[str] = None) -> Dict[str, List[dict]]:
    """Load typed user preferences from PostgreSQL."""
    result = {"movie": [], "series": []}
    if not is_database_enabled():
        return result

    where_sql = "WHERE user_id = %(user_id)s"
    params = {"user_id": user_id}
    if content_type:
        where_sql += " AND content_type = %(content_type)s"
        params["content_type"] = str(content_type).strip().lower()

    sql_with_comment = f"""
    SELECT content_id, content_type, title, genres, rating, year, director, actors, cover_url, comment
    FROM {Config.PGSCHEMA}.user_preferences
    {where_sql}
    ORDER BY created_at ASC, id ASC
    """
    sql_without_comment = f"""
    SELECT content_id, content_type, title, genres, rating, year, director, actors, cover_url
    FROM {Config.PGSCHEMA}.user_preferences
    {where_sql}
    ORDER BY created_at ASC, id ASC
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(sql_with_comment, params)
                    rows = cur.fetchall()
                    has_comment = True
                except Exception as exc:
                    if 'comment' not in str(exc).lower():
                        raise
                    cur.execute(sql_without_comment, params)
                    rows = cur.fetchall()
                    has_comment = False
    except Exception as exc:
        print(f"[WARN] Failed to load user preferences from PostgreSQL: {exc}")
        return result

    for row in rows:
        item_type = str(row[1] or "").strip().lower()
        if item_type not in result:
            continue

        title = row[2] or ""
        result[item_type].append(
            {
                "id": str(row[0]).strip(),
                "name": title,
                "title": title,
                "genres": [part.strip() for part in str(row[3] or "").split(",") if part.strip()],
                "rating": float(row[4] or 0),
                "year": row[5] or 0,
                "director": row[6] or "",
                "actors": row[7] or "",
                "cover_url": row[8] or "",
                "comment": row[9] or "" if has_comment else "",
                "content_type": item_type,
            }
        )

    return result


def replace_user_preferences(user_id: str, preferences_by_type: Dict[str, List[dict]]) -> bool:
    """Replace one user's stored preferences in PostgreSQL."""
    if not is_database_enabled():
        return False

    delete_sql = f"DELETE FROM {Config.PGSCHEMA}.user_preferences WHERE user_id = %(user_id)s"
    insert_sql_with_comment = f"""
    INSERT INTO {Config.PGSCHEMA}.user_preferences (
        user_id, content_id, content_type, title, genres, rating, year, director, actors, cover_url, comment, source
    ) VALUES (
        %(user_id)s, %(content_id)s, %(content_type)s, %(title)s, %(genres)s,
        %(rating)s, %(year)s, %(director)s, %(actors)s, %(cover_url)s, %(comment)s, %(source)s
    )
    """
    insert_sql_without_comment = f"""
    INSERT INTO {Config.PGSCHEMA}.user_preferences (
        user_id, content_id, content_type, title, genres, rating, year, director, actors, cover_url, source
    ) VALUES (
        %(user_id)s, %(content_id)s, %(content_type)s, %(title)s, %(genres)s,
        %(rating)s, %(year)s, %(director)s, %(actors)s, %(cover_url)s, %(source)s
    )
    """

    records = []
    for item_type in ("movie", "series"):
        for item in preferences_by_type.get(item_type, []) or []:
            records.append(
                {
                    "user_id": user_id,
                    "content_id": str(item.get("id", "")).strip(),
                    "content_type": item_type,
                    "title": str(item.get("title", "") or item.get("name", "")).strip(),
                    "genres": _stringify_multi_value(item.get("genres", [])),
                    "rating": item.get("rating", 0) or 0,
                    "year": item.get("year") or None,
                    "director": str(item.get("director", "")).strip(),
                    "actors": _stringify_multi_value(item.get("actors", "")),
                    "cover_url": str(item.get("cover_url", "")).strip(),
                    "comment": str(item.get("comment", "")).strip(),
                    "source": "sync_user_data",
                }
            )

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(delete_sql, {"user_id": user_id})
                if records:
                    try:
                        cur.executemany(insert_sql_with_comment, records)
                    except Exception as exc:
                        if 'comment' not in str(exc).lower():
                            raise
                        fallback_records = []
                        for record in records:
                            fallback_record = dict(record)
                            fallback_record.pop("comment", None)
                            fallback_records.append(fallback_record)
                        cur.executemany(insert_sql_without_comment, fallback_records)
            conn.commit()
        return True
    except Exception as exc:
        print(f"[WARN] Failed to replace user preferences in PostgreSQL: {exc}")
        return False


def clear_user_preferences(user_id: str = "user_default", content_type: Optional[str] = None) -> bool:
    """Remove stored preferences for one user, optionally narrowed by content type."""
    if not is_database_enabled():
        return False

    where_sql = "WHERE user_id = %(user_id)s"
    params = {"user_id": user_id}
    if content_type:
        where_sql += " AND content_type = %(content_type)s"
        params["content_type"] = str(content_type).strip().lower()

    sql = f"DELETE FROM {Config.PGSCHEMA}.user_preferences {where_sql}"

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()
        return True
    except Exception as exc:
        print(f"[WARN] Failed to clear user preferences in PostgreSQL: {exc}")
        return False
