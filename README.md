# MiWay ETL

Loads MiWay GTFS data into PostgreSQL.

## Setup

Create `.env` with:

```env
DATABASE_URL=postgresql://USER:PASSWORD@localhost:5433/miway
GTFS_STATIC_URL=https://www.miapp.ca/GTFS/google_transit.zip
GTFS_RT_LOCATION_URL=https://www.miapp.ca/GTFS_RT/Vehicle/VehiclePositions.pb
GTFS_RT_ALERT_URL=https://www.miapp.ca/gtfs_rt/Alerts/Alerts.pb
GTFS_RT_TRIP_UPDATE_URL=https://www.miapp.ca/gtfs_rt/TripUpdate/TripUpdates.pb
```

Install dependencies:

```powershell
pip install -e .
```

## Reset and load

From the repository root:

```powershell
python -m miway_etl.reset_db
python -m miway_etl.init_db
python -m miway_etl.pipeline
```

The pipeline downloads the GTFS feed and loads:

```text
routes → stops → trips → stop_times
```

The `stop_times` load may take several minutes.

To also fetch and load the current GTFS-realtime snapshots, call the pipeline with
`include_realtime=True`:

```powershell
python -c "from miway_etl.pipeline import run_pipeline; run_pipeline(include_realtime=True)"
```

The real-time feeds are decoded as protobuf and stored in `vehicle_positions`,
`trip_updates`, and `alerts`. These tables represent the latest snapshot for each
vehicle, trip, or alert and are upserted on each run.

## Verify

Run [`sql/queries/feed_counts.sql`](sql/queries/feed_counts.sql) in SQLTools, or query:

```sql
SELECT 'routes' AS table_name, COUNT(*) AS row_count FROM routes
UNION ALL SELECT 'stops', COUNT(*) FROM stops
UNION ALL SELECT 'trips', COUNT(*) FROM trips
UNION ALL SELECT 'stop_times', COUNT(*) FROM stop_times;
```

Current real-time data can be queried with:

```sql
SELECT vehicle_id, route_id, trip_id, latitude, longitude, speed
FROM vehicle_positions
ORDER BY updated_at DESC;
```

Additional sample queries are in [`sql/queries/`](sql/queries/).