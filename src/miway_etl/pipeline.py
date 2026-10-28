import os
from pathlib import Path

from dotenv import load_dotenv

from miway_etl.db import get_connection
from miway_etl.extract import (
    download_gtfs_files,
    download_gtfs_realtime_feed,
    read_alerts,
    read_routes,
    read_stop_times,
    read_stops,
    read_trip_updates,
    read_trips,
    read_vehicle_positions,
)
from miway_etl.load import (
    load_alerts,
    load_routes,
    load_stop_times,
    load_stops,
    load_trip_updates,
    load_trips,
    load_vehicle_positions,
)
from miway_etl.transform import clean_route, clean_stop, clean_stop_time, clean_trip

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROUTES_PATH = PROJECT_ROOT / "data" / "raw" / "routes.txt"
DEFAULT_STOPS_PATH = PROJECT_ROOT / "data" / "raw" / "stops.txt"
DEFAULT_TRIPS_PATH = PROJECT_ROOT / "data" / "raw" / "trips.txt"
DEFAULT_STOP_TIMES_PATH = PROJECT_ROOT / "data" / "raw" / "stop_times.txt"
STOP_TIMES_BATCH_SIZE = 10_000

def run_pipeline(
    routes_path: str | Path = DEFAULT_ROUTES_PATH,
    stops_path: str | Path = DEFAULT_STOPS_PATH,
    trips_path: str | Path = DEFAULT_TRIPS_PATH,
    stop_times_path: str | Path = DEFAULT_STOP_TIMES_PATH,
    include_realtime: bool = False,
) -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    using_default_paths = (
        routes_path == DEFAULT_ROUTES_PATH
        and stops_path == DEFAULT_STOPS_PATH
        and trips_path == DEFAULT_TRIPS_PATH
        and stop_times_path == DEFAULT_STOP_TIMES_PATH
    )
    if using_default_paths:
        release_path = download_gtfs_files(DEFAULT_ROUTES_PATH.parent)
        routes_path = release_path / "routes.txt"
        stops_path = release_path / "stops.txt"
        trips_path = release_path / "trips.txt"
        stop_times_path = release_path / "stop_times.txt"

    routes = [clean_route(row) for row in read_routes(routes_path)]
    stops = [clean_stop(row) for row in read_stops(stops_path)]
    trips = [clean_trip(row) for row in read_trips(trips_path)]
    stop_times = (clean_stop_time(row) for row in read_stop_times(stop_times_path))

    with get_connection() as connection:
        load_routes(connection, routes)
        load_stops(connection, stops)
        load_trips(connection, trips)
        print("Loading stop_times...")
        stop_times_count = load_stop_times(
            connection,
            stop_times,
            batch_size=STOP_TIMES_BATCH_SIZE,
            on_batch=lambda count: print(f"  stop_times loaded: {count:,}"),
        )
        print(f"Loaded {stop_times_count:,} stop_times")
        if include_realtime:
            load_realtime(connection)


def load_realtime(connection) -> None:
    """Fetch and load the configured current GTFS-realtime snapshots."""
    feeds = (
        ("GTFS_RT_LOCATION_URL", read_vehicle_positions, load_vehicle_positions),
        ("GTFS_RT_ALERT_URL", read_alerts, load_alerts),
        ("GTFS_RT_TRIP_UPDATE_URL", read_trip_updates, load_trip_updates),
    )
    for environment_name, reader, loader in feeds:
        url = os.environ.get(environment_name)
        if not url:
            raise RuntimeError(f"{environment_name} is not set")
        rows = reader(download_gtfs_realtime_feed(url))
        loader(connection, rows)
        print(f"Loaded {len(rows):,} {environment_name.removeprefix('GTFS_RT_').lower()}")

def main() -> None:
    run_pipeline()

if __name__ == "__main__":
    main()