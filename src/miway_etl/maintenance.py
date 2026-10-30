import logging
import os
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from miway_etl.db import get_connection

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGGER = logging.getLogger(__name__)
HISTORY_TABLES = (
    "vehicle_position_history",
    "trip_update_history",
    "alert_history",
)


@dataclass(frozen=True)
class RetentionResult:
    history_rows_deleted: int
    files_deleted: int


def retention_days_from_env() -> int:
    value = int(os.environ.get("RETENTION_DAYS", "30"))
    if value < 0:
        raise ValueError("RETENTION_DAYS must be zero or a positive integer")
    return value


def prune_raw_files(raw_dir: str | Path, retention_days: int) -> int:
    if retention_days < 0:
        raise ValueError("retention_days must be zero or a positive integer")
    if retention_days == 0:
        return 0

    raw_path = Path(raw_dir)
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    latest_release: Path | None = None
    latest_path = raw_path / ".gtfs.latest"
    if latest_path.exists():
        latest_release = Path(latest_path.read_text(encoding="utf-8").strip())
        if not latest_release.is_absolute():
            latest_release = raw_path / latest_release
        latest_release = latest_release.resolve()

    deleted = 0
    for folder_name, suffix in (("archives", ".zip"), ("realtime", ".pb")):
        folder = raw_path / folder_name
        if not folder.exists():
            continue
        for path in folder.iterdir():
            if path.is_file() and path.suffix.lower() == suffix:
                modified_at = datetime.fromtimestamp(path.stat().st_mtime, UTC)
                if modified_at < cutoff:
                    path.unlink()
                    deleted += 1

    releases = raw_path / "releases"
    if releases.exists():
        for path in releases.iterdir():
            if (
                path.is_dir()
                and not path.is_symlink()
                and latest_release != path.resolve()
                and datetime.fromtimestamp(path.stat().st_mtime, UTC) < cutoff
            ):
                shutil.rmtree(path)
                deleted += 1
    return deleted


def cleanup_expired_data(
    retention_days: int,
    raw_dir: str | Path | None = None,
) -> RetentionResult:
    if retention_days < 0:
        raise ValueError("retention_days must be zero or a positive integer")
    if retention_days == 0:
        LOGGER.info("Retention cleanup is disabled")
        return RetentionResult(history_rows_deleted=0, files_deleted=0)

    history_rows_deleted = 0
    with get_connection() as connection:
        for table_name in HISTORY_TABLES:
            result = connection.execute(
                f"DELETE FROM {table_name} "
                "WHERE recorded_at < CURRENT_TIMESTAMP - (%s * INTERVAL '1 day')",
                (retention_days,),
            )
            history_rows_deleted += max(result.rowcount, 0)

    files_deleted = prune_raw_files(
        raw_dir or PROJECT_ROOT / "data" / "raw",
        retention_days,
    )
    LOGGER.info(
        "Retention cleanup deleted %s history rows and %s files",
        history_rows_deleted,
        files_deleted,
    )
    return RetentionResult(history_rows_deleted, files_deleted)


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    cleanup_expired_data(retention_days_from_env())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
