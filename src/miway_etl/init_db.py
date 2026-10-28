from pathlib import Path

from dotenv import load_dotenv

from miway_etl.db import get_connection

PROJECT_ROOT = Path(__file__).resolve().parents[2]


EXPECTED_COLUMNS = {
    ("stop_times", "arrival_time"): "integer",
    ("stop_times", "departure_time"): "integer",
    ("vehicle_positions", "direction_id"): "smallint",
    ("alerts", "observed_at"): "bigint",
}


def validate_schema(connection) -> None:
    for (table_name, column_name), expected_type in EXPECTED_COLUMNS.items():
        row = connection.execute(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = %s
            """,
            (table_name, column_name),
        ).fetchone()
        if row is None or row[0] != expected_type:
            actual = "missing" if row is None else row[0]
            raise RuntimeError(
                f"Schema mismatch for {table_name}.{column_name}: "
                f"expected {expected_type}, found {actual}. "
                "Run reset_db --yes before initializing again."
            )


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    schema_path = PROJECT_ROOT / "sql" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    with get_connection() as connection:
        connection.execute(schema_sql)
        validate_schema(connection)

    print(f"Initialized database using {schema_path}")

if __name__ == "__main__":
    main()