import argparse
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

from miway_etl.db import get_connection

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RESET_SQL = """
DROP TABLE IF EXISTS static_feed_loads;
DROP TABLE IF EXISTS calendar_dates;
DROP TABLE IF EXISTS alerts;
DROP TABLE IF EXISTS alert_history;
DROP TABLE IF EXISTS trip_update_history;
DROP TABLE IF EXISTS vehicle_position_history;
DROP TABLE IF EXISTS trip_updates;
DROP TABLE IF EXISTS vehicle_positions;
DROP TABLE IF EXISTS stop_times;
DROP TABLE IF EXISTS trips;
DROP TABLE IF EXISTS stops;
DROP TABLE IF EXISTS routes;
"""

def main(argv: list[str] | None = None) -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    parser = argparse.ArgumentParser(description="Delete all MiWay ETL tables.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="confirm deletion; required even for local databases",
    )
    args = parser.parse_args(argv)
    if not args.yes:
        raise SystemExit("Refusing to reset without --yes")

    database_url = os.environ.get("DATABASE_URL", "")
    hostname = urlparse(database_url).hostname
    if hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Refusing to reset a non-local database")

    with get_connection() as connection:
        connection.execute(RESET_SQL)

    print(
        "Reset database tables: alerts, alert_history, trip_updates, "
        "trip_update_history, vehicle_positions, vehicle_position_history, "
        "calendar_dates, stop_times, trips, stops, routes"
    )

if __name__ == "__main__":
    main()