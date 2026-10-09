import csv
import os
from pathlib import Path
from typing import Self
from zipfile import ZipFile

import httpx
import psycopg
import pytest
from dotenv import load_dotenv

from miway_etl import extract, load, pipeline, transform
from miway_etl.db import get_connection


def test_extract_reads_rows_as_dictionaries(tmp_path: Path) -> None:
    routes_path = tmp_path / "routes.txt"
    routes_path.write_text("route_id,route_type\nR1,3\n", encoding="utf-8")

    assert extract.read_routes(routes_path) == [{"route_id": "R1", "route_type": "3"}]


def test_extract_downloads_required_gtfs_files(tmp_path: Path, monkeypatch) -> None:
    archive_path = tmp_path / "feed.zip"
    with ZipFile(archive_path, "w") as archive:
        for file_name in ("routes.txt", "stops.txt", "trips.txt", "stop_times.txt"):
            archive.writestr(f"nested/{file_name}", f"{file_name}\n")

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
    assert list((tmp_path / "archives").glob("*.zip"))


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

    assert route == {"route_id": "R1", "route_type": 3, "route_desc": None}
    assert stop == {
        "stop_id": "S1",
        "stop_lat": 43.5,
        "stop_lon": -79.6,
        "location_type": 0,
    }
    assert trip == {"trip_id": "T1", "direction_id": 1, "trip_headsign": None}


def test_transform_cleans_stop_times() -> None:
    assert transform.clean_stop_time(
        {
            "trip_id": " T1 ",
            "arrival_time": " 25:00:00 ",
            "stop_id": " S1 ",
            "stop_sequence": " 2 ",
            "pickup_type": "0",
            "shape_dist_traveled": " 1.5 ",
        }
    ) == {
        "trip_id": "T1",
        "arrival_time": "25:00:00",
        "stop_id": "S1",
        "stop_sequence": 2,
        "pickup_type": 0,
        "shape_dist_traveled": 1.5,
    }


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
        lambda connection, rows: calls.append(("stop_times", rows)),
    )

    pipeline.run_pipeline(routes_path, stops_path, trips_path, stop_times_path)

    assert [name for name, _ in calls] == ["routes", "stops", "trips", "stop_times"]
    assert calls[0][1] == [{"route_id": "R1", "route_type": 3}]
    assert calls[1][1] == [
        {
            "stop_id": "S1",
            "stop_lat": 43.5,
            "stop_lon": -79.6,
            "location_type": 0,
            "wheelchair_boarding": 1,
        }
    ]
    assert calls[2][1] == [
        {
            "route_id": "R1",
            "service_id": "weekday",
            "trip_id": "T1",
            "direction_id": 1,
            "wheelchair_accessible": 1,
            "bikes_allowed": 1,
        }
    ]
    assert calls[3][1] == [
        {
            "trip_id": "T1",
            "arrival_time": "07:00:00",
            "departure_time": "07:00:00",
            "stop_id": "S1",
            "stop_sequence": 1,
            "timepoint": 1,
        }
    ]


@pytest.mark.integration
def test_pipeline_rolls_back_earlier_upserts_when_trip_load_fails(
    tmp_path: Path, monkeypatch
) -> None:
    load_dotenv(pipeline.PROJECT_ROOT / ".env")
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL is not configured")

    monkeypatch.setattr(
        pipeline,
        "download_gtfs_files",
        lambda output_dir: pipeline.DEFAULT_ROUTES_PATH.parent,
    )
    pipeline.run_pipeline()
    with get_connection() as connection:
        original_name = connection.execute(
            "SELECT route_long_name FROM routes WHERE route_id = %s", ("1",)
        ).fetchone()[0]

    routes_path = tmp_path / "routes.txt"
    trips_path = tmp_path / "trips.txt"
    routes_path.write_text(
        pipeline.DEFAULT_ROUTES_PATH.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    trips_path.write_text(
        pipeline.DEFAULT_TRIPS_PATH.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

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
            trips_path=trips_path,
        )

    with get_connection() as connection:
        persisted_name = connection.execute(
            "SELECT route_long_name FROM routes WHERE route_id = %s", ("1",)
        ).fetchone()[0]

    assert persisted_name == original_name
