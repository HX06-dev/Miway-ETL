import json
from collections.abc import Callable, Iterable, Mapping, Sequence

import psycopg

ROUTES_UPSERT = """
INSERT INTO routes (
    route_id,
    agency_id,
    route_short_name,
    route_long_name,
    route_desc,
    route_type,
    route_url,
    route_color,
    route_text_color,
    route_sort_order,
    continuous_pickup,
    continuous_drop_off,
    cemv_support
)
VALUES (
    %(route_id)s,
    %(agency_id)s,
    %(route_short_name)s,
    %(route_long_name)s,
    %(route_desc)s,
    %(route_type)s,
    %(route_url)s,
    %(route_color)s,
    %(route_text_color)s,
    %(route_sort_order)s,
    %(continuous_pickup)s,
    %(continuous_drop_off)s,
    %(cemv_support)s
)
ON CONFLICT (route_id) DO UPDATE SET
    agency_id = EXCLUDED.agency_id,
    route_short_name = EXCLUDED.route_short_name,
    route_long_name = EXCLUDED.route_long_name,
    route_desc = EXCLUDED.route_desc,
    route_type = EXCLUDED.route_type,
    route_url = EXCLUDED.route_url,
    route_color = EXCLUDED.route_color,
    route_text_color = EXCLUDED.route_text_color,
    route_sort_order = EXCLUDED.route_sort_order,
    continuous_pickup = EXCLUDED.continuous_pickup,
    continuous_drop_off = EXCLUDED.continuous_drop_off,
    cemv_support = EXCLUDED.cemv_support
"""

STOPS_UPSERT = """
INSERT INTO stops (
    stop_id, stop_code, stop_name, tts_stop_name, stop_desc, stop_lat,
    stop_lon, zone_id, stop_url, location_type, parent_station,
    stop_timezone, wheelchair_boarding, level_id, platform_code
)
VALUES (
    %(stop_id)s, %(stop_code)s, %(stop_name)s, %(tts_stop_name)s, %(stop_desc)s,
    %(stop_lat)s, %(stop_lon)s, %(zone_id)s, %(stop_url)s, %(location_type)s,
    %(parent_station)s, %(stop_timezone)s, %(wheelchair_boarding)s,
    %(level_id)s, %(platform_code)s
)
ON CONFLICT (stop_id) DO UPDATE SET
    stop_code = EXCLUDED.stop_code,
    stop_name = EXCLUDED.stop_name,
    tts_stop_name = EXCLUDED.tts_stop_name,
    stop_desc = EXCLUDED.stop_desc,
    stop_lat = EXCLUDED.stop_lat,
    stop_lon = EXCLUDED.stop_lon,
    zone_id = EXCLUDED.zone_id,
    stop_url = EXCLUDED.stop_url,
    location_type = EXCLUDED.location_type,
    parent_station = EXCLUDED.parent_station,
    stop_timezone = EXCLUDED.stop_timezone,
    wheelchair_boarding = EXCLUDED.wheelchair_boarding,
    level_id = EXCLUDED.level_id,
    platform_code = EXCLUDED.platform_code
"""

TRIPS_UPSERT = """
INSERT INTO trips (
    route_id, service_id, trip_id, trip_headsign, trip_short_name,
    direction_id, block_id, shape_id, wheelchair_accessible, bikes_allowed
)
VALUES (
    %(route_id)s, %(service_id)s, %(trip_id)s, %(trip_headsign)s,
    %(trip_short_name)s, %(direction_id)s, %(block_id)s, %(shape_id)s,
    %(wheelchair_accessible)s, %(bikes_allowed)s
)
ON CONFLICT (trip_id) DO UPDATE SET
    route_id = EXCLUDED.route_id,
    service_id = EXCLUDED.service_id,
    trip_headsign = EXCLUDED.trip_headsign,
    trip_short_name = EXCLUDED.trip_short_name,
    direction_id = EXCLUDED.direction_id,
    block_id = EXCLUDED.block_id,
    shape_id = EXCLUDED.shape_id,
    wheelchair_accessible = EXCLUDED.wheelchair_accessible,
    bikes_allowed = EXCLUDED.bikes_allowed
"""

