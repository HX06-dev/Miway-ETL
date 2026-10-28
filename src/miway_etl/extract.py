import csv
import os
import tempfile
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import httpx
from google.transit import gtfs_realtime_pb2

FEED_FILES = ("routes.txt", "stops.txt", "trips.txt", "stop_times.txt")

def download_gtfs_files(
    output_dir: str | Path,
    static_url: str | None = None,
) -> Path:
    static_url = static_url or os.environ.get("GTFS_STATIC_URL")
    if not static_url:
        raise RuntimeError("GTFS_STATIC_URL is not set")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    archive_path = (
        output_path
        / "archives"
        / f"gtfs-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex}.zip"
    )
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    partial_archive_path = archive_path.with_suffix(".zip.part")

    try:
        with httpx.stream("GET", static_url, follow_redirects=True, timeout=60) as response:
            response.raise_for_status()
            with partial_archive_path.open("wb") as archive_file:
                for chunk in response.iter_bytes():
                    archive_file.write(chunk)
        partial_archive_path.replace(archive_path)
    except httpx.HTTPError as error:
        partial_archive_path.unlink(missing_ok=True)
        raise RuntimeError(f"Unable to download GTFS feed from {static_url}: {error}") from error

    release_path = output_path / "releases" / archive_path.stem
    release_path.parent.mkdir(parents=True, exist_ok=True)
    staging_path = Path(tempfile.mkdtemp(prefix=f".{release_path.name}.", dir=output_path))
    try:
        with ZipFile(archive_path) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("GTFS feed ZIP is corrupted")

            members = {}
            for name in archive.namelist():
                base_name = Path(name).name
                if base_name in FEED_FILES:
                    if base_name in members:
                        raise RuntimeError(f"GTFS feed contains duplicate file: {base_name}")
                    members[base_name] = name

            missing_files = [file_name for file_name in FEED_FILES if file_name not in members]
            if missing_files:
                missing = ", ".join(missing_files)
                raise RuntimeError(f"GTFS feed is missing required files: {missing}")

            for file_name in FEED_FILES:
                (staging_path / file_name).write_bytes(archive.read(members[file_name]))
        staging_path.replace(release_path)
    except BadZipFile as error:
        for path in staging_path.iterdir():
            path.unlink()
        staging_path.rmdir()
        raise RuntimeError("GTFS feed response is not a valid ZIP archive") from error
    except Exception:
        for path in staging_path.iterdir():
            path.unlink()
        staging_path.rmdir()
        raise

    return release_path

def _read_rows(file_path: str | Path) -> list[dict[str, str]]:
    with Path(file_path).open(newline="", encoding="utf-8") as input_file:
        return list(csv.DictReader(input_file))

def read_routes(file_path: str | Path) -> list[dict[str, str]]:
    return _read_rows(file_path)

def read_stops(file_path: str | Path) -> list[dict[str, str]]:
    return _read_rows(file_path)

def read_trips(file_path: str | Path) -> list[dict[str, str]]:
    return _read_rows(file_path)


def read_stop_times(file_path: str | Path) -> Iterator[dict[str, str]]:
    with Path(file_path).open(newline="", encoding="utf-8") as input_file:
        yield from csv.DictReader(input_file)


def download_gtfs_realtime_feed(url: str | None = None) -> gtfs_realtime_pb2.FeedMessage:
    """Download and decode a GTFS-realtime protobuf feed."""
    if not url:
        raise RuntimeError("A GTFS real-time URL is not set")

    try:
        response = httpx.get(url, follow_redirects=True, timeout=60)
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise RuntimeError(f"Unable to download GTFS real-time feed from {url}: {error}") from error

    feed = gtfs_realtime_pb2.FeedMessage()
    try:
        feed.ParseFromString(response.content)
    except Exception as error:
        raise RuntimeError(f"GTFS real-time feed from {url} is not valid protobuf") from error
    return feed


def read_gtfs_realtime_feed(
    source: bytes | bytearray | memoryview | str | Path,
) -> gtfs_realtime_pb2.FeedMessage:
    """Decode a GTFS-realtime protobuf payload or file."""
    payload = (
        bytes(source)
        if isinstance(source, (bytes, bytearray, memoryview))
        else Path(source).read_bytes()
    )
    feed = gtfs_realtime_pb2.FeedMessage()
    try:
        feed.ParseFromString(payload)
    except Exception as error:
        raise ValueError("GTFS real-time data is not valid protobuf") from error
    return feed


