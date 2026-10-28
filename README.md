# MiWay ETL

Loads MiWay static GTFS schedules and GTFS-realtime vehicle, trip-update, and
alert feeds into PostgreSQL for transit analysis.

Topics: `gtfs` `gtfs-realtime` `etl` `postgresql` `public-transit` `python`

## Setup

```powershell
Copy-Item .env.example .env
pip install -e .
```

Start PostgreSQL, then initialize the schema:

```powershell
python -m miway_etl.init_db
```

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
batched `executemany`; `stop_times` is streamed in batches of 10,000 rows.
Previously loaded static feed hashes are recorded in PostgreSQL so a successful
unchanged feed is skipped safely.

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

`trips.service_id` is retained as a source identifier. The optional
`calendar_dates.txt` feed is stored in `calendar_dates`; weekly `calendar.txt`
modeling is intentionally not included.

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
```

The suite covers static extraction failures, protobuf parsing, transformations,
load ordering, and rollback. Integration tests require a separate
`TEST_DATABASE_URL`:

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
