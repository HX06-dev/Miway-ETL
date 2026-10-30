import time

from miway_etl.scheduler import HEARTBEAT_PATH, _poll_interval_seconds


def main() -> None:
    interval = _poll_interval_seconds()
    stale_after = max(interval * 3, interval + 180)
    if not HEARTBEAT_PATH.is_file():
        raise SystemExit("No successful realtime poll has completed")
    if time.time() - HEARTBEAT_PATH.stat().st_mtime > stale_after:
        raise SystemExit("Last successful realtime poll is stale")


if __name__ == "__main__":
    main()
