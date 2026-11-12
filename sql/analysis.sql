SELECT COUNT(DISTINCT unique_key) AS distinct_requests,
       COUNT(*)                   AS rows_in_table
FROM service_requests;

SELECT complaint_type,
       COUNT(*) AS requests,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_all
FROM service_requests
GROUP BY complaint_type
ORDER BY requests DESC
LIMIT 10;

SELECT agency,
       MAX(agency_name) AS agency_name,
       COUNT(*) AS requests,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_all
FROM service_requests
GROUP BY agency
ORDER BY requests DESC;

SELECT borough,
       COUNT(*) AS requests,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_all
FROM service_requests
GROUP BY borough
ORDER BY requests DESC;

SELECT created_year_month AS month,
       COUNT(*) AS requests
FROM service_requests
GROUP BY created_year_month
ORDER BY created_year_month;

SELECT created_weekday_num AS weekday_num,
       created_weekday     AS weekday,
       created_hour        AS hour,
       COUNT(*)            AS requests
FROM service_requests
GROUP BY created_weekday_num, created_weekday, created_hour
ORDER BY weekday_num, hour;

SELECT status,
       COUNT(*) AS requests,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_all
FROM service_requests
GROUP BY status
ORDER BY requests DESC;

SELECT COUNT(resolution_hours)                                          AS n_valid,
       ROUND(AVG(resolution_hours)::numeric, 2)                         AS mean_h,
       ROUND(percentile_cont(0.5)  WITHIN GROUP (ORDER BY resolution_hours)::numeric, 2) AS median_h,
       ROUND(MIN(resolution_hours)::numeric, 2)                         AS min_h,
       ROUND(percentile_cont(0.25) WITHIN GROUP (ORDER BY resolution_hours)::numeric, 2) AS q1_h,
       ROUND(percentile_cont(0.75) WITHIN GROUP (ORDER BY resolution_hours)::numeric, 2) AS q3_h,
       ROUND(percentile_cont(0.95) WITHIN GROUP (ORDER BY resolution_hours)::numeric, 2) AS p95_h,
       ROUND(MAX(resolution_hours)::numeric, 2)                         AS max_h,
       ROUND(STDDEV_SAMP(resolution_hours)::numeric, 2)                 AS std_h
FROM service_requests
WHERE resolution_hours IS NOT NULL;

SELECT complaint_type,
       COUNT(resolution_hours) AS n_valid,
       ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY resolution_hours)::numeric, 2) AS median_h,
       ROUND(AVG(resolution_hours)::numeric, 2) AS mean_h
FROM service_requests
WHERE resolution_hours IS NOT NULL
GROUP BY complaint_type
HAVING COUNT(resolution_hours) >= 100
ORDER BY median_h DESC;

SELECT agency,
       COUNT(resolution_hours) AS n_valid,
       ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY resolution_hours)::numeric, 2) AS median_h,
       ROUND(AVG(resolution_hours)::numeric, 2) AS mean_h
FROM service_requests
WHERE resolution_hours IS NOT NULL
GROUP BY agency
HAVING COUNT(resolution_hours) >= 100
ORDER BY median_h DESC;

WITH q AS (
    SELECT percentile_cont(0.25) WITHIN GROUP (ORDER BY resolution_hours) AS q1,
           percentile_cont(0.75) WITHIN GROUP (ORDER BY resolution_hours) AS q3
    FROM service_requests
    WHERE resolution_hours IS NOT NULL
)
SELECT ROUND(q.q1::numeric, 2)                        AS q1_h,
       ROUND(q.q3::numeric, 2)                        AS q3_h,
       ROUND((q.q3 - q.q1)::numeric, 2)               AS iqr_h,
       ROUND((q.q1 - 1.5 * (q.q3 - q.q1))::numeric, 2) AS lower_fence_h,
       ROUND((q.q3 + 1.5 * (q.q3 - q.q1))::numeric, 2) AS upper_fence_h,
       COUNT(*) FILTER (WHERE s.resolution_hours > q.q3 + 1.5 * (q.q3 - q.q1)) AS high_outliers,
       COUNT(*) FILTER (WHERE s.resolution_hours < q.q1 - 1.5 * (q.q3 - q.q1)) AS low_outliers,
       COUNT(*)                                        AS n_valid
FROM service_requests s, q
WHERE s.resolution_hours IS NOT NULL
GROUP BY q.q1, q.q3;

WITH q AS (
    SELECT percentile_cont(0.25) WITHIN GROUP (ORDER BY resolution_hours) AS q1,
           percentile_cont(0.75) WITHIN GROUP (ORDER BY resolution_hours) AS q3
    FROM service_requests
    WHERE resolution_hours IS NOT NULL
)
SELECT s.agency,
       COUNT(*) AS n_valid,
       COUNT(*) FILTER (WHERE s.resolution_hours > q.q3 + 1.5 * (q.q3 - q.q1)) AS high_outliers,
       ROUND(100.0 * COUNT(*) FILTER (WHERE s.resolution_hours > q.q3 + 1.5 * (q.q3 - q.q1)) / COUNT(*), 1) AS pct_outliers
