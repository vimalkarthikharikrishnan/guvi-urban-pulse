-- Urban Pulse: the 15 analyst tasks (PostgreSQL)
-- Every query starts with "-- name: <id>" so the notebook can find it.
-- "valid resolution" = resolution_hours IS NOT NULL (closed date present and not before created date).


-- name: t01_total_volume
-- Task 1: total distinct request volume
SELECT COUNT(DISTINCT unique_key) AS distinct_requests,
       COUNT(*)                   AS rows_in_table
FROM service_requests;


-- name: t02_top_complaints
-- Task 2: top 10 complaint categories by count
SELECT complaint_type,
       COUNT(*) AS requests,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_all
FROM service_requests
GROUP BY complaint_type
ORDER BY requests DESC
LIMIT 10;


-- name: t03_agency_workload
-- Task 3: agency workload distribution
SELECT agency,
       MAX(agency_name) AS agency_name,
       COUNT(*) AS requests,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_all
FROM service_requests
GROUP BY agency
ORDER BY requests DESC;


-- name: t04_borough_volume
-- Task 4: request volume by borough
SELECT borough,
       COUNT(*) AS requests,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_all
FROM service_requests
GROUP BY borough
ORDER BY requests DESC;


-- name: t05_monthly_trend
-- Task 5: monthly request trend
SELECT created_year_month AS month,
       COUNT(*) AS requests
FROM service_requests
GROUP BY created_year_month
ORDER BY created_year_month;


-- name: t06_weekday_hour
-- Task 6: demand by weekday and hour (weekday_num: Monday = 0)
SELECT created_weekday_num AS weekday_num,
       created_weekday     AS weekday,
       created_hour        AS hour,
       COUNT(*)            AS requests
FROM service_requests
GROUP BY created_weekday_num, created_weekday, created_hour
ORDER BY weekday_num, hour;


-- name: t07_status
-- Task 7: distribution of recorded request statuses
SELECT status,
       COUNT(*) AS requests,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_all
FROM service_requests
GROUP BY status
ORDER BY requests DESC;


-- name: t08_resolution_stats
-- Task 8: descriptive statistics for valid resolution durations (hours)
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


-- name: t09_median_by_complaint
-- Task 9: median resolution duration by complaint category (at least 100 valid cases)
SELECT complaint_type,
       COUNT(resolution_hours) AS n_valid,
       ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY resolution_hours)::numeric, 2) AS median_h,
       ROUND(AVG(resolution_hours)::numeric, 2) AS mean_h
FROM service_requests
WHERE resolution_hours IS NOT NULL
GROUP BY complaint_type
HAVING COUNT(resolution_hours) >= 100
ORDER BY median_h DESC;


-- name: t10_median_by_agency
-- Task 10: median resolution duration by agency (at least 100 valid cases)
SELECT agency,
       COUNT(resolution_hours) AS n_valid,
       ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY resolution_hours)::numeric, 2) AS median_h,
       ROUND(AVG(resolution_hours)::numeric, 2) AS mean_h
FROM service_requests
WHERE resolution_hours IS NOT NULL
GROUP BY agency
HAVING COUNT(resolution_hours) >= 100
ORDER BY median_h DESC;


-- name: t11_outlier_fences
-- Task 11: IQR outlier investigation, part 1: the fences and the counts
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


-- name: t11_outliers_by_agency
-- Task 11, part 2: which agencies the high outliers come from
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


-- name: t12_skewness
-- Task 12, part 1: skewness (moment formula, sample size n) and mean vs median
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


-- name: t12_distribution
-- Task 12, part 2: distribution in time bands
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


-- name: t13_geo_by_borough
-- Task 13, part 1: how many requests have usable coordinates, by borough
SELECT borough,
       COUNT(*) AS requests,
       COUNT(*) FILTER (WHERE NOT flag_missing_coordinates) AS with_coordinates,
       ROUND(100.0 * COUNT(*) FILTER (WHERE NOT flag_missing_coordinates) / COUNT(*), 1) AS pct_with_coordinates
FROM service_requests
GROUP BY borough
ORDER BY requests DESC;


-- name: t13_geo_hotspots
-- Task 13, part 2: busiest grid cells (coordinates rounded to 2 decimals, roughly 1 km)
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


-- name: t13_hotspot_exact
-- Task 13, part 3: check the busiest cell, are the requests spread out or at one exact point?
SELECT latitude, longitude,
       COUNT(*) AS requests,
       MODE() WITHIN GROUP (ORDER BY complaint_type) AS top_complaint,
       MODE() WITHIN GROUP (ORDER BY incident_address) AS address
FROM service_requests
WHERE NOT flag_missing_coordinates
GROUP BY latitude, longitude
ORDER BY requests DESC
LIMIT 5;


-- name: t14_closure_by_agency
-- Task 14, part 1: recorded closure rate by agency (at least 500 requests)
-- closure_rate_pct uses the recorded closed date (project definition); status_closed_pct uses the status text,
-- shown next to it because the two disagree for some agencies.
SELECT agency,
       COUNT(*) AS requests,
       SUM(is_closed) AS closed,
       ROUND(100.0 * SUM(is_closed) / COUNT(*), 2) AS closure_rate_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'Closed') / COUNT(*), 2) AS status_closed_pct
FROM service_requests
GROUP BY agency
HAVING COUNT(*) >= 500
ORDER BY closure_rate_pct;


-- name: t14_closure_by_borough
-- Task 14, part 2: recorded closure rate by borough
SELECT borough,
       COUNT(*) AS requests,
       SUM(is_closed) AS closed,
       ROUND(100.0 * SUM(is_closed) / COUNT(*), 2) AS closure_rate_pct
FROM service_requests
GROUP BY borough
ORDER BY closure_rate_pct;


-- name: t15_volume_vs_resolution
-- Task 15: complaint types with BOTH high volume and long median resolution.
-- "High" = at or above the 75th percentile across complaint types that have at least 100 valid cases.
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
