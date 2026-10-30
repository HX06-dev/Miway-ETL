import csv
import os
import uuid
from pathlib import Path
from typing import Self
from zipfile import ZipFile

import httpx
import psycopg
import pytest
from dotenv import load_dotenv
from google.transit import gtfs_realtime_pb2

from miway_etl import extract, load, pipeline, transform
from miway_etl.db import get_connection
from miway_etl.init_db import apply_migrations, validate_schema


def test_extract_reads_rows_as_dictionaries(tmp_path: Path) -> None:
    routes_path = tmp_path / "routes.txt"
    routes_path.write_text("route_id,route_type\nR1,3\n", encoding="utf-8")

    assert extract.read_routes(routes_path) == [{"route_id": "R1", "route_type": "3"}]


def test_extract_downloads_required_gtfs_files(tmp_path: Path, monkeypatch) -> None:
    archive_path = tmp_path / "feed.zip"
    with ZipFile(archive_path, "w") as archive:
        for file_name in ("routes.txt", "stops.txt", "trips.txt", "stop_times.txt"):
            archive.writestr(f"nested/{file_name}", f"{file_name}\n")
        archive.writestr(
            "nested/calendar_dates.txt",
            "service_id,date,exception_type\nSERVICE,20261028,1\n",
        )

    class StreamResponse:
        def __enter__(self):
            return httpx.Response(
                200,
                content=archive_path.read_bytes(),
                request=httpx.Request("GET", "https://example.test/feed.zip"),
            )

        def __exit__(self, *args: object) -> None:
            pass

    requests = []
    monkeypatch.setattr(
        extract.httpx,
        "stream",
        lambda method, url, **kwargs: requests.append((method, url, kwargs))
        or StreamResponse(),
    )
    monkeypatch.setenv("GTFS_STATIC_URL", "https://example.test/feed.zip")

    release_path = extract.download_gtfs_files(tmp_path)

    assert requests == [
        ("GET", "https://example.test/feed.zip", {"follow_redirects": True, "timeout": 60})
    ]
    for file_name in ("routes.txt", "stops.txt", "trips.txt", "stop_times.txt"):
        assert (release_path / file_name).read_text(encoding="utf-8") == f"{file_name}\n"
    assert (release_path / "calendar_dates.txt").read_text(encoding="utf-8") == (
        "service_id,date,exception_type\nSERVICE,20261028,1\n"
    )
    assert list((tmp_path / "archives").glob("*.zip"))


def test_extract_rejects_non_zip_download(tmp_path: Path, monkeypatch) -> None:
    class StreamResponse:
        def __enter__(self):
            return httpx.Response(
                200,
                content=b"not a zip",
                request=httpx.Request("GET", "https://example.test/feed.zip"),
            )

        def __exit__(self, *args: object) -> None:
            pass

    monkeypatch.setattr(extract.httpx, "stream", lambda *args, **kwargs: StreamResponse())
    with pytest.raises(RuntimeError, match="not a valid ZIP"):
        extract.download_gtfs_files(tmp_path, "https://example.test/feed.zip")
    assert not list((tmp_path / "archives").glob("*.zip"))


def test_extract_reports_http_404(tmp_path: Path, monkeypatch) -> None:
    def request(*args, **kwargs):
        response = httpx.Response(
            404,
            request=httpx.Request("GET", "https://example.test/feed.zip"),
        )
        response.raise_for_status()
        return response

    class StreamResponse:
        def __enter__(self):
            return request()

        def __exit__(self, *args: object) -> None:
            pass

    monkeypatch.setattr(extract.httpx, "stream", lambda *args, **kwargs: StreamResponse())
    with pytest.raises(RuntimeError, match="Unable to download"):
        extract.download_gtfs_files(tmp_path, "https://example.test/feed.zip")


