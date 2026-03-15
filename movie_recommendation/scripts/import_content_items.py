import argparse
import math
import os
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd
from dotenv import load_dotenv
import psycopg
from psycopg.types.json import Jsonb


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MOVIES_CSV = BASE_DIR / "data" / "datasets" / "douban_movies.csv"
DEFAULT_SERIES_CSV = BASE_DIR / "data" / "datasets" / "douban_series.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import movie and series CSV data into PostgreSQL app.content_items."
    )
    parser.add_argument(
        "--type",
        choices=["movie", "series", "all"],
        default="all",
        help="Which content type to import. Defaults to all.",
    )
    parser.add_argument(
        "--movies-csv",
        default=str(DEFAULT_MOVIES_CSV),
        help="Path to douban_movies.csv.",
    )
    parser.add_argument(
        "--series-csv",
        default=str(DEFAULT_SERIES_CSV),
        help="Path to douban_series.csv.",
    )
    parser.add_argument(
        "--schema",
        default=os.getenv("PGSCHEMA", "app"),
        help="Target PostgreSQL schema. Defaults to env PGSCHEMA or app.",
    )
    return parser.parse_args()


def load_environment() -> None:
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()


def build_connection_string() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        return database_url

    host = os.getenv("PGHOST", "127.0.0.1").strip()
    port = os.getenv("PGPORT", "5432").strip()
    database = os.getenv("PGDATABASE", "movie_recommendation").strip()
    user = os.getenv("PGUSER", "postgres").strip()
    password = os.getenv("PGPASSWORD", "")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def normalize_nullable_text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    return text or None


def normalize_nullable_int(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def normalize_nullable_rating(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, float) and math.isnan(value):
        return 0.0
    text = str(value).strip()
    if not text:
        return 0.0
    try:
        return round(float(text), 1)
    except (TypeError, ValueError):
        return 0.0


def normalize_record(row: pd.Series, content_type: str) -> Dict:
    source_item_id = normalize_nullable_text(row.get("id"))
    title = normalize_nullable_text(row.get("title"))
    if not source_item_id or not title:
        raise ValueError("missing_required_fields")

    return {
        "source_item_id": source_item_id,
        "content_type": content_type,
        "title": title,
        "original_title": normalize_nullable_text(row.get("original_title")),
        "genres": normalize_nullable_text(row.get("genres")),
        "rating": normalize_nullable_rating(row.get("rating")),
        "year": normalize_nullable_int(row.get("year")),
        "director": normalize_nullable_text(row.get("director")),
        "actors": normalize_nullable_text(row.get("actors")),
        "cover_url": normalize_nullable_text(row.get("cover_url")),
        "plot": normalize_nullable_text(row.get("plot")),
        "popularity": normalize_nullable_rating(row.get("popularity")),
        "region": normalize_nullable_text(row.get("region") or row.get("country")),
        "language": normalize_nullable_text(row.get("language")),
        "duration": normalize_nullable_text(row.get("duration") or row.get("runtime")),
        "episodes": normalize_nullable_text(row.get("episodes") or row.get("total_episodes")),
        "status": normalize_nullable_text(row.get("status")),
        "raw_source": Jsonb(row.to_dict()),
    }


def load_csv_records(csv_path: Path, content_type: str) -> Tuple[List[Dict], int]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    df = pd.read_csv(csv_path)
    records: List[Dict] = []
    skipped = 0

    for _, row in df.iterrows():
        try:
            records.append(normalize_record(row, content_type))
        except ValueError:
            skipped += 1

    return records, skipped


def ensure_schema_exists(conn: psycopg.Connection, schema: str) -> None:
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    conn.commit()


def ensure_content_table_exists(conn: psycopg.Connection, schema: str) -> None:
    sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.content_items (
        id BIGSERIAL PRIMARY KEY,
        source_item_id VARCHAR(64) NOT NULL,
        content_type VARCHAR(16) NOT NULL CHECK (content_type IN ('movie', 'series')),
        title VARCHAR(255) NOT NULL,
        original_title VARCHAR(255),
        genres TEXT,
        rating NUMERIC(3,1) DEFAULT 0,
        year INTEGER,
        director VARCHAR(255),
        actors TEXT,
        cover_url TEXT,
        plot TEXT,
        popularity NUMERIC(10,4) DEFAULT 0,
        region VARCHAR(100),
        language VARCHAR(100),
        duration VARCHAR(100),
        episodes VARCHAR(100),
        status VARCHAR(100),
        raw_source JSONB,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uq_content_items UNIQUE (source_item_id, content_type)
    )
    """
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def upsert_records(conn: psycopg.Connection, schema: str, records: Iterable[Dict]) -> int:
    sql = f"""
    INSERT INTO {schema}.content_items (
        source_item_id, content_type, title, original_title, genres, rating, year,
        director, actors, cover_url, plot, popularity, region, language, duration,
        episodes, status, raw_source
    ) VALUES (
        %(source_item_id)s, %(content_type)s, %(title)s, %(original_title)s, %(genres)s,
        %(rating)s, %(year)s, %(director)s, %(actors)s, %(cover_url)s, %(plot)s,
        %(popularity)s, %(region)s, %(language)s, %(duration)s, %(episodes)s,
        %(status)s, %(raw_source)s
    )
    ON CONFLICT (source_item_id, content_type)
    DO UPDATE SET
        title = EXCLUDED.title,
        original_title = EXCLUDED.original_title,
        genres = EXCLUDED.genres,
        rating = EXCLUDED.rating,
        year = EXCLUDED.year,
        director = EXCLUDED.director,
        actors = EXCLUDED.actors,
        cover_url = EXCLUDED.cover_url,
        plot = EXCLUDED.plot,
        popularity = EXCLUDED.popularity,
        region = EXCLUDED.region,
        language = EXCLUDED.language,
        duration = EXCLUDED.duration,
        episodes = EXCLUDED.episodes,
        status = EXCLUDED.status,
        raw_source = EXCLUDED.raw_source,
        updated_at = CURRENT_TIMESTAMP
    """

    records = list(records)
    if not records:
        return 0

    with conn.cursor() as cur:
        cur.executemany(sql, records)
    conn.commit()
    return len(records)


def run_import(conn: psycopg.Connection, schema: str, csv_path: Path, content_type: str) -> None:
    records, skipped = load_csv_records(csv_path, content_type)
    affected_rows = upsert_records(conn, schema, records)
    print(
        f"[OK] Imported {affected_rows} {content_type} rows from {csv_path.name}"
        f" (skipped {skipped})"
    )


def main() -> None:
    load_environment()
    args = parse_args()
    connection_string = build_connection_string()

    print(f"[INFO] Connecting to PostgreSQL using schema '{args.schema}'")
    with psycopg.connect(connection_string) as conn:
        ensure_schema_exists(conn, args.schema)
        ensure_content_table_exists(conn, args.schema)

        if args.type in ("movie", "all"):
            run_import(conn, args.schema, Path(args.movies_csv), "movie")

        if args.type in ("series", "all"):
            run_import(conn, args.schema, Path(args.series_csv), "series")

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT content_type, COUNT(*)
                FROM {args.schema}.content_items
                GROUP BY content_type
                ORDER BY content_type
                """
            )
            rows = cur.fetchall()

    print("[INFO] Current content_items counts:")
    for content_type, total in rows:
        print(f"  - {content_type}: {total}")


if __name__ == "__main__":
    main()
