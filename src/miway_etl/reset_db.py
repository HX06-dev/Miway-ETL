import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RESET_SQL = """
DROP TABLE IF EXISTS trips;
DROP TABLE IF EXISTS stops;
DROP TABLE IF EXISTS routes;
"""

def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    with psycopg.connect(database_url) as connection:
        connection.execute(RESET_SQL)

    print("Reset database tables: trips, stops, routes")

if __name__ == "__main__":
    main()