CALENDAR_DATES_UPSERT = """
INSERT INTO calendar_dates (service_id, date, exception_type)
VALUES (%(service_id)s, %(date)s, %(exception_type)s)
ON CONFLICT (service_id, date) DO UPDATE SET
    exception_type = EXCLUDED.exception_type
"""

STOP_TIMES_UPSERT = """
INSERT INTO stop_times (
    trip_id, arrival_time, departure_time, stop_id, stop_sequence,
    stop_headsign, pickup_type, drop_off_type, continuous_pickup,
    continuous_drop_off, shape_dist_traveled, timepoint
)
VALUES (
    %(trip_id)s, %(arrival_time)s, %(departure_time)s, %(stop_id)s,
    %(stop_sequence)s, %(stop_headsign)s, %(pickup_type)s, %(drop_off_type)s,
    %(continuous_pickup)s, %(continuous_drop_off)s,
    %(shape_dist_traveled)s, %(timepoint)s
)
ON CONFLICT (trip_id, stop_sequence) DO UPDATE SET
    arrival_time = EXCLUDED.arrival_time,
    departure_time = EXCLUDED.departure_time,
    stop_id = EXCLUDED.stop_id,
    stop_headsign = EXCLUDED.stop_headsign,
    pickup_type = EXCLUDED.pickup_type,
    drop_off_type = EXCLUDED.drop_off_type,
    continuous_pickup = EXCLUDED.continuous_pickup,
    continuous_drop_off = EXCLUDED.continuous_drop_off,
    shape_dist_traveled = EXCLUDED.shape_dist_traveled,
    timepoint = EXCLUDED.timepoint
"""

VEHICLE_POSITIONS_UPSERT = """
INSERT INTO vehicle_positions (
    vehicle_id, trip_id, route_id, direction_id, latitude, longitude, bearing,
    speed, current_stop_sequence, current_status, stop_id, timestamp,
    congestion_level, occupancy_status, occupancy_percentage
)
VALUES (
    %(vehicle_id)s, %(trip_id)s, %(route_id)s, %(direction_id)s, %(latitude)s,
    %(longitude)s, %(bearing)s, %(speed)s, %(current_stop_sequence)s,
    %(current_status)s, %(stop_id)s, %(timestamp)s, %(congestion_level)s,
    %(occupancy_status)s, %(occupancy_percentage)s
)
ON CONFLICT (vehicle_id) DO UPDATE SET
    trip_id = EXCLUDED.trip_id, route_id = EXCLUDED.route_id,
    direction_id = EXCLUDED.direction_id, latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude, bearing = EXCLUDED.bearing,
    speed = EXCLUDED.speed, current_stop_sequence = EXCLUDED.current_stop_sequence,
    current_status = EXCLUDED.current_status, stop_id = EXCLUDED.stop_id,
    timestamp = EXCLUDED.timestamp, congestion_level = EXCLUDED.congestion_level,
    occupancy_status = EXCLUDED.occupancy_status,
    occupancy_percentage = EXCLUDED.occupancy_percentage
WHERE vehicle_positions.timestamp IS NULL
   OR EXCLUDED.timestamp IS NULL
   OR EXCLUDED.timestamp >= vehicle_positions.timestamp
"""

TRIP_UPDATES_UPSERT = """
INSERT INTO trip_updates (
    trip_id, route_id, vehicle_id, timestamp, delay_seconds, stop_time_updates
)
VALUES (
    %(trip_id)s, %(route_id)s, %(vehicle_id)s, %(timestamp)s, %(delay_seconds)s,
    %(stop_time_updates)s::jsonb
)
ON CONFLICT (trip_id) DO UPDATE SET
    route_id = EXCLUDED.route_id, vehicle_id = EXCLUDED.vehicle_id,
    timestamp = EXCLUDED.timestamp, delay_seconds = EXCLUDED.delay_seconds,
    stop_time_updates = EXCLUDED.stop_time_updates
WHERE trip_updates.timestamp IS NULL
   OR EXCLUDED.timestamp IS NULL
   OR EXCLUDED.timestamp >= trip_updates.timestamp
"""