def test_extract_reads_realtime_entities_and_rejects_missing_trip_id() -> None:
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.timestamp = 100
    vehicle_entity = feed.entity.add()
    vehicle_entity.id = "vehicle-1"
    vehicle_entity.vehicle.vehicle.id = "bus-1"
    vehicle_entity.vehicle.trip.trip_id = "trip-1"
    vehicle_entity.vehicle.timestamp = 99
    vehicle_entity.vehicle.position.speed = 4.5
    update_entity = feed.entity.add()
    update_entity.id = "missing-trip"
    update_entity.trip_update.stop_time_update.add().stop_id = "stop-1"

    vehicles = extract.read_vehicle_positions(feed)
    trip_updates = extract.read_trip_updates(feed)

    assert vehicles[0]["timestamp"] == 99
    assert vehicles[0]["speed"] == 4.5
    assert trip_updates == []


def test_transform_cleans_routes_stops_and_trips() -> None:
    route = transform.clean_route(
        {"route_id": " R1 ", "route_type": " 3 ", "route_desc": " "}
    )
    stop = transform.clean_stop(
        {"stop_id": " S1 ", "stop_lat": " 43.5 ", "stop_lon": "-79.6", "location_type": "0"}
    )
    trip = transform.clean_trip(
        {"trip_id": " T1 ", "direction_id": " 1 ", "trip_headsign": " "}
    )

    assert route["route_id"] == "R1"
    assert route["route_type"] == 3
    assert route["route_desc"] is None
    assert route["agency_id"] is None
    assert stop["stop_id"] == "S1"
    assert stop["stop_lat"] == 43.5
    assert stop["stop_lon"] == -79.6
    assert stop["location_type"] == 0
    assert trip["trip_id"] == "T1"
    assert trip["direction_id"] == 1
    assert trip["trip_headsign"] is None


def test_transform_cleans_stop_times() -> None:
    cleaned = transform.clean_stop_time(
        {
            "trip_id": " T1 ",
            "arrival_time": " 25:00:00 ",
            "stop_id": " S1 ",
            "stop_sequence": " 2 ",
            "pickup_type": "0",
            "shape_dist_traveled": " 1.5 ",
        }
    )
    assert cleaned["trip_id"] == "T1"
    assert cleaned["arrival_time"] == 90000
    assert cleaned["stop_id"] == "S1"
    assert cleaned["stop_sequence"] == 2
    assert cleaned["pickup_type"] == 0
    assert cleaned["shape_dist_traveled"] == 1.5


def test_transform_cleans_additional_static_gtfs_rows() -> None:
    agency = transform.clean_agency(
        {"agency_id": " M1 ", "agency_name": " MiWay ", "cemv_support": "1"}
    )
    assert agency["agency_id"] == "M1"
    assert agency["agency_name"] == "MiWay"
    assert agency["cemv_support"] == 1
    assert transform.clean_calendar(
        {"service_id": " WEEKDAY ", "monday": "1", "sunday": "0"}
    ) == {"service_id": "WEEKDAY", "monday": 1, "sunday": 0}
    assert transform.clean_feed_info({"feed_version": " 3 "})["feed_version"] == "3"
    assert transform.clean_shape(
        {
            "shape_id": " S1 ",
            "shape_pt_lat": "43.5",
            "shape_pt_lon": "-79.6",
            "shape_pt_sequence": "2",
            "shape_dist_traveled": "1.25",
        }
    ) == {
        "shape_id": "S1",
        "shape_pt_lat": 43.5,
        "shape_pt_lon": -79.6,
        "shape_pt_sequence": 2,
        "shape_dist_traveled": 1.25,
    }


