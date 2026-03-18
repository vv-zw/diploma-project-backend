from pathlib import Path
from typing import Callable, Iterable, List

from config import Config
from .connection import get_db_connection, is_database_enabled


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def get_migration_files() -> List[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def render_sql_template(sql_text: str, schema: str) -> str:
    return sql_text.replace("{{SCHEMA}}", schema)


def run_migrations(schema: str | None = None, log: Callable[[str], None] | None = None) -> List[str]:
    """Run bundled SQL migrations for the configured PostgreSQL schema."""
    if not is_database_enabled():
        raise RuntimeError("database_not_available")

    schema = (schema or Config.PGSCHEMA or "app").strip() or "app"
    log = log or (lambda message: None)
    applied: List[str] = []

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
            for migration_path in get_migration_files():
                sql_text = migration_path.read_text(encoding="utf-8").strip()
                if not sql_text:
                    continue
                cur.execute(render_sql_template(sql_text, schema))
                applied.append(migration_path.name)
                log(f"[OK] Applied migration {migration_path.name}")
        conn.commit()

    return applied


def describe_tables(schema: str | None = None) -> Iterable[tuple[str, int]]:
    """Yield table names and row counts for the configured schema."""
    if not is_database_enabled():
        raise RuntimeError("database_not_available")

    schema = (schema or Config.PGSCHEMA or "app").strip() or "app"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %(schema)s
                ORDER BY table_name
                """,
                {"schema": schema},
            )
            table_names = [row[0] for row in cur.fetchall()]
            summary = []
            for table_name in table_names:
                cur.execute(f"SELECT COUNT(*) FROM {schema}.{table_name}")
                summary.append((table_name, int(cur.fetchone()[0])))
    return summary
