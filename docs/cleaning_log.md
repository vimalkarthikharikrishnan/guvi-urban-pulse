# Cleaning and validation log

Input: `data/raw/nyc311_raw_2024.csv` (103,841 rows, extracted 2026-11-11T04:09:38+00:00 UTC).
Output: `data/clean/nyc311_clean_2024.csv` (103,841 rows, 41 columns).

Principles: raw data is never edited; nulls are preserved; impossible or implausible values are flagged, not corrected; no rows are dropped except exact duplicate keys.

## Steps

| # | Step | Detail | Affected |
|---|---|---|---|
| 1 | Trim and collapse repeated whitespace in text fields | {"descriptor": 45, "incident_address": 19614, "resolution_description": 9025} | 28,684 |
| 2 | Empty strings converted to proper nulls (values not imputed) | all columns |  |
| 3 | Harmonised label case (complaint_type/descriptor -> most common spelling; city/borough -> UPPER) | {"complaint_type": 139, "descriptor": 5, "city": 12, "borough": 88} | 244 |
| 4 | Parsed dates / coordinates / numeric ids safely (errors become null) | {"unparseable_dates": {"created_date": 0, "closed_date": 0, "due_date": 0, "resolution_action_updated_date": 0}} |  |
| 5 | Checked duplicate unique_key (duplicates dropped, first kept) | 0 duplicates found | 0 |
| 6 | Quality flags added (original values kept) | {"flag_closed_before_created": 25, "flag_future_date": 0, "flag_status_closed_no_closed_date": 805, "flag_closed_date_status_not_closed": 81, "flag_invalid_zip": 1, "flag_missing_coordinates": 1526, "flag_coordinates_outside_nyc": 0} |  |
| 7 | Invalid ZIP values set to null and flagged | incident_zip not 5 digits | 1 |
| 8 | Derived fields added | ["is_closed", "resolution_hours (valid closed records only)", "is_over_72h", "created_year", "created_month", "created_year_month", "created_weekday", "created_weekday_num", "created_hour"] |  |

## Validation

| Check | Result |
|---|---|
| Raw rows -> cleaned rows | 103,841 -> 103,841 (removed 0) |
| `unique_key` unique | 103,841 distinct of 103,841 |
| created_date range | 2024-01-01 00:01:26 to 2024-12-31 23:56:59 |
| Latitude / longitude range | 40.4997..40.9122 / -74.2532..-73.7007 |
| resolution_hours range (valid only) | 0.00 to 24,242.76 hours |
| Re-read of cleaned file | csv re-read: row count and unique_key match |

## resolution_hours coverage

Valid values: 101,965. Excluded: 1,851 with no closed date, 25 with closed date before created date (flagged, not corrected), 0 with a date after the extraction date.

Zero-hour resolutions (closed at the creation minute) are kept: they are plausible instant closures, not errors.
Rows with status = Closed but no closed date, or a closed date but a non-Closed status, are flagged; `is_closed` follows the project definition (a recorded closed date).
Long resolutions (several months) are kept; IQR outliers are investigated in Step 4, not deleted.
