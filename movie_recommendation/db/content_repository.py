import pandas as pd

from config import Config
from .connection import get_db_connection, is_database_enabled


CONTENT_COLUMNS = [
    "source_item_id",
    "content_type",
    "title",
    "original_title",
    "genres",
    "rating",
    "year",
    "director",
    "actors",
    "cover_url",
    "plot",
    "popularity",
    "region",
    "language",
    "duration",
    "episodes",
    "status",
]


def load_content_items_df(content_type: str) -> pd.DataFrame:
    """Load movie or series content rows from PostgreSQL."""
    if not is_database_enabled():
        return pd.DataFrame()

    query = f"""
    SELECT
        source_item_id AS id,
        content_type,
        title,
        original_title,
        genres,
        rating,
        year,
        director,
        actors,
        cover_url,
        plot,
        popularity,
        region,
        language,
        duration,
        episodes,
        status
    FROM {Config.PGSCHEMA}.content_items
    WHERE content_type = %(content_type)s
    ORDER BY id
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"content_type": content_type})
                rows = cur.fetchall()
                columns = [desc.name for desc in cur.description]
    except Exception as exc:
        print(f"[WARN] PostgreSQL content load failed for {content_type}: {exc}")
        return pd.DataFrame()

    if not rows:
        return pd.DataFrame(columns=["id", *CONTENT_COLUMNS])

    return pd.DataFrame(rows, columns=columns)


def _normalize_content_type(content_type: str | None) -> str:
    normalized = str(content_type or "").strip().lower()
    return normalized if normalized in ("movie", "series") else ""


def _build_content_item_payload(row, include_match_fields: bool = False) -> dict:
    item = {
        "id": str(row[0] or ""),
        "content_type": str(row[1] or ""),
        "title": row[2] or "",
        "name": row[2] or "",
        "original_title": row[3] or "",
        "genres": row[4] or "",
        "rating": float(row[5] or 0) if row[5] is not None else 0,
        "year": row[6] or "",
        "director": row[7] or "",
        "actors": row[8] or "",
        "cover_url": row[9] or "",
        "coverUrl": row[9] or "",
        "plot": row[10] or "",
        "popularity": float(row[11] or 0) if row[11] is not None else 0,
        "region": row[12] or "",
        "language": row[13] or "",
        "duration": row[14] or "",
        "episodes": row[15] or "",
        "status": row[16] or "",
    }
    if include_match_fields:
        item["match_score"] = float(row[17] or 0)
        item["similarity_score"] = float(row[17] or 0)
        item["match_reason"] = row[18] or ""
    return item


def search_content_items(query: str, content_type: str | None = None, limit: int = 30) -> list[dict]:
    """Search content items from PostgreSQL with lightweight ranking."""
    if not is_database_enabled():
        return []

    normalized_query = str(query or "").strip()
    if not normalized_query:
        return []

    normalized_type = _normalize_content_type(content_type)
    safe_limit = max(1, min(int(limit or 30), 100))
    lowered_query = normalized_query.lower()
    prefix_pattern = f"{normalized_query}%"
    like_pattern = f"%{normalized_query}%"

    where_clauses = [
        """
        (
            title ILIKE %(like_pattern)s
            OR COALESCE(original_title, '') ILIKE %(like_pattern)s
            OR COALESCE(director, '') ILIKE %(like_pattern)s
            OR COALESCE(actors, '') ILIKE %(like_pattern)s
            OR COALESCE(genres, '') ILIKE %(like_pattern)s
        )
        """
    ]
    params: dict[str, object] = {
        "lowered_query": lowered_query,
        "prefix_pattern": prefix_pattern,
        "like_pattern": like_pattern,
        "limit": safe_limit,
    }
    if normalized_type:
        where_clauses.append("content_type = %(content_type)s")
        params["content_type"] = normalized_type

    query_sql = f"""
    SELECT
        source_item_id,
        content_type,
        title,
        original_title,
        genres,
        rating,
        year,
        director,
        actors,
        cover_url,
        plot,
        popularity,
        region,
        language,
        duration,
        episodes,
        status,
        (
            CASE
                WHEN LOWER(title) = %(lowered_query)s THEN 1.0
                WHEN LOWER(COALESCE(original_title, '')) = %(lowered_query)s THEN 0.98
                WHEN title ILIKE %(prefix_pattern)s THEN 0.95
                WHEN COALESCE(original_title, '') ILIKE %(prefix_pattern)s THEN 0.93
                WHEN title ILIKE %(like_pattern)s THEN 0.88
                WHEN COALESCE(original_title, '') ILIKE %(like_pattern)s THEN 0.85
                WHEN COALESCE(director, '') ILIKE %(like_pattern)s THEN 0.74
                WHEN COALESCE(actors, '') ILIKE %(like_pattern)s THEN 0.70
                WHEN COALESCE(genres, '') ILIKE %(like_pattern)s THEN 0.62
                ELSE 0.0
            END
        ) AS match_score,
        (
            CASE
                WHEN LOWER(title) = %(lowered_query)s THEN 'title_exact'
                WHEN LOWER(COALESCE(original_title, '')) = %(lowered_query)s THEN 'original_title_exact'
                WHEN title ILIKE %(prefix_pattern)s THEN 'title_prefix'
                WHEN COALESCE(original_title, '') ILIKE %(prefix_pattern)s THEN 'original_title_prefix'
                WHEN title ILIKE %(like_pattern)s THEN 'title_fuzzy'
                WHEN COALESCE(original_title, '') ILIKE %(like_pattern)s THEN 'original_title_fuzzy'
                WHEN COALESCE(director, '') ILIKE %(like_pattern)s THEN 'director_match'
                WHEN COALESCE(actors, '') ILIKE %(like_pattern)s THEN 'actor_match'
                WHEN COALESCE(genres, '') ILIKE %(like_pattern)s THEN 'genre_match'
                ELSE 'unknown'
            END
        ) AS match_reason
    FROM {Config.PGSCHEMA}.content_items
    WHERE {' AND '.join(where_clauses)}
    ORDER BY match_score DESC, rating DESC, popularity DESC, year DESC NULLS LAST
    LIMIT %(limit)s
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query_sql, params)
                rows = cur.fetchall()
    except Exception as exc:
        print(f"[WARN] PostgreSQL search failed for '{normalized_query}': {exc}")
        return []

    return [_build_content_item_payload(row, include_match_fields=True) for row in rows]


def find_content_item_by_name(name: str, content_type: str | None = None) -> dict | None:
    results = search_content_items(name, content_type=content_type, limit=10)
    return results[0] if results else None


def find_content_items_by_names(names: list[str], content_type: str | None = None) -> list[dict]:
    results: list[dict] = []
    for raw_name in names or []:
        normalized_name = str(raw_name or "").strip()
        if not normalized_name:
            continue
        item = find_content_item_by_name(normalized_name, content_type=content_type)
        results.append({
            "name_requested": normalized_name,
            "matched_title": item.get("title", normalized_name) if item else normalized_name,
            "data": item,
            "similarity_score": float(item.get("match_score", 0)) if item else 0,
        })
    return results