ALERTS_UPSERT = """
INSERT INTO alerts (
    alert_id, observed_at, active_periods, informed_entities, cause, effect, url,
    header_text, description_text
)
VALUES (
    %(alert_id)s, %(observed_at)s, %(active_periods)s::jsonb,
    %(informed_entities)s::jsonb, %(cause)s, %(effect)s, %(url)s,
    %(header_text)s, %(description_text)s
)
ON CONFLICT (alert_id) DO UPDATE SET
    observed_at = EXCLUDED.observed_at,
    active_periods = EXCLUDED.active_periods,
    informed_entities = EXCLUDED.informed_entities, cause = EXCLUDED.cause,
    effect = EXCLUDED.effect, url = EXCLUDED.url,
    header_text = EXCLUDED.header_text, description_text = EXCLUDED.description_text
WHERE alerts.observed_at IS NULL
   OR EXCLUDED.observed_at IS NULL
   OR EXCLUDED.observed_at >= alerts.observed_at
"""

VEHICLE_POSITION_HISTORY_INSERT = """
INSERT INTO vehicle_position_history (
    vehicle_id, observed_at, trip_id, route_id, direction_id, latitude, longitude,
    bearing, speed, current_stop_sequence, current_status, stop_id,
    congestion_level, occupancy_status, occupancy_percentage
)
VALUES (
    %(vehicle_id)s, %(timestamp)s, %(trip_id)s, %(route_id)s, %(direction_id)s,
    %(latitude)s, %(longitude)s, %(bearing)s, %(speed)s, %(current_stop_sequence)s,
    %(current_status)s, %(stop_id)s, %(congestion_level)s, %(occupancy_status)s,
    %(occupancy_percentage)s
)
ON CONFLICT (vehicle_id, observed_at) DO NOTHING
"""

TRIP_UPDATE_HISTORY_INSERT = """
INSERT INTO trip_update_history (
    trip_id, observed_at, route_id, vehicle_id, delay_seconds, stop_time_updates
)
VALUES (
    %(trip_id)s, %(timestamp)s, %(route_id)s, %(vehicle_id)s, %(delay_seconds)s,
    %(stop_time_updates)s::jsonb
)
ON CONFLICT (trip_id, observed_at) DO NOTHING
"""

ALERT_HISTORY_INSERT = """
INSERT INTO alert_history (
    alert_id, observed_at, active_periods, informed_entities, cause, effect,
    url, header_text, description_text
)
SELECT
    %(alert_id)s, %(observed_at)s, %(active_periods)s::jsonb,
    %(informed_entities)s::jsonb, %(cause)s, %(effect)s, %(url)s,
    %(header_text)s, %(description_text)s
WHERE NOT EXISTS (
    SELECT 1 FROM alert_history
    WHERE alert_id = %(alert_id)s
      AND active_periods = %(active_periods)s::jsonb
      AND informed_entities = %(informed_entities)s::jsonb
      AND cause IS NOT DISTINCT FROM %(cause)s
      AND effect IS NOT DISTINCT FROM %(effect)s
      AND url IS NOT DISTINCT FROM %(url)s
      AND header_text IS NOT DISTINCT FROM %(header_text)s
      AND description_text IS NOT DISTINCT FROM %(description_text)s
)
ON CONFLICT (alert_id, observed_at) DO NOTHING
"""

def load_routes(
    connection: psycopg.Connection,
    rows: Sequence[Mapping[str, object]],
) -> None:
    with connection.cursor() as cursor:
        cursor.executemany(ROUTES_UPSERT, rows)


def load_stops(
    connection: psycopg.Connection,
    rows: Sequence[Mapping[str, object]],
) -> None:
    with connection.cursor() as cursor:
        cursor.executemany(STOPS_UPSERT, rows)


def load_trips(
    connection: psycopg.Connection,
    rows: Sequence[Mapping[str, object]],
) -> None:
    with connection.cursor() as cursor:
        cursor.executemany(TRIPS_UPSERT, rows)

def load_calendar_dates(
    connection: psycopg.Connection,
    rows: Sequence[Mapping[str, object]],
) -> None:
    with connection.cursor() as cursor:
        cursor.executemany(CALENDAR_DATES_UPSERT, rows)