def test_prune_raw_files_respects_age_and_latest_release(tmp_path: Path) -> None:
    import os
    from datetime import UTC, datetime, timedelta

    from miway_etl.maintenance import prune_raw_files

    old_time = (datetime.now(UTC) - timedelta(days=31)).timestamp()
    old_archive = tmp_path / "archives" / "old.zip"
    recent_archive = tmp_path / "archives" / "recent.zip"
    old_payload = tmp_path / "realtime" / "old.pb"
    old_release = tmp_path / "releases" / "old"
    latest_release = tmp_path / "releases" / "latest"
    for path in (old_archive, recent_archive, old_payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    for path in (old_release, latest_release):
        path.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".gtfs.latest").write_text(str(latest_release), encoding="utf-8")
    for path in (old_archive, old_payload, old_release):
        os.utime(path, (old_time, old_time))

    assert prune_raw_files(tmp_path, 30) == 3
    assert not old_archive.exists()
    assert recent_archive.exists()
    assert not old_payload.exists()
    assert not old_release.exists()
    assert latest_release.exists()


def test_healthcheck_rejects_stale_poll_heartbeat(
    tmp_path: Path, monkeypatch
) -> None:
    from miway_etl import healthcheck

    heartbeat = tmp_path / "heartbeat"
    heartbeat.touch()
    monkeypatch.setattr(healthcheck, "HEARTBEAT_PATH", heartbeat)
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", "1")

    healthcheck.main()
    stale_time = heartbeat.stat().st_mtime - 200
    os.utime(heartbeat, (stale_time, stale_time))
    with pytest.raises(SystemExit, match="stale"):
        healthcheck.main()


class _Cursor:
    def __init__(self) -> None:
        self.query = ""
        self.rows = []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def executemany(self, query: str, rows: object) -> None:
        self.query = query
        self.rows = list(rows)


class _Connection:
    def __init__(self) -> None:
        self.cursor_instance = _Cursor()

    def cursor(self) -> _Cursor:
        return self.cursor_instance


def test_loaders_execute_upserts() -> None:
    rows = [{"route_id": "R1"}]

    for loader, table in (
        (load.load_routes, "routes"),
        (load.load_stops, "stops"),
        (load.load_trips, "trips"),
        (load.load_stop_times, "stop_times"),
    ):
        connection = _Connection()
        loader(connection, rows)

        assert connection.cursor_instance.rows == rows
        assert f"INSERT INTO {table}" in connection.cursor_instance.query
        assert "ON CONFLICT" in connection.cursor_instance.query


def test_pipeline_extracts_transforms_and_loads_in_order(
    tmp_path: Path, monkeypatch
) -> None:
    routes_path = tmp_path / "routes.txt"
    stops_path = tmp_path / "stops.txt"
    trips_path = tmp_path / "trips.txt"
    stop_times_path = tmp_path / "stop_times.txt"
    routes_path.write_text("route_id,route_type\nR1,3\n", encoding="utf-8")
    stops_path.write_text(
        "stop_id,stop_lat,stop_lon,location_type,wheelchair_boarding\nS1,43.5,-79.6,0,1\n",
        encoding="utf-8",
    )
    trips_path.write_text(
        "route_id,service_id,trip_id,direction_id,wheelchair_accessible,bikes_allowed\n"
        "R1,weekday,T1,1,1,1\n",
        encoding="utf-8",
    )
    stop_times_path.write_text(
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence,timepoint\n"
        "T1,07:00:00,07:00:00,S1,1,1\n",
        encoding="utf-8",
    )

    calls = []

    class ConnectionContext:
        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            pass

    monkeypatch.setattr(pipeline, "get_connection", lambda: ConnectionContext())
    monkeypatch.setattr(
        pipeline,
        "load_routes",
        lambda connection, rows: calls.append(("routes", rows)),
    )
    monkeypatch.setattr(
        pipeline,
        "load_stops",
        lambda connection, rows: calls.append(("stops", rows)),
    )
    monkeypatch.setattr(
        pipeline,
        "load_trips",
        lambda connection, rows: calls.append(("trips", rows)),
    )
    monkeypatch.setattr(
        pipeline,
        "load_stop_times",
        lambda connection, rows, **kwargs: (
            calls.append(("stop_times", list(rows))) or 1
        ),
    )

    pipeline.run_pipeline(routes_path, stops_path, trips_path, stop_times_path)

    assert [name for name, _ in calls] == ["routes", "stops", "trips", "stop_times"]
    assert calls[0][1][0]["route_id"] == "R1"
    assert calls[0][1][0]["route_type"] == 3
    assert calls[1][1][0]["stop_lat"] == 43.5
    assert calls[1][1][0]["wheelchair_boarding"] == 1
    assert calls[2][1][0]["trip_id"] == "T1"
    assert calls[2][1][0]["direction_id"] == 1
    assert calls[3][1][0]["arrival_time"] == 25200
    assert calls[3][1][0]["departure_time"] == 25200


