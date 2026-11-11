# Data dictionary

Cleaned table: 103,841 rows, 41 columns. Missingness is measured on the cleaned file. Source fields come from the NYC 311 API (`erm2-nwe9`); fields marked *derived* are created in `src/clean.py`.

| Field | Origin | Meaning | Type | Missing | Transformation | Analytical use |
|---|---|---|---|---|---|---|
| `unique_key` | source | Unique 311 request identifier | integer | 0 (0.0%) | Cast to integer | Primary key; distinct request count |
| `created_date` | source | When the request was created | datetime | 0 (0.0%) | Parsed to datetime | Time trends, weekday/hour demand, start of resolution time |
| `closed_date` | source | When the request was closed (blank if not closed) | datetime | 1,851 (1.8%) | Parsed to datetime; nulls kept | Closure indicator and resolution time |
| `due_date` | source | Date the agency planned to respond by (rarely filled) | datetime | 103,242 (99.4%) | Parsed to datetime; nulls kept | Not used in KPIs (almost entirely missing) |
| `agency` | source | Responsible agency code (e.g. NYPD, HPD) | text | 0 (0.0%) | Whitespace trimmed | Workload and resolution comparison by agency |
| `agency_name` | source | Full agency name | text | 0 (0.0%) | Whitespace trimmed | Labels for charts |
| `complaint_type` | source | Main complaint category | text | 0 (0.0%) | Whitespace trimmed; case variants merged | Top categories, resolution by category |
| `descriptor` | source | Sub-category detail of the complaint | text | 1,145 (1.1%) | Whitespace collapsed; case variants merged | Drill-down within a complaint type |
| `location_type` | source | Type of place where the problem occurred | text | 12,504 (12.0%) | Whitespace trimmed; nulls kept | Context for complaint patterns |
| `address_type` | source | How the location was recorded (ADDRESS, INTERSECTION ...) | text | 425 (0.4%) | Whitespace trimmed | Location data quality |
| `incident_zip` | source | ZIP code of the incident | text | 1,021 (1.0%) | Not 5 digits -> null and flagged | Local geographic summaries |
| `incident_address` | source | Street address of the incident | text | 3,684 (3.5%) | Whitespace collapsed | Not used in analysis (identifying detail) |
| `city` | source | City name as recorded | text | 4,745 (4.6%) | Upper-cased; whitespace trimmed | Secondary location label |
| `borough` | source | NYC borough (BROOKLYN, QUEENS, BRONX, MANHATTAN, STATEN ISLAND, UNSPECIFIED) | text | 0 (0.0%) | Upper-cased | Borough volume, filters, geographic summary |
| `status` | source | Recorded request status | text | 0 (0.0%) | Whitespace trimmed | Status distribution, closure rate |
| `resolution_description` | source | Agency's text explanation of the outcome | text | 787 (0.8%) | Whitespace collapsed | Reference only; not used in KPIs |
| `resolution_action_updated_date` | source | Last time the agency updated the resolution | datetime | 374 (0.4%) | Parsed to datetime | Reference only |
| `community_board` | source | Community board of the incident | text | 0 (0.0%) | Whitespace trimmed | Optional local grouping |
| `council_district` | source | City council district number | integer | 2,061 (2.0%) | Cast to nullable integer | Optional local grouping |
| `police_precinct` | source | Police precinct label | text | 0 (0.0%) | Whitespace trimmed | Optional local grouping |
| `open_data_channel_type` | source | How the request was submitted (ONLINE, PHONE, MOBILE ...) | text | 0 (0.0%) | Whitespace trimmed | Channel mix |
| `x_coordinate_state_plane` | source | NY State Plane X coordinate | integer | 1,525 (1.5%) | Numeric conversion | Not used (latitude/longitude used instead) |
| `y_coordinate_state_plane` | source | NY State Plane Y coordinate | integer | 1,521 (1.5%) | Numeric conversion | Not used (latitude/longitude used instead) |
| `latitude` | source | Latitude of the incident | float | 1,526 (1.5%) | Numeric conversion; nulls kept | Maps and geographic concentration |
| `longitude` | source | Longitude of the incident | float | 1,526 (1.5%) | Numeric conversion; nulls kept | Maps and geographic concentration |
| `flag_closed_before_created` | derived | Derived flag: closed date earlier than created date | boolean flag | 0 (0.0%) | closed_date < created_date | Excludes the row from resolution statistics |
| `flag_future_date` | derived | Derived flag: a date after the extraction date | boolean flag | 0 (0.0%) | Compared with extraction timestamp | Excludes the row from resolution statistics |
| `flag_status_closed_no_closed_date` | derived | Derived flag: status Closed but no closed date | text | 0 (0.0%) | status == Closed and closed_date null | Explains closure-rate gaps |
| `flag_closed_date_status_not_closed` | derived | Derived flag: has a closed date but status is not Closed | text | 0 (0.0%) | closed_date present and status != Closed | Explains closure-rate gaps |
| `flag_invalid_zip` | derived | Derived flag: ZIP was not a 5-digit value | text | 0 (0.0%) | Original value replaced by null | Data-quality reporting |
| `flag_missing_coordinates` | derived | Derived flag: latitude or longitude missing | boolean flag | 0 (0.0%) | Null check | Geography coverage |
| `flag_coordinates_outside_nyc` | derived | Derived flag: coordinates outside the NYC bounding box | text | 0 (0.0%) | Bounding box 40.4-41.0 N, -74.3 to -73.6 E | Data-quality reporting |
| `is_closed` | derived | 1 if a closed date is recorded, else 0 | integer | 0 (0.0%) | closed_date notna | Recorded closure KPI, open requests KPI |
| `resolution_hours` | derived | Hours from created to closed (valid closed records only) | float | 1,876 (1.8%) | (closed - created) in hours; null if invalid | Median resolution KPI, outliers, skewness |
| `is_over_72h` | derived | 1 if resolution_hours > 72 (project-defined cut-off) | integer | 1,876 (1.8%) | Null when resolution_hours is null | Over-72-hours KPI |
| `created_year` | derived | Year of creation | integer | 0 (0.0%) | From created_date | Trend grouping |
| `created_month` | derived | Month number of creation (1-12) | integer | 0 (0.0%) | From created_date | Seasonality |
| `created_year_month` | derived | Year-month label, e.g. 2024-03 | text | 0 (0.0%) | From created_date | Monthly trend |
| `created_weekday` | derived | Day name of creation | text | 0 (0.0%) | From created_date | Weekday demand |
| `created_weekday_num` | derived | Weekday number, Monday=0 .. Sunday=6 | integer | 0 (0.0%) | From created_date | Sorting weekdays |
| `created_hour` | derived | Hour of creation (0-23) | integer | 0 (0.0%) | From created_date | Hourly demand |

Do not assume every field is populated: `due_date` is almost always empty and `location_type` is missing for about 12% of rows.
