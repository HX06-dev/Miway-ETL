from typing import Any


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

    return cleaned_row

def _clean_strings(row: dict[str, Any]) -> dict[str, Any]:
    return {
        column: value.strip() or None if isinstance(value, str) else value
        for column, value in row.items()
    }

def clean_stop(row: dict[str, Any]) -> dict[str, Any]:
    cleaned_row = _clean_strings(row)
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
        "direction_id",
        "wheelchair_accessible",
        "bikes_allowed",
    ):
        if column in cleaned_row and cleaned_row[column] is not None:
            cleaned_row[column] = int(cleaned_row[column])
    return cleaned_row


def clean_stop_time(row: dict[str, Any]) -> dict[str, Any]:
    cleaned_row = _clean_strings(row)
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
    return cleaned_row