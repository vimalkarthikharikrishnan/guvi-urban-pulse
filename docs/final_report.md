# Urban Pulse: final report

NYC 311 complaint intelligence, 2024 sample. Prepared from the project pipeline in this repository.

## 1. What we did

We built a workflow from API to dashboard:

1. Pulled NYC 311 requests created in 2024 through the NYC Open Data API (`erm2-nwe9`).
2. Cleaned them and added derived fields, flagging doubtful values instead of correcting them.
3. Checked distributions, skewness and outliers.
4. Loaded them into PostgreSQL with a staging table and count checks.
5. Answered 15 analyst questions in SQL and Python.
6. Built a Streamlit dashboard with filters and five KPIs.

**Deviation from the brief:** the brief suggests MySQL. We used PostgreSQL 18 in Docker because that is the database available to the author. The data model and workflow are the same; median queries use `percentile_cont`.

## 2. Data

| Item | Value |
|---|---|
| Source | NYC Open Data, 311 Service Requests from 2020 to Present |
| Window | Requests created 1 Jan to 31 Dec 2024 |
| Extraction date | 11 Nov 2026 |
| Population in window | about 3.46 million requests (API count) |
| Sample | systematic ~3%: `unique_key` ends in 03, 47 or 81 |
| Realised rows | 103,841 (the brief's 100,000 target is approximate) |
| Fields | 25 source fields chosen from 48 in the live schema |

The sample spreads across all days and hours in proportion to demand (rows per month 7,230 to 9,410). Counts in this report are roughly one thirty-third of the real citywide totals. We first tried a random sort by the API's internal id, but it timed out on a year of data, and sorting by date would have kept only the start of each month, so we used the id-ending rule.

## 3. Data quality

Every step is in `docs/cleaning_log.md`; every field is in `docs/data_dictionary.md`.

| Check | Result |
|---|---|
| Row counts | raw 103,841 = cleaned 103,841 = database 103,841 |
| Duplicate `unique_key` | 0 |
| Unparseable dates | 0 |
| Whitespace fixes | 28,684 cells (mainly addresses and resolution text) |
| Label case merged | 139 complaint types, 88 boroughs, 12 cities, 5 descriptors |
| Invalid ZIP | 1 (`NA`), set to null and flagged |
| Missing coordinates | 1,526 rows (1.5%) |
| `due_date` missing | 99.4% (not used in analysis) |
| Closed date before created date | 25 rows, flagged and excluded from resolution time |
| Status "Closed" but no closed date | 805 rows |
| Closed date but status not "Closed" | 81 rows |

`resolution_hours` is calculated only when the closed date exists and is not before the created date: 101,965 valid values. Nothing was deleted or silently corrected.

## 4. Statistics: spread, skewness, outliers

Details and charts: `docs/stats_report.md`.

| Measure (hours) | Value |
|---|---|
| Mean | 332.6 |
| Median | 8.2 |
| Q1 / Q3 | 0.99 / 82.7 |
| 95th percentile | 1,712 (about 71 days) |
| Maximum | 24,243 (about 2.8 years) |
| Standard deviation | 1,256.8 |
| Skewness | 6.70 (0.74 after log transform) |

- The mean is about 40 times the median, so a few very long cases pull the average up. The dashboard therefore uses the median.
- The log histogram has two humps: quick closures (under about 4 hours) and a smaller group around 1 to 3 days.
- IQR rule: upper fence 205.3 hours (8.6 days), 17,001 requests (16.7%) above it, none below (the lower fence is negative). These are prompts for investigation, not rows to delete. Most come from work that normally takes weeks, such as repairs, inspections and permits.

## 5. Findings from the 15 analyst tasks

Full queries, charts and interpretations are in `sql/analysis.sql` and `notebooks/eda.ipynb`.

| # | Task | Result |
|---|---|---|
| 1 | Distinct volume | 103,841 requests |
| 2 | Top complaints | Illegal Parking 14.7%, Residential Noise 11.0%, HEAT/HOT WATER 7.7%; top 10 are about 54% |
| 3 | Agency workload | NYPD 44.8%, HPD 21.2%, DSNY 8.9%; the three hold about three quarters |
| 4 | Borough volume | Brooklyn 30.3%, Queens 23.9%, Bronx 21.5%, Manhattan 20.7%, Staten Island 3.5% |
| 5 | Monthly trend | 7,230 (Feb, a shorter month) to 9,410 (Dec); June to December stays around 8,600 to 9,400 |
| 6 | Weekday and hour | Monday busiest (16,274), Saturday quietest (13,123); peak at 11:00, low at 3 to 4 am |
| 7 | Status | 98.9% Closed |
| 8 | Resolution statistics | Median 8.2 h, mean 332.6 h |
| 9 | Median by complaint | Slowest: New Tree Request (8,089 h, about 11 months). Fast: police-type complaints |
| 10 | Median by agency | TLC 1,726 h, EDC 862 h, DPR 667 h; NYPD 1.05 h; HPD 93.6 h |
| 11 | IQR outliers | 16.7% above 205.3 h; highest share at EDC (96%), TLC (80%), DPR (62%) |
| 12 | Skewness | 6.7; 25.1% under 1 hour, 73.2% within 3 days, 8.7% over 30 days |
| 13 | Geography | 98.5% have coordinates; busy areas are northern Manhattan, the Bronx and parts of Brooklyn |
| 14 | Closure rate | NYPD and DOB 100%; DHS 46.7%; by borough 96.4% (Manhattan) to 99.4% (Bronx) |
| 15 | High volume and slow | DOOR/WINDOW and WATER LEAK; UNSANITARY CONDITION and PLUMBING are close behind |

## 6. Dashboard and KPIs

The dashboard is live at https://urban-pulse-guvi.streamlit.app/ (hosted on Streamlit Community Cloud, data in a hosted PostgreSQL database). It has date, borough and complaint-type filters, an overview page, four analyst pages, a filtered record preview, an empty-state message and a database-error message. All queries are parameterized and credentials come from `.env` locally and from Streamlit Secrets when hosted.

| KPI | All data |
|---|---|
| Total requests | 103,841 |
| Recorded closure | 98.2% |
| Open requests | 1,851 |
| Median resolution | 8.2 h |
| Over 72 hours | 26.8% |

KPI values were compared with direct SQL for the full data, Brooklyn only and February only, and matched.

## 7. Possible operational implications

These are patterns in recorded data, so treat them as questions to ask, not conclusions.

- **Staffing.** Requests are created mostly Monday to Friday between about 8 am and 4 pm, with Monday the busiest. Intake and triage coverage could follow that shape.
- **Housing maintenance.** HPD handles 21% of requests and the common housing types (doors/windows, water leaks, plumbing, unsanitary conditions) have medians from about 1.5 days (heat and hot water) to 11 days (doors and windows), with many cases far longer. These are the best candidates for process attention because they are both frequent and slow.
- **Planning around skew.** Report the median and the share over a threshold, not the average, which a few extreme cases distort.
- **Licensing and permits.** Categories such as New Tree Request, Mobile Food Vendor and Food Establishment are slow by nature. Setting expectations for citizens may help more than speeding them up.

## 8. Data-recording issues to raise with the data owner

- **DHS:** all 1,511 requests have status Closed but only 706 have a closed date, so the recorded closure rate (46.7%) reflects missing dates, not open work.
- **Closed without a date:** 805 requests overall have status Closed and no closed date.
- **Rodent:** 680 requests have a closed date equal to the created date, giving a median of 0 hours. This may be how inspection requests are recorded.
- **One map point:** 1,701 requests share a single coordinate (655 East 230 Street, Bronx), 1,680 of them Noise - Residential. This looks like a default location, not real concentration. We have not confirmed it.
- **Midnight bump:** more requests are created in the midnight hour than at 1 to 5 am. We have not checked whether some come with default timestamps.

## 9. Limitations

- A ~3% sample of one year, not the whole city or a multi-year trend. One year cannot show seasonality.
- 311 records are reported requests, not the full amount of urban problems.
- Status and closed dates are as of 11 Nov 2026. Requests can be updated or reopened later.
- Recorded closure is a date in the system. It is not satisfaction, quality or verified resolution.
- Agencies and complaint types differ in complexity and operating rules, so comparisons are not performance rankings.
- Counts are raw and not adjusted for population or area.
- The 72-hour threshold is a project choice, not an official standard.
- Some fields (due date, location type) are mostly empty and were not used.

## 10. Reproducibility

See `README.md` for the run order. The extraction method, parameters and row counts are logged in `docs/extraction_log.json`. Running `extract.py` again may return slightly different rows if the source data was updated.

## Appendix: deliverables checklist

| Deliverable in the brief | Where |
|---|---|
| API extraction and loading script | `src/extract.py`, `src/load.py` |
| Raw and cleaned data files | `data/raw/nyc311_raw_2024.csv`, `data/clean/nyc311_clean_2024.csv` (not committed by default, see README) |
| Data dictionary and cleaning/validation log | `docs/data_dictionary.md`, `docs/cleaning_log.md` |
| Database schema and loading instructions | `sql/schema.sql`, `README.md`, `src/load.py` |
| SQL queries and Python EDA for the 15 tasks | `sql/analysis.sql`, `notebooks/eda.ipynb` |
| Streamlit app and run instructions | `app/`, `README.md`; live app: https://urban-pulse-guvi.streamlit.app/ |
| Final documentation and findings | this report, `README.md`, `docs/stats_report.md` |
