# MiWay ETL

Loads MiWay static GTFS schedules and GTFS-realtime vehicle, trip-update, and
alert feeds into PostgreSQL for transit analysis.

Topics: `gtfs` `gtfs-realtime` `etl` `postgresql` `public-transit` `python`

## Setup

```powershell
Copy-Item .env.example .env
pip install -e ".[dev]"
```

Start PostgreSQL, then initialize or upgrade the database:

```powershell
python -m miway_etl.init_db
```

`init_db` applies versioned SQL migrations. Existing databases are adopted as
the initial baseline before pending migrations are applied.

## Commands

Load the static feed:

```powershell
python -m miway_etl.pipeline static
```

Fetch and load one realtime snapshot:

```powershell
python -m miway_etl.pipeline poll
```

Static and realtime loads use separate transactions. Static data is loaded with
batched `executemany`; `stop_times` and `shapes` are streamed in batches of
10,000 rows. In addition to routes, stops, trips, and stop times, the loader
ingests agency metadata, feed metadata, weekly calendar service, calendar-date
exceptions, and shapes when those optional files are present.
Previously loaded static feed hashes are recorded in PostgreSQL so a successful
unchanged feed is skipped safely. A loader-version marker forces a reload after
the set of loaded static tables changes. Rows absent from a newer feed are
retained; they are not deleted.

Realtime current-state tables are:

```text
vehicle_positions, trip_updates, alerts
```

Each poll also writes timestamped history to:

```text
vehicle_position_history, trip_update_history, alert_history
```

Current upserts reject older feed timestamps. Cleanup follows this policy:

- accepted entities: upsert them, then delete older rows outside the accepted set;
- no entities with a header timestamp: delete rows older than that timestamp;
- all entities rejected, or a missing header timestamp: do not delete;
- download or parse failure: the loader is never called.

Realtime payloads are saved under `data/raw/realtime/` before decoding.

`trips.service_id` is retained as a source identifier.

## Docker polling

The Compose stack starts PostgreSQL, applies migrations, and runs an unattended
realtime poller:

```powershell
docker compose up --build -d
docker compose logs -f poller
```

Set `POLL_INTERVAL_SECONDS` and `RETENTION_DAYS` in `.env` to adjust the polling
interval and retention period. Retention defaults to 30 days; set it to `0` to
disable automated history/raw-file retention. The poller logs failures and
retries on the next interval. Review provider guidance before choosing a
polling interval. The poller container reports unhealthy if no successful poll
has completed for the configured interval plus the maximum expected download
time; inspect this status with `docker compose ps`.
The host `DATABASE_URL` in `.env` is overridden inside Compose to reach the
database service; use `DOCKER_DATABASE_URL` only if a different container
database URL is needed.

Retention removes old realtime history and old files in `data/raw/archives/`,
`data/raw/realtime/`, and `data/raw/releases/`. The latest static release is
always preserved. Retention is based on database record timestamps and file
modification times.

The Compose stack also makes an immediate PostgreSQL custom-format backup, then
repeats according to `BACKUP_INTERVAL_SECONDS` (default: daily). It prunes local
backup files older than `BACKUP_RETENTION_DAYS` (default: 30). Backups are stored
in ignored `data/backups/`; copy them to independent, off-host storage for
disaster recovery. Restore a backup with `pg_restore` into a fresh database.

## Reset

> **Warning:** This permanently deletes all ETL tables and data.

The reset command requires explicit confirmation and only permits local database
hosts:

```powershell
python -m miway_etl.reset_db --yes
python -m miway_etl.init_db
```

For production, use versioned migrations such as Alembic instead of resetting.

## Verify

Run tests:

```powershell
python -m pytest tests
ruff check src tests
```

The CI workflow runs unit tests, Ruff, and the PostgreSQL integration test.
To run integration tests locally, set `TEST_DATABASE_URL` to a separate
disposable PostgreSQL database:

```powershell
$env:TEST_DATABASE_URL = "postgresql://miway:miway@localhost:5433/miway_test"
python -m pytest tests -m integration
```

Example queries:

```sql
SELECT vehicle_id, route_id, trip_id, latitude, longitude, speed
FROM vehicle_positions
ORDER BY timestamp DESC;

SELECT vehicle_id, observed_at, route_id, speed
FROM vehicle_position_history
ORDER BY observed_at DESC;
```

## Design notes

- Static rows are upserted; rows absent from a later feed are retained.
- `stop_times` values are stored as seconds since midnight, including times
  beyond 24:00.
- `delay_seconds` is a convenience value from the first stop's arrival delay;
  use `stop_time_updates` for complete trip data.
- History and raw files need retention policies for unattended polling,
  especially under OneDrive.
- Review the [MiWay developer-download page](https://www.mississauga.ca/miway-transit/developer-download/)
  and provider terms before redistribution. No MiWay-specific polling interval
  is published; follow provider guidance and [GTFS Realtime best
  practices](https://gtfs.org/documentation/realtime/realtime-best-practices/).
