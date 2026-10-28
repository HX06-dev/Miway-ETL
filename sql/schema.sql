-- Load order:
--   1. routes
--   2. stops
--   3. trips
--   4. stop_times

CREATE TABLE IF NOT EXISTS static_feed_loads (
    feed_name TEXT PRIMARY KEY,
    feed_hash TEXT NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

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

CREATE TABLE IF NOT EXISTS calendar_dates (
    service_id TEXT NOT NULL,
    date DATE NOT NULL,
    exception_type SMALLINT NOT NULL CHECK (exception_type IN (1, 2)),
    PRIMARY KEY (service_id, date)
);

CREATE TABLE IF NOT EXISTS stop_times (
    trip_id TEXT NOT NULL,
    arrival_time INTEGER,
    departure_time INTEGER,
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

CREATE TABLE IF NOT EXISTS vehicle_positions (
    vehicle_id TEXT PRIMARY KEY,
    trip_id TEXT,
    route_id TEXT,
    direction_id SMALLINT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    bearing REAL,
    speed REAL,
    current_stop_sequence INTEGER,
    current_status SMALLINT,
    stop_id TEXT,
    timestamp BIGINT,
    congestion_level SMALLINT,
    occupancy_status SMALLINT,
    occupancy_percentage SMALLINT
);

CREATE TABLE IF NOT EXISTS trip_updates (
    trip_id TEXT PRIMARY KEY,
    route_id TEXT,
    vehicle_id TEXT,
    timestamp BIGINT,
    delay_seconds INTEGER,
    stop_time_updates JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY,
    observed_at BIGINT,
    active_periods JSONB NOT NULL,
    informed_entities JSONB NOT NULL,
    cause SMALLINT,
    effect SMALLINT,
    url TEXT,
    header_text TEXT,
    description_text TEXT
);

CREATE INDEX IF NOT EXISTS trips_route_id_idx ON trips (route_id);
CREATE INDEX IF NOT EXISTS stop_times_stop_id_idx ON stop_times (stop_id);
CREATE INDEX IF NOT EXISTS stop_times_departure_time_idx ON stop_times (departure_time);

CREATE TABLE IF NOT EXISTS vehicle_position_history (
    vehicle_id TEXT NOT NULL,
    observed_at BIGINT NOT NULL,
    trip_id TEXT,
    route_id TEXT,
    direction_id SMALLINT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    bearing REAL,
    speed REAL,
    current_stop_sequence INTEGER,
    current_status SMALLINT,
    stop_id TEXT,
    congestion_level SMALLINT,
    occupancy_status SMALLINT,
    occupancy_percentage SMALLINT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (vehicle_id, observed_at)
);

CREATE TABLE IF NOT EXISTS trip_update_history (
    trip_id TEXT NOT NULL,
    observed_at BIGINT NOT NULL,
    route_id TEXT,
    vehicle_id TEXT,
    delay_seconds INTEGER,
    stop_time_updates JSONB NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (trip_id, observed_at)
);

CREATE TABLE IF NOT EXISTS alert_history (
    alert_id TEXT NOT NULL,
    observed_at BIGINT NOT NULL,
    active_periods JSONB NOT NULL,
    informed_entities JSONB NOT NULL,
    cause SMALLINT,
    effect SMALLINT,
    url TEXT,
    header_text TEXT,
    description_text TEXT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (alert_id, observed_at)
);

CREATE INDEX IF NOT EXISTS vehicle_position_history_observed_idx
    ON vehicle_position_history (observed_at);
CREATE INDEX IF NOT EXISTS trip_update_history_observed_idx
    ON trip_update_history (observed_at);