def load_stop_times(
    connection: psycopg.Connection,
    rows: Iterable[Mapping[str, object]],
    batch_size: int = 10_000,
    on_batch: Callable[[int], None] | None = None,
) -> int:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")

    total = 0
    with connection.cursor() as cursor:
        batch = []
        for row in rows:
            batch.append(row)
            if len(batch) == batch_size:
                cursor.executemany(STOP_TIMES_UPSERT, batch)
                total += len(batch)
                if on_batch is not None:
                    on_batch(total)
                batch.clear()
        if batch:
            cursor.executemany(STOP_TIMES_UPSERT, batch)
            total += len(batch)
            if on_batch is not None:
                on_batch(total)
    return total


def _json_rows(rows: Sequence[Mapping[str, object]], columns: Sequence[str]) -> list[dict[str, object]]:
    return [
        {
            **row,
            **{column: json.dumps(row[column]) for column in columns},
        }
        for row in rows
    ]


def load_vehicle_positions(
    connection: psycopg.Connection,
    rows: Sequence[Mapping[str, object]],
    *,
    feed_timestamp: int | None = None,
    entity_count: int | None = None,
) -> tuple[int, int, int]:
    return load_realtime_snapshot(
        connection, rows, VEHICLE_POSITIONS_UPSERT, VEHICLE_POSITION_HISTORY_INSERT,
        (), "vehicle_id", "timestamp",
        "DELETE FROM vehicle_positions "
        "WHERE vehicle_id <> ALL(%s) AND (timestamp IS NULL OR timestamp <= %s)",
        feed_timestamp=feed_timestamp,
        entity_count=entity_count,
    )


def load_trip_updates(
    connection: psycopg.Connection,
    rows: Sequence[Mapping[str, object]],
    *,
    feed_timestamp: int | None = None,
    entity_count: int | None = None,
) -> tuple[int, int, int]:
    return load_realtime_snapshot(
        connection, rows, TRIP_UPDATES_UPSERT, TRIP_UPDATE_HISTORY_INSERT,
        ("stop_time_updates",), "trip_id", "timestamp",
        "DELETE FROM trip_updates "
        "WHERE trip_id <> ALL(%s) AND (timestamp IS NULL OR timestamp <= %s)",
        feed_timestamp=feed_timestamp,
        entity_count=entity_count,
    )


def load_alerts(
    connection: psycopg.Connection,
    rows: Sequence[Mapping[str, object]],
    *,
    feed_timestamp: int | None = None,
    entity_count: int | None = None,
) -> tuple[int, int, int]:
    return load_realtime_snapshot(
        connection, rows, ALERTS_UPSERT, ALERT_HISTORY_INSERT,
        ("active_periods", "informed_entities"), "alert_id", "observed_at",
        "DELETE FROM alerts "
        "WHERE alert_id <> ALL(%s) AND (observed_at IS NULL OR observed_at <= %s)",
        feed_timestamp=feed_timestamp,
        entity_count=entity_count,
    )


def load_realtime_snapshot(
    connection: psycopg.Connection,
    rows: Sequence[Mapping[str, object]],
    current_query: str,
    history_query: str,
    json_columns: Sequence[str],
    current_key: str,
    observed_key: str,
    delete_query: str | None = None,
    *,
    feed_timestamp: int | None = None,
    entity_count: int | None = None,
) -> tuple[int, int, int]:
    current_rows = [row for row in rows if row.get(current_key) is not None]
    historical_rows = [
        row for row in current_rows if row.get(observed_key) is not None
    ]
    with connection.cursor() as cursor:
        history_count = 0
        current_count = 0
        if historical_rows:
            cursor.executemany(history_query, _json_rows(historical_rows, json_columns))
            history_count = max(cursor.rowcount, 0)
        if current_rows:
            cursor.executemany(current_query, _json_rows(current_rows, json_columns))
            current_count = max(cursor.rowcount, 0)
        accepted_entities_seen = bool(current_rows) or entity_count == 0
        cutoff = feed_timestamp
        if delete_query is not None and accepted_entities_seen and cutoff is not None:
            cursor.execute(
                delete_query,
                ([row[current_key] for row in current_rows], cutoff),
            )
            deleted_count = max(cursor.rowcount, 0)
        else:
            deleted_count = 0
    return history_count, current_count, deleted_count