def test_pipeline_loads_optional_static_gtfs_files(
    tmp_path: Path, monkeypatch
) -> None:
    paths = {
        "routes": tmp_path / "routes.txt",
        "stops": tmp_path / "stops.txt",
        "trips": tmp_path / "trips.txt",
        "stop_times": tmp_path / "stop_times.txt",
        "agency": tmp_path / "agency.txt",
        "calendar": tmp_path / "calendar.txt",
        "calendar_dates": tmp_path / "calendar_dates.txt",
        "feed_info": tmp_path / "feed_info.txt",
        "shapes": tmp_path / "shapes.txt",
    }
    paths["routes"].write_text("route_id,route_type\nR1,3\n", encoding="utf-8")
    paths["stops"].write_text(
        "stop_id,stop_lat,stop_lon\nS1,43.5,-79.6\n", encoding="utf-8"
    )
    paths["trips"].write_text(
        "route_id,service_id,trip_id\nR1,weekdays,T1\n", encoding="utf-8"
    )
    paths["stop_times"].write_text(
        "trip_id,stop_id,stop_sequence\nT1,S1,1\n", encoding="utf-8"
    )
    paths["agency"].write_text(
        "agency_id,agency_name,agency_url,agency_timezone,cemv_support\n"
        "M1,MiWay,https://example.test,America/Toronto,1\n",
        encoding="utf-8",
    )
    paths["calendar"].write_text(
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
        "start_date,end_date\n"
        "weekdays,1,1,1,1,1,0,0,20260101,20261231\n",
        encoding="utf-8",
    )
    paths["calendar_dates"].write_text(
        "service_id,date,exception_type\nweekdays,20261028,1\n", encoding="utf-8"
    )
    paths["feed_info"].write_text(
        "feed_publisher_name,feed_publisher_url,feed_lang,feed_version\n"
        "MiWay,https://example.test,en,3\n",
        encoding="utf-8",
    )
    paths["shapes"].write_text(
        "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\nS1,43.5,-79.6,1\n",
        encoding="utf-8",
    )

    calls = []

    class ConnectionContext:
        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            pass

    monkeypatch.setattr(pipeline, "get_connection", lambda: ConnectionContext())
    for name in (
        "agency",
        "routes",
        "stops",
        "trips",
        "calendar",
        "calendar_dates",
        "feed_info",
    ):
        monkeypatch.setattr(
            pipeline,
            f"load_{name}",
            lambda connection, rows, loader_name=name: calls.append(
                (loader_name, list(rows))
            ),
        )
    monkeypatch.setattr(
        pipeline,
        "load_shapes",
        lambda connection, rows, **kwargs: (
            calls.append(("shapes", list(rows))) or 1
        ),
    )
    monkeypatch.setattr(
        pipeline,
        "load_stop_times",
        lambda connection, rows, **kwargs: (
            calls.append(("stop_times", list(rows))) or 1
        ),
    )

    pipeline.run_static_pipeline(
        routes_path=paths["routes"],
        stops_path=paths["stops"],
        trips_path=paths["trips"],
        stop_times_path=paths["stop_times"],
    )

    assert [name for name, _ in calls] == [
        "agency",
        "routes",
        "stops",
        "trips",
        "calendar",
        "calendar_dates",
        "feed_info",
        "shapes",
        "stop_times",
    ]
    assert calls[0][1][0]["cemv_support"] == 1
    assert calls[4][1][0]["monday"] == 1
    assert calls[5][1][0]["exception_type"] == 1
    assert calls[6][1][0]["feed_name"] == "miway"
    assert calls[7][1][0]["shape_pt_lat"] == 43.5


