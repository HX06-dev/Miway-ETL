SELECT
    route_id,
    route_short_name,
    route_long_name,
    route_type
FROM routes
ORDER BY route_short_name NULLS LAST, route_id;
