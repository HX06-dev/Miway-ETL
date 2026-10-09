import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    schema_path = PROJECT_ROOT / "sql" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    with psycopg.connect(database_url) as connection:
        connection.execute(schema_sql)

    print(f"Initialized database using {schema_path}")

if __name__ == "__main__":
    main()