@pytest.mark.integration
def test_pipeline_rolls_back_earlier_upserts_when_trip_load_fails(
    tmp_path: Path, monkeypatch
) -> None:
    load_dotenv(pipeline.PROJECT_ROOT / ".env")
    test_database_url = os.environ.get("TEST_DATABASE_URL")
    if not test_database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    with get_connection() as connection:
        apply_migrations(connection)
        apply_migrations(connection)
        validate_schema(connection)

    route_id = f"TEST_ROUTE_{uuid.uuid4().hex}"
    trip_id = f"TEST_TRIP_{uuid.uuid4().hex}"
    routes_path = tmp_path / "routes.txt"
    stops_path = tmp_path / "stops.txt"
    trips_path = tmp_path / "trips.txt"
    stop_times_path = tmp_path / "stop_times.txt"
    (tmp_path / "agency.txt").write_text(
        "agency_id,agency_name,agency_url,agency_timezone\n"
        "TEST,Test Agency,https://example.test,America/Toronto\n",
        encoding="utf-8",
    )
    (tmp_path / "calendar.txt").write_text(
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
        "start_date,end_date\n"
        "TEST,1,1,1,1,1,0,0,20261001,20261231\n",
        encoding="utf-8",
    )
    (tmp_path / "calendar_dates.txt").write_text(
        "service_id,date,exception_type\nTEST,20261028,1\n", encoding="utf-8"
    )
    (tmp_path / "feed_info.txt").write_text(
        "feed_publisher_name,feed_publisher_url,feed_lang,feed_start_date,feed_end_date\n"
        "Test,https://example.test,en,20261001,20261231\n",
        encoding="utf-8",
    )
    (tmp_path / "shapes.txt").write_text(
        "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n"
        "TEST_SHAPE,43.5,-79.6,1\n",
        encoding="utf-8",
    )
    routes_path.write_text(
        "route_id,agency_id,route_short_name,route_long_name,route_type\n"
        f"{route_id},TEST,1,Original,3\n",
        encoding="utf-8",
    )
    stops_path.write_text(
        "stop_id,stop_name,stop_lat,stop_lon\nTEST_STOP,Test Stop,43.5,-79.6\n",
        encoding="utf-8",
    )
    trips_path.write_text(
        "route_id,service_id,trip_id\n"
        f"{route_id},TEST,{trip_id}\n",
        encoding="utf-8",
    )
    stop_times_path.write_text(
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        f"{trip_id},08:00:00,08:00:00,TEST_STOP,1\n",
        encoding="utf-8",
    )
    pipeline.run_pipeline(routes_path, stops_path, trips_path, stop_times_path)
    with get_connection() as connection:
        original_name = connection.execute(
            "SELECT route_long_name FROM routes WHERE route_id = %s", (route_id,)
        ).fetchone()[0]

    with routes_path.open(newline="", encoding="utf-8") as file:
        routes = list(csv.DictReader(file))
    routes[0]["route_long_name"] = "ROLLBACK SENTINEL"
    with routes_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=routes[0].keys())
        writer.writeheader()
        writer.writerows(routes)

    with trips_path.open(newline="", encoding="utf-8") as file:
        trips = list(csv.DictReader(file))
    trips[0]["route_id"] = "DOES_NOT_EXIST"
    with trips_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=trips[0].keys())
        writer.writeheader()
        writer.writerows(trips)

    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        pipeline.run_pipeline(
            routes_path=routes_path,
            stops_path=stops_path,
            trips_path=trips_path,
            stop_times_path=stop_times_path,
        )

    with get_connection() as connection:
        persisted_name = connection.execute(
            "SELECT route_long_name FROM routes WHERE route_id = %s", (route_id,)
        ).fetchone()[0]

    assert persisted_name == original_name
