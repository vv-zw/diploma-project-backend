from contextlib import contextmanager

try:
    import psycopg
except ImportError:  # pragma: no cover - optional dependency fallback
    psycopg = None

from config import Config


def is_database_enabled() -> bool:
    """Return whether PostgreSQL access is configured and available."""
    return bool(Config.DB_ENABLED and psycopg is not None)


@contextmanager
def get_db_connection():
    """Yield a PostgreSQL connection using project config."""
    if not is_database_enabled():
        raise RuntimeError("database_not_available")

    connection = psycopg.connect(Config.get_database_url())
    try:
        yield connection
    finally:
        connection.close()
