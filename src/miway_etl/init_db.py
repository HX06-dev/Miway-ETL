from pathlib import Path

from dotenv import load_dotenv

from miway_etl.db import get_connection

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    schema_path = PROJECT_ROOT / "sql" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    with get_connection() as connection:
        connection.execute(schema_sql)

    print(f"Initialized database using {schema_path}")

if __name__ == "__main__":
    main()