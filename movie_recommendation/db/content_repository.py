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
