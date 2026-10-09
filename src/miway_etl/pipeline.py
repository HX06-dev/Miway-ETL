from pathlib import Path

from dotenv import load_dotenv

from miway_etl.db import get_connection
from miway_etl.extract import (
    download_gtfs_files,
    read_routes,
    read_stop_times,
    read_stops,
    read_trips,
)
from miway_etl.load import load_routes, load_stop_times, load_stops, load_trips
from miway_etl.transform import clean_route, clean_stop, clean_stop_time, clean_trip

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROUTES_PATH = PROJECT_ROOT / "data" / "raw" / "routes.txt"
DEFAULT_STOPS_PATH = PROJECT_ROOT / "data" / "raw" / "stops.txt"
DEFAULT_TRIPS_PATH = PROJECT_ROOT / "data" / "raw" / "trips.txt"
DEFAULT_STOP_TIMES_PATH = PROJECT_ROOT / "data" / "raw" / "stop_times.txt"

def run_pipeline(
    routes_path: str | Path = DEFAULT_ROUTES_PATH,
    stops_path: str | Path = DEFAULT_STOPS_PATH,
    trips_path: str | Path = DEFAULT_TRIPS_PATH,
    stop_times_path: str | Path = DEFAULT_STOP_TIMES_PATH,
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
    stop_times = [clean_stop_time(row) for row in read_stop_times(stop_times_path)]

    with get_connection() as connection:
        load_routes(connection, routes)
        load_stops(connection, stops)
        load_trips(connection, trips)
        load_stop_times(connection, stop_times)

def main() -> None:
    run_pipeline()

if __name__ == "__main__":
    main()