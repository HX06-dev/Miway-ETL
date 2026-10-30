import argparse
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from miway_etl.db import get_connection
from miway_etl.extract import (
    download_gtfs_files,
    download_gtfs_realtime_feed,
    read_agency,
    read_alerts,
    read_calendar,
    read_calendar_dates,
    read_feed_info,
    read_routes,
    read_shapes,
    read_stop_times,
    read_stops,
    read_trip_updates,
    read_trips,
    read_vehicle_positions,
)
from miway_etl.load import (
    load_agency,
    load_alerts,
    load_calendar,
    load_calendar_dates,
    load_feed_info,
    load_routes,
    load_shapes,
    load_stop_times,
    load_stops,
    load_trip_updates,
    load_trips,
    load_vehicle_positions,
)
from miway_etl.transform import (
    clean_agency,
    clean_calendar,
    clean_calendar_date,
    clean_feed_info,
    clean_route,
    clean_shape,
    clean_stop,
    clean_stop_time,
    clean_trip,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROUTES_PATH = PROJECT_ROOT / "data" / "raw" / "routes.txt"
DEFAULT_STOPS_PATH = PROJECT_ROOT / "data" / "raw" / "stops.txt"
DEFAULT_TRIPS_PATH = PROJECT_ROOT / "data" / "raw" / "trips.txt"
DEFAULT_STOP_TIMES_PATH = PROJECT_ROOT / "data" / "raw" / "stop_times.txt"
STOP_TIMES_BATCH_SIZE = 10_000
STATIC_LOADER_VERSION = 2
LOGGER = logging.getLogger(__name__)


def run_static_pipeline(
    routes_path: str | Path | None = None,
    stops_path: str | Path | None = None,
    trips_path: str | Path | None = None,
    stop_times_path: str | Path | None = None,
) -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    paths = (routes_path, stops_path, trips_path, stop_times_path)
    calendar_dates_path: Path | None = None
    if all(path is None for path in paths):
        release_path = download_gtfs_files(DEFAULT_ROUTES_PATH.parent)
        routes_path = release_path / "routes.txt"
        stops_path = release_path / "stops.txt"
        trips_path = release_path / "trips.txt"
        stop_times_path = release_path / "stop_times.txt"
        calendar_dates_path = release_path / "calendar_dates.txt"
    elif any(path is None for path in paths):
        raise ValueError("Provide all static GTFS paths or none of them")

    assert routes_path is not None
    assert stops_path is not None
    assert trips_path is not None
    assert stop_times_path is not None
    release_dir = Path(routes_path).parent
    optional_paths = {
        "agency": release_dir / "agency.txt",
        "calendar": release_dir / "calendar.txt",
        "calendar_dates": calendar_dates_path or release_dir / "calendar_dates.txt",
        "feed_info": release_dir / "feed_info.txt",
        "shapes": release_dir / "shapes.txt",
    }
    release_hash_path = Path(routes_path).parent / ".sha256"
    feed_hash = (
        release_hash_path.read_text(encoding="utf-8").strip()
        if release_hash_path.exists()
        else None
    )
    agencies = (
        [clean_agency(row) for row in read_agency(optional_paths["agency"])]
        if optional_paths["agency"].exists()
        else []
    )
    routes = [clean_route(row) for row in read_routes(routes_path)]
    stops = [clean_stop(row) for row in read_stops(stops_path)]
    trips = [clean_trip(row) for row in read_trips(trips_path)]
    stop_times = (clean_stop_time(row) for row in read_stop_times(stop_times_path))
    calendars = (
        [clean_calendar(row) for row in read_calendar(optional_paths["calendar"])]
        if optional_paths["calendar"].exists()
        else []
    )
    calendar_dates = (
        [clean_calendar_date(row) for row in read_calendar_dates(optional_paths["calendar_dates"])]
        if optional_paths["calendar_dates"].exists()
        else []
    )
    feed_info = (
        [
            {"feed_name": "miway", **clean_feed_info(row)}
            for row in read_feed_info(optional_paths["feed_info"])
        ]
        if optional_paths["feed_info"].exists()
        else []
    )
    shapes = (
        (clean_shape(row) for row in read_shapes(optional_paths["shapes"]))
        if optional_paths["shapes"].exists()
        else None
    )
    with get_connection() as connection:
        if feed_hash is not None and connection.execute(
            """
            SELECT 1 FROM static_feed_loads
            WHERE feed_name = %s AND feed_hash = %s AND loader_version = %s
            """,
            ("miway", feed_hash, STATIC_LOADER_VERSION),
        ).fetchone():
            LOGGER.info("Static GTFS feed was already loaded; skipping")
            return
        if agencies:
            load_agency(connection, agencies)
        load_routes(connection, routes)
        load_stops(connection, stops)
        load_trips(connection, trips)
        if calendars:
            load_calendar(connection, calendars)
        if calendar_dates:
            load_calendar_dates(connection, calendar_dates)
        if feed_info:
            load_feed_info(connection, feed_info)
        if shapes is not None:
            LOGGER.info("Loading shapes...")
            shapes_count = load_shapes(
                connection,
                shapes,
                batch_size=STOP_TIMES_BATCH_SIZE,
                on_batch=lambda count: LOGGER.info("shapes loaded: %s", count),
            )
            LOGGER.info("Loaded %s shapes", shapes_count)
        LOGGER.info("Loading stop_times...")
        stop_times_count = load_stop_times(
            connection,
            stop_times,
            batch_size=STOP_TIMES_BATCH_SIZE,
            on_batch=lambda count: LOGGER.info("stop_times loaded: %s", count),
        )
        LOGGER.info("Loaded %s stop_times", stop_times_count)
        if feed_hash is not None:
            connection.execute(
                """
                INSERT INTO static_feed_loads (feed_name, feed_hash, loader_version)
                VALUES (%s, %s, %s)
                ON CONFLICT (feed_name) DO UPDATE SET
                    feed_hash = EXCLUDED.feed_hash,
                    loader_version = EXCLUDED.loader_version,
                    loaded_at = CURRENT_TIMESTAMP
                """,
                ("miway", feed_hash, STATIC_LOADER_VERSION),
            )


run_pipeline = run_static_pipeline


def poll_once() -> None:
    """Fetch all feeds, then load each feed in its own transaction."""
    load_dotenv(PROJECT_ROOT / ".env")
    raw_dir = PROJECT_ROOT / "data" / "raw" / "realtime"
    feeds = _read_realtime_feeds(raw_dir)
    for name, rows, loader, feed_timestamp, entity_count in feeds:
        with get_connection() as connection:
            history_count, current_count, deleted_count = loader(
                connection,
                rows,
                feed_timestamp=feed_timestamp,
                entity_count=entity_count,
            )
        LOGGER.info(
            "Read %s %s; history inserted %s, current rows affected %s, stale rows deleted %s",
            len(rows),
            name,
            history_count,
            current_count,
            deleted_count,
        )


def _read_realtime_feeds(raw_dir: Path):
    feeds = (
        ("GTFS_RT_LOCATION_URL", read_vehicle_positions, load_vehicle_positions),
        ("GTFS_RT_ALERT_URL", read_alerts, load_alerts),
        ("GTFS_RT_TRIP_UPDATE_URL", read_trip_updates, load_trip_updates),
    )
    loaded = []
    for environment_name, reader, loader in feeds:
        url = os.environ.get(environment_name)
        if not url:
            raise RuntimeError(f"{environment_name} is not set")
        feed = download_gtfs_realtime_feed(url, raw_dir=raw_dir)
        rows = reader(feed)
        loaded.append(
            (
                environment_name.removeprefix("GTFS_RT_").lower(),
                rows,
                loader,
                feed.header.timestamp if feed.header.HasField("timestamp") else None,
                len(feed.entity),
            )
        )
    return loaded

def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Load MiWay static and real-time GTFS data.")
    parser.add_argument("command", nargs="?", choices=("static", "poll"), default="static")
    args = parser.parse_args(argv)
    if args.command == "poll":
        poll_once()
    else:
        run_static_pipeline()

if __name__ == "__main__":
    main()