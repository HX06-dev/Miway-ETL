-- Load order:
--   1. routes
--   2. stops
--   3. trips
--   4. stop_times

CREATE TABLE IF NOT EXISTS routes (
    route_id TEXT PRIMARY KEY,
    agency_id TEXT NOT NULL,
    route_short_name TEXT,
    route_long_name TEXT,
    route_desc TEXT,
    route_type SMALLINT NOT NULL CHECK (route_type BETWEEN 0 AND 12),
    route_url TEXT,
    route_color TEXT,
    route_text_color TEXT,
    route_sort_order INTEGER,
    continuous_pickup SMALLINT CHECK (continuous_pickup BETWEEN 0 AND 3),
    continuous_drop_off SMALLINT CHECK (continuous_drop_off BETWEEN 0 AND 3),
    cemv_support SMALLINT CHECK (cemv_support BETWEEN 0 AND 1),
    CONSTRAINT routes_name_required
        CHECK (route_short_name IS NOT NULL OR route_long_name IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS stops (
    stop_id TEXT PRIMARY KEY,
    stop_code TEXT,
    stop_name TEXT NOT NULL,
    tts_stop_name TEXT,
    stop_desc TEXT,
    stop_lat DOUBLE PRECISION NOT NULL CHECK (stop_lat BETWEEN -90 AND 90),
    stop_lon DOUBLE PRECISION NOT NULL CHECK (stop_lon BETWEEN -180 AND 180),
    zone_id TEXT,
    stop_url TEXT,
    location_type SMALLINT CHECK (location_type BETWEEN 0 AND 4),
    parent_station TEXT,
    stop_timezone TEXT,
    wheelchair_boarding SMALLINT CHECK (wheelchair_boarding BETWEEN 0 AND 2),
    level_id TEXT,
    platform_code TEXT,
    CONSTRAINT stops_parent_station_fk
        FOREIGN KEY (parent_station)
        REFERENCES stops (stop_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE IF NOT EXISTS trips (
    route_id TEXT NOT NULL,
    service_id TEXT NOT NULL,
    trip_id TEXT PRIMARY KEY,
    trip_headsign TEXT,
    trip_short_name TEXT,
    direction_id SMALLINT CHECK (direction_id BETWEEN 0 AND 1),
    block_id TEXT,
    shape_id TEXT,
    wheelchair_accessible SMALLINT CHECK (wheelchair_accessible BETWEEN 0 AND 2),
    bikes_allowed SMALLINT CHECK (bikes_allowed BETWEEN 0 AND 2),
    CONSTRAINT trips_route_fk
        FOREIGN KEY (route_id)
        REFERENCES routes (route_id)
);

CREATE TABLE IF NOT EXISTS stop_times (
    trip_id TEXT NOT NULL,
    arrival_time TEXT,
    departure_time TEXT,
    stop_id TEXT NOT NULL,
    stop_sequence INTEGER NOT NULL,
    stop_headsign TEXT,
    pickup_type SMALLINT CHECK (pickup_type BETWEEN 0 AND 3),
    drop_off_type SMALLINT CHECK (drop_off_type BETWEEN 0 AND 3),
    continuous_pickup SMALLINT CHECK (continuous_pickup BETWEEN 0 AND 3),
    continuous_drop_off SMALLINT CHECK (continuous_drop_off BETWEEN 0 AND 3),
    shape_dist_traveled DOUBLE PRECISION,
    timepoint SMALLINT CHECK (timepoint BETWEEN 0 AND 1),
    PRIMARY KEY (trip_id, stop_sequence),
    CONSTRAINT stop_times_trip_fk
        FOREIGN KEY (trip_id)
        REFERENCES trips (trip_id),
    CONSTRAINT stop_times_stop_fk
        FOREIGN KEY (stop_id)
        REFERENCES stops (stop_id)
);