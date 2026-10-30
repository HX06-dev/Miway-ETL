CREATE TABLE IF NOT EXISTS agency (
    agency_id TEXT PRIMARY KEY,
    agency_name TEXT NOT NULL,
    agency_url TEXT NOT NULL,
    agency_timezone TEXT NOT NULL,
    agency_lang TEXT,
    agency_phone TEXT,
    agency_fare_url TEXT,
    agency_email TEXT,
    cemv_support SMALLINT CHECK (cemv_support BETWEEN 0 AND 1)
);

CREATE TABLE IF NOT EXISTS feed_info (
    feed_name TEXT PRIMARY KEY,
    feed_publisher_name TEXT NOT NULL,
    feed_publisher_url TEXT NOT NULL,
    feed_lang TEXT NOT NULL,
    default_lang TEXT,
    feed_start_date DATE,
    feed_end_date DATE,
    feed_version TEXT,
    feed_contact_email TEXT,
    feed_contact_url TEXT
);

CREATE TABLE IF NOT EXISTS calendar (
    service_id TEXT PRIMARY KEY,
    monday SMALLINT NOT NULL CHECK (monday IN (0, 1)),
    tuesday SMALLINT NOT NULL CHECK (tuesday IN (0, 1)),
    wednesday SMALLINT NOT NULL CHECK (wednesday IN (0, 1)),
    thursday SMALLINT NOT NULL CHECK (thursday IN (0, 1)),
    friday SMALLINT NOT NULL CHECK (friday IN (0, 1)),
    saturday SMALLINT NOT NULL CHECK (saturday IN (0, 1)),
    sunday SMALLINT NOT NULL CHECK (sunday IN (0, 1)),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS shapes (
    shape_id TEXT NOT NULL,
    shape_pt_lat DOUBLE PRECISION NOT NULL CHECK (shape_pt_lat BETWEEN -90 AND 90),
    shape_pt_lon DOUBLE PRECISION NOT NULL CHECK (shape_pt_lon BETWEEN -180 AND 180),
    shape_pt_sequence INTEGER NOT NULL,
    shape_dist_traveled DOUBLE PRECISION,
    PRIMARY KEY (shape_id, shape_pt_sequence)
);

ALTER TABLE static_feed_loads
    ADD COLUMN IF NOT EXISTS loader_version INTEGER NOT NULL DEFAULT 1;

ALTER TABLE routes
    ALTER COLUMN agency_id DROP NOT NULL;
