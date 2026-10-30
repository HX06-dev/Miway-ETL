from pathlib import Path

from dotenv import load_dotenv

from miway_etl.db import get_connection

PROJECT_ROOT = Path(__file__).resolve().parents[2]


EXPECTED_COLUMNS = {
    ("stop_times", "arrival_time"): "integer",
    ("stop_times", "departure_time"): "integer",
    ("vehicle_positions", "direction_id"): "smallint",
    ("alerts", "observed_at"): "bigint",
    ("static_feed_loads", "loader_version"): "integer",
    ("shapes", "shape_pt_sequence"): "integer",
    ("feed_info", "feed_version"): "text",
}


def apply_migrations(connection) -> None:
    schema_path = PROJECT_ROOT / "sql" / "schema.sql"
    migration_dir = PROJECT_ROOT / "sql" / "migrations"
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    has_routes = connection.execute(
        "SELECT to_regclass('public.routes')"
    ).fetchone()[0]
    if has_routes is None:
        connection.execute(schema_path.read_text(encoding="utf-8"))

    connection.execute(
        """
        INSERT INTO schema_migrations (version)
        VALUES ('0000_baseline')
        ON CONFLICT (version) DO NOTHING
        """
    )
    applied_versions = {
        row[0]
        for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
    }
    for migration_path in sorted(migration_dir.glob("*.sql")):
        version = migration_path.stem
        if version in applied_versions:
            continue
        connection.execute(migration_path.read_text(encoding="utf-8"))
        connection.execute(
            "INSERT INTO schema_migrations (version) VALUES (%s)",
            (version,),
        )
        applied_versions.add(version)


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
                "Check pending migrations and schema_migrations; only reset disposable databases."
            )


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    with get_connection() as connection:
        apply_migrations(connection)
        validate_schema(connection)

    print(f"Initialized database using migrations in {PROJECT_ROOT / 'sql' / 'migrations'}")

if __name__ == "__main__":
    main()