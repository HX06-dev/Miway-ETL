import csv
import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import httpx

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
    with Path(file_path).open(newline="", encoding="utf-8") as routes_file:
        return list(csv.DictReader(routes_file))

def read_routes(file_path: str | Path) -> list[dict[str, str]]:
    return _read_rows(file_path)

def read_stops(file_path: str | Path) -> list[dict[str, str]]:
    return _read_rows(file_path)

def read_trips(file_path: str | Path) -> list[dict[str, str]]:
    return _read_rows(file_path)


def read_stop_times(file_path: str | Path) -> list[dict[str, str]]:
    return _read_rows(file_path)