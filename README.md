# MiWay ETL

Loads MiWay GTFS data into PostgreSQL.

## Setup

Create `.env` with:

```env
DATABASE_URL=postgresql://USER:PASSWORD@localhost:5433/miway
GTFS_STATIC_URL=https://www.miapp.ca/GTFS/google_transit.zip
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

## Verify

Run [`sql/queries/feed_counts.sql`](sql/queries/feed_counts.sql) in SQLTools, or query:

```sql
SELECT 'routes' AS table_name, COUNT(*) AS row_count FROM routes
UNION ALL SELECT 'stops', COUNT(*) FROM stops
UNION ALL SELECT 'trips', COUNT(*) FROM trips
UNION ALL SELECT 'stop_times', COUNT(*) FROM stop_times;
```

Additional sample queries are in [`sql/queries/`](sql/queries/).