def read_vehicle_positions(
    source: gtfs_realtime_pb2.FeedMessage | bytes | bytearray | memoryview | str | Path,
) -> list[dict[str, object]]:
    feed = (
        source
        if isinstance(source, gtfs_realtime_pb2.FeedMessage)
        else read_gtfs_realtime_feed(source)
    )
    rows = []
    for entity in feed.entity:
        if not entity.HasField("vehicle"):
            continue
        vehicle = entity.vehicle
        position = vehicle.position if vehicle.HasField("position") else None
        trip = vehicle.trip if vehicle.HasField("trip") else None
        rows.append(
            {
                "vehicle_id": vehicle.vehicle.id if vehicle.HasField("vehicle") else entity.id,
                "trip_id": trip.trip_id if trip else None,
                "route_id": trip.route_id if trip else None,
                "direction_id": (
                    trip.direction_id if trip and trip.HasField("direction_id") else None
                ),
                "latitude": position.latitude if position else None,
                "longitude": position.longitude if position else None,
                "bearing": position.bearing if position and position.HasField("bearing") else None,
                "speed": position.speed if position and position.HasField("speed") else None,
                "current_stop_sequence": (
                    vehicle.current_stop_sequence
                    if vehicle.HasField("current_stop_sequence")
                    else None
                ),
                "current_status": vehicle.current_status if vehicle.HasField("current_status") else None,
                "stop_id": vehicle.stop_id if vehicle.HasField("stop_id") else None,
                "timestamp": vehicle.timestamp if vehicle.HasField("timestamp") else None,
                "congestion_level": (
                    vehicle.congestion_level if vehicle.HasField("congestion_level") else None
                ),
                "occupancy_status": (
                    vehicle.occupancy_status if vehicle.HasField("occupancy_status") else None
                ),
                "occupancy_percentage": (
                    vehicle.occupancy_percentage
                    if vehicle.HasField("occupancy_percentage")
                    else None
                ),
            }
        )
    return rows


def read_alerts(
    source: gtfs_realtime_pb2.FeedMessage | bytes | bytearray | memoryview | str | Path,
) -> list[dict[str, object]]:
    feed = (
        source
        if isinstance(source, gtfs_realtime_pb2.FeedMessage)
        else read_gtfs_realtime_feed(source)
    )
    rows = []
    for entity in feed.entity:
        if not entity.HasField("alert"):
            continue
        alert = entity.alert
        rows.append(
            {
                "alert_id": entity.id,
                "active_periods": [
                    {
                        "start": period.start if period.HasField("start") else None,
                        "end": period.end if period.HasField("end") else None,
                    }
                    for period in alert.active_period
                ],
                "informed_entities": [
                    {
                        "agency_id": (
                            informed.agency_id if informed.HasField("agency_id") else None
                        ),
                        "route_id": informed.route_id if informed.HasField("route_id") else None,
                        "trip_id": (
                            informed.trip.trip_id if informed.HasField("trip") else None
                        ),
                        "stop_id": informed.stop_id if informed.HasField("stop_id") else None,
                    }
                    for informed in alert.informed_entity
                ],
                "cause": alert.cause if alert.HasField("cause") else None,
                "effect": alert.effect if alert.HasField("effect") else None,
                "url": alert.url.translation[0].text
                if alert.HasField("url") and alert.url.translation
                else None,
                "header_text": alert.header_text.translation[0].text
                if alert.HasField("header_text") and alert.header_text.translation
                else None,
                "description_text": alert.description_text.translation[0].text
                if alert.HasField("description_text") and alert.description_text.translation
                else None,
            }
        )
    return rows


def read_trip_updates(
    source: gtfs_realtime_pb2.FeedMessage | bytes | bytearray | memoryview | str | Path,
) -> list[dict[str, object]]:
    feed = (
        source
        if isinstance(source, gtfs_realtime_pb2.FeedMessage)
        else read_gtfs_realtime_feed(source)
    )
    rows = []
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        update = entity.trip_update
        trip = update.trip
        vehicle = update.vehicle
        stop_time_updates = [
            {
                "stop_sequence": stop.stop_sequence if stop.HasField("stop_sequence") else None,
                "stop_id": stop.stop_id if stop.HasField("stop_id") else None,
                "arrival": (
                    {"delay": stop.arrival.delay if stop.arrival.HasField("delay") else None,
                     "time": stop.arrival.time if stop.arrival.HasField("time") else None}
                    if stop.HasField("arrival")
                    else None
                ),
                "departure": (
                    {"delay": stop.departure.delay if stop.departure.HasField("delay") else None,
                     "time": stop.departure.time if stop.departure.HasField("time") else None}
                    if stop.HasField("departure")
                    else None
                ),
            }
            for stop in update.stop_time_update
        ]
        rows.append(
            {
                "trip_id": trip.trip_id or entity.id,
                "route_id": trip.route_id if trip.HasField("route_id") else None,
                "vehicle_id": vehicle.id if vehicle.HasField("id") else None,
                "timestamp": update.timestamp if update.HasField("timestamp") else None,
                "delay_seconds": (
                    stop_time_updates[0]["arrival"]["delay"]
                    if stop_time_updates
                    and stop_time_updates[0]["arrival"] is not None
                    and stop_time_updates[0]["arrival"]["delay"] is not None
                    else None
                ),
                "stop_time_updates": stop_time_updates,
            }
        )
    return rows