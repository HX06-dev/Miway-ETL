from collections.abc import Mapping, Sequence

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


def load_stop_times(
    connection: psycopg.Connection,
    rows: Sequence[Mapping[str, object]],
) -> None:
    with connection.cursor() as cursor:
        cursor.executemany(STOP_TIMES_UPSERT, rows)