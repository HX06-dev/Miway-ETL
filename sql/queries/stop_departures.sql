WITH parameters AS (
    SELECT '0001'::TEXT AS stop_id
)
SELECT
    st.trip_id,
    st.stop_sequence,
    st.stop_id,
    s.stop_name,
    st.departure_time
FROM stop_times AS st
JOIN stops AS s ON s.stop_id = st.stop_id
JOIN parameters AS p ON p.stop_id = st.stop_id
ORDER BY st.departure_time, st.trip_id, st.stop_sequence;
