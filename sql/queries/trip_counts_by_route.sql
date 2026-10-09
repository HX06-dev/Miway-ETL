SELECT
    r.route_id,
    COALESCE(r.route_short_name, r.route_long_name) AS route_name,
    COUNT(t.trip_id) AS trip_count
FROM routes AS r
LEFT JOIN trips AS t ON t.route_id = r.route_id
GROUP BY r.route_id, r.route_short_name, r.route_long_name
ORDER BY trip_count DESC, r.route_id;
