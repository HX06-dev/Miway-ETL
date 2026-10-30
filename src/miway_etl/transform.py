from typing import Any


def _time_to_seconds(value: str) -> int:
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds)


def clean_route(row: dict[str, Any]) -> dict[str, Any]:
    integer_columns = {
        "route_type",
        "route_sort_order",
        "continuous_pickup",
        "continuous_drop_off",
        "cemv_support",
    }
    cleaned_row: dict[str, Any] = {}

    for column, value in row.items():
        if isinstance(value, str):
            value = value.strip() or None
        if column in integer_columns and value is not None:
            value = int(value)
        cleaned_row[column] = value

    for column in (
        "agency_id",
        "route_short_name",
        "route_long_name",
        "route_desc",
        "route_url",
        "route_color",
        "route_text_color",
        "route_sort_order",
        "continuous_pickup",
        "continuous_drop_off",
        "cemv_support",
    ):
        cleaned_row.setdefault(column, None)
    return cleaned_row


def clean_agency(row: dict[str, Any]) -> dict[str, Any]:
    cleaned_row = _clean_strings(row)
    for column in (
        "agency_id",
        "agency_name",
        "agency_url",
        "agency_timezone",
        "agency_lang",
        "agency_phone",
        "agency_fare_url",
        "agency_email",
        "cemv_support",
    ):
        cleaned_row.setdefault(column, None)
    if cleaned_row.get("cemv_support") is not None:
        cleaned_row["cemv_support"] = int(cleaned_row["cemv_support"])
    return cleaned_row


def _clean_strings(row: dict[str, Any]) -> dict[str, Any]:
    return {
        column: value.strip() or None if isinstance(value, str) else value
        for column, value in row.items()
    }

def clean_stop(row: dict[str, Any]) -> dict[str, Any]:
    cleaned_row = _clean_strings(row)
    for column in (
        "stop_code",
        "tts_stop_name",
        "stop_desc",
        "zone_id",
        "stop_url",
        "location_type",
        "parent_station",
        "stop_timezone",
        "wheelchair_boarding",
        "level_id",
        "platform_code",
    ):
        cleaned_row.setdefault(column, None)
    for column in ("stop_lat", "stop_lon"):
        if column in cleaned_row and cleaned_row[column] is not None:
            cleaned_row[column] = float(cleaned_row[column])
    for column in ("location_type", "wheelchair_boarding"):
        if column in cleaned_row and cleaned_row[column] is not None:
            cleaned_row[column] = int(cleaned_row[column])
    return cleaned_row

def clean_trip(row: dict[str, Any]) -> dict[str, Any]:
    cleaned_row = _clean_strings(row)
    for column in (
        "trip_headsign",
        "trip_short_name",
        "direction_id",
        "block_id",
        "shape_id",
        "wheelchair_accessible",
        "bikes_allowed",
    ):
        cleaned_row.setdefault(column, None)
    for column in (
        "direction_id",
        "wheelchair_accessible",
        "bikes_allowed",
    ):
        if column in cleaned_row and cleaned_row[column] is not None:
            cleaned_row[column] = int(cleaned_row[column])
    return cleaned_row

def clean_calendar_date(row: dict[str, Any]) -> dict[str, Any]:
    cleaned_row = _clean_strings(row)
    if cleaned_row.get("exception_type") is not None:
        cleaned_row["exception_type"] = int(cleaned_row["exception_type"])
    return cleaned_row


def clean_calendar(row: dict[str, Any]) -> dict[str, Any]:
    cleaned_row = _clean_strings(row)
    for column in (
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ):
        if cleaned_row.get(column) is not None:
            cleaned_row[column] = int(cleaned_row[column])
    return cleaned_row


def clean_feed_info(row: dict[str, Any]) -> dict[str, Any]:
    cleaned_row = _clean_strings(row)
    for column in (
        "feed_publisher_name",
        "feed_publisher_url",
        "feed_lang",
        "default_lang",
        "feed_start_date",
        "feed_end_date",
        "feed_version",
        "feed_contact_email",
        "feed_contact_url",
    ):
        cleaned_row.setdefault(column, None)
    return cleaned_row


def clean_stop_time(row: dict[str, Any]) -> dict[str, Any]:
    cleaned_row = _clean_strings(row)
    for column in (
        "arrival_time",
        "departure_time",
        "stop_headsign",
        "pickup_type",
        "drop_off_type",
        "continuous_pickup",
        "continuous_drop_off",
        "shape_dist_traveled",
        "timepoint",
    ):
        cleaned_row.setdefault(column, None)
    for column in (
        "stop_sequence",
        "pickup_type",
        "drop_off_type",
        "continuous_pickup",
        "continuous_drop_off",
        "timepoint",
    ):
        if column in cleaned_row and cleaned_row[column] is not None:
            cleaned_row[column] = int(cleaned_row[column])
    if (
        "shape_dist_traveled" in cleaned_row
        and cleaned_row["shape_dist_traveled"] is not None
    ):
        cleaned_row["shape_dist_traveled"] = float(cleaned_row["shape_dist_traveled"])
    for column in ("arrival_time", "departure_time"):
        if column in cleaned_row and cleaned_row[column] is not None:
            cleaned_row[column] = _time_to_seconds(cleaned_row[column])
    return cleaned_row


def clean_shape(row: dict[str, Any]) -> dict[str, Any]:
    cleaned_row = _clean_strings(row)
    cleaned_row.setdefault("shape_dist_traveled", None)
    for column in ("shape_pt_lat", "shape_pt_lon", "shape_dist_traveled"):
        if cleaned_row.get(column) is not None:
            cleaned_row[column] = float(cleaned_row[column])
    if cleaned_row.get("shape_pt_sequence") is not None:
        cleaned_row["shape_pt_sequence"] = int(cleaned_row["shape_pt_sequence"])
    return cleaned_row