FROM service_requests s, q
WHERE s.resolution_hours IS NOT NULL
GROUP BY s.agency
HAVING COUNT(*) >= 200
ORDER BY high_outliers DESC;

WITH x AS (
    SELECT resolution_hours AS h FROM service_requests WHERE resolution_hours IS NOT NULL
), m AS (
    SELECT AVG(h) AS mean, STDDEV_POP(h) AS sd FROM x
)
SELECT ROUND((AVG(POWER(x.h - m.mean, 3)) / POWER(m.sd, 3))::numeric, 2) AS skewness,
       ROUND(m.mean::numeric, 2) AS mean_h,
       ROUND((SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY h) FROM x)::numeric, 2) AS median_h
FROM x, m
GROUP BY m.mean, m.sd;

SELECT CASE
           WHEN resolution_hours < 1    THEN '1) under 1 hour'
           WHEN resolution_hours < 4    THEN '2) 1 to 4 hours'
           WHEN resolution_hours < 24   THEN '3) 4 to 24 hours'
           WHEN resolution_hours < 72   THEN '4) 1 to 3 days'
           WHEN resolution_hours < 168  THEN '5) 3 to 7 days'
           WHEN resolution_hours < 720  THEN '6) 7 to 30 days'
           ELSE                              '7) over 30 days'
       END AS band,
       COUNT(*) AS requests,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM service_requests
WHERE resolution_hours IS NOT NULL
GROUP BY band
ORDER BY band;

SELECT borough,
       COUNT(*) AS requests,
       COUNT(*) FILTER (WHERE NOT flag_missing_coordinates) AS with_coordinates,
       ROUND(100.0 * COUNT(*) FILTER (WHERE NOT flag_missing_coordinates) / COUNT(*), 1) AS pct_with_coordinates
FROM service_requests
GROUP BY borough
ORDER BY requests DESC;

SELECT ROUND(latitude::numeric, 2)  AS lat_cell,
       ROUND(longitude::numeric, 2) AS lon_cell,
       COUNT(*) AS requests,
       MODE() WITHIN GROUP (ORDER BY borough) AS borough,
       MODE() WITHIN GROUP (ORDER BY complaint_type) AS top_complaint
FROM service_requests
WHERE NOT flag_missing_coordinates
GROUP BY lat_cell, lon_cell
ORDER BY requests DESC
LIMIT 15;

SELECT latitude, longitude,
       COUNT(*) AS requests,
       MODE() WITHIN GROUP (ORDER BY complaint_type) AS top_complaint,
       MODE() WITHIN GROUP (ORDER BY incident_address) AS address
FROM service_requests
WHERE NOT flag_missing_coordinates
GROUP BY latitude, longitude
ORDER BY requests DESC
LIMIT 5;

SELECT agency,
       COUNT(*) AS requests,
       SUM(is_closed) AS closed,
       ROUND(100.0 * SUM(is_closed) / COUNT(*), 2) AS closure_rate_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'Closed') / COUNT(*), 2) AS status_closed_pct
FROM service_requests
GROUP BY agency
HAVING COUNT(*) >= 500
ORDER BY closure_rate_pct;

SELECT borough,
       COUNT(*) AS requests,
       SUM(is_closed) AS closed,
       ROUND(100.0 * SUM(is_closed) / COUNT(*), 2) AS closure_rate_pct
FROM service_requests
GROUP BY borough
ORDER BY closure_rate_pct;

WITH per_type AS (
    SELECT complaint_type,
           COUNT(*) AS requests,
           COUNT(resolution_hours) AS n_valid,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY resolution_hours) AS median_h
    FROM service_requests
    GROUP BY complaint_type
    HAVING COUNT(resolution_hours) >= 100
), cuts AS (
    SELECT percentile_cont(0.75) WITHIN GROUP (ORDER BY requests) AS vol_cut,
           percentile_cont(0.75) WITHIN GROUP (ORDER BY median_h) AS med_cut
    FROM per_type
)
SELECT p.complaint_type,
       p.requests,
       p.n_valid,
       ROUND(p.median_h::numeric, 2) AS median_h,
       ROUND(c.vol_cut::numeric, 0)  AS volume_cut,
       ROUND(c.med_cut::numeric, 2)  AS median_cut_h,
       (p.requests >= c.vol_cut AND p.median_h >= c.med_cut) AS high_volume_and_slow
FROM per_type p, cuts c
ORDER BY high_volume_and_slow DESC, p.requests DESC;
