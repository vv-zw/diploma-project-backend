import argparse
import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = CURRENT_DIR.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from config import Config
from db.bootstrap import describe_tables, run_migrations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize PostgreSQL tables for the project.")
    parser.add_argument(
        "--schema",
        default=Config.PGSCHEMA,
        help="Target PostgreSQL schema. Defaults to env PGSCHEMA or app.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress migration progress logging.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logger = (lambda message: None) if args.quiet else print
    applied = run_migrations(schema=args.schema, log=logger)
    print(f"[INFO] Applied {len(applied)} migration files to schema '{args.schema}'.")
    for table_name, row_count in describe_tables(schema=args.schema):
        print(f"  - {table_name}: {row_count}")


if __name__ == "__main__":
    main()
