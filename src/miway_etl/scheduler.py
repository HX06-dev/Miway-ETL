import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from miway_etl.maintenance import cleanup_expired_data, retention_days_from_env
from miway_etl.pipeline import PROJECT_ROOT, poll_once

LOGGER = logging.getLogger(__name__)
HEARTBEAT_PATH = PROJECT_ROOT / "data" / ".poller-last-success"


def _poll_interval_seconds() -> int:
    value = int(os.environ.get("POLL_INTERVAL_SECONDS", "60"))
    if value < 1:
        raise ValueError("POLL_INTERVAL_SECONDS must be a positive integer")
    return value


def run_forever() -> None:
    interval = _poll_interval_seconds()
    retention_days = retention_days_from_env()
    next_cleanup = 0.0
    LOGGER.info(
        "Starting realtime polling every %s seconds; retention is %s days",
        interval,
        retention_days if retention_days else "disabled",
    )
    while True:
        loop_started = time.monotonic()
        try:
            poll_once()
        except Exception:
            LOGGER.exception("Realtime poll failed; the scheduler will retry")
        else:
            try:
                HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
                HEARTBEAT_PATH.touch()
            except OSError:
                LOGGER.exception("Realtime poll succeeded but its health marker could not be updated")

        if retention_days and time.monotonic() >= next_cleanup:
            try:
                cleanup_expired_data(retention_days)
                next_cleanup = time.monotonic() + 24 * 60 * 60
            except Exception:
                LOGGER.exception("Retention cleanup failed; it will be retried in 15 minutes")
                next_cleanup = time.monotonic() + 15 * 60

        time.sleep(max(0, interval - (time.monotonic() - loop_started)))


def main() -> None:
    load_dotenv(Path(PROJECT_ROOT) / ".env")
    run_forever()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
