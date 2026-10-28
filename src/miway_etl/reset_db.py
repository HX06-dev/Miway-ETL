from pathlib import Path

from dotenv import load_dotenv

from miway_etl.db import get_connection

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RESET_SQL = """
DROP TABLE IF EXISTS alerts;
DROP TABLE IF EXISTS trip_updates;
DROP TABLE IF EXISTS vehicle_positions;
DROP TABLE IF EXISTS stop_times;
DROP TABLE IF EXISTS trips;
DROP TABLE IF EXISTS stops;
DROP TABLE IF EXISTS routes;
"""

def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    with get_connection() as connection:
        connection.execute(RESET_SQL)

    print(
        "Reset database tables: alerts, trip_updates, vehicle_positions, "
        "stop_times, trips, stops, routes"
    )

if __name__ == "__main__":
    main()