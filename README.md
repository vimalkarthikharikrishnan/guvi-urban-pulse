# Urban Pulse: NYC 311 complaint intelligence

An end-to-end analytics project on NYC 311 service requests: pull the data from the NYC Open Data API, clean it, check the statistics, store it in a database, answer 15 analyst questions in SQL and Python, and show the results in a Streamlit dashboard with five KPIs.

**Live dashboard:** https://urban-pulse-guvi.streamlit.app/

Data source: [311 Service Requests from 2020 to Present](https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9) (dataset `erm2-nwe9`).

> **Database note:** the project brief suggests MySQL. This version uses **PostgreSQL 18 running in Docker** (the database I had available). The schema and queries are standard SQL apart from a few PostgreSQL features (`percentile_cont`, `FILTER`, `MODE()`), which are what MySQL lacks.

## What is in here

```
src/extract.py        API extraction (paging, retries, resumable) -> data/raw/
src/clean.py          cleaning, derived fields, quality flags -> data/clean/
src/stats.py          descriptive statistics, skewness, IQR outliers, charts
src/load.py           staging table -> validation -> publish to PostgreSQL
src/db.py             database connection (reads .env)
src/test_connection.py  checks the connection and creates the database
sql/schema.sql        table definition and indexes
sql/analysis.sql      the 15 analyst queries
notebooks/eda.ipynb   the 15 tasks with charts and interpretation
app/                  Streamlit dashboard (overview + 4 analyst pages)
docs/                 data dictionary, cleaning log, extraction log, stats report, final report
```

## How to run it

Needs Python 3.12 and Docker.

**1. Database.** Start a PostgreSQL container (use your own password):

```bash
docker run --name postgres -e POSTGRES_PASSWORD=choose_a_password -e POSTGRES_DB=development \
  -p 5432:5432 -d postgres:18
```

**2. Python environment.**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # then put your password in .env (this file is never committed)
```

**3. Check the connection** (this also creates the `urban_pulse_db` database):

```bash
.venv/bin/python src/test_connection.py
```

**4. Run the pipeline in order:**

```bash
.venv/bin/python src/extract.py --year 2024   # ~100k rows, a few minutes, no API key needed
.venv/bin/python src/clean.py                 # writes data/clean/ + data dictionary + cleaning log
.venv/bin/python src/stats.py                 # statistics report and charts in docs/
.venv/bin/python src/load.py                  # loads and validates in PostgreSQL
```

`extract.py` saves each month in `data/raw/parts/`, so if it stops you can run it again and it continues. A free Socrata app token in `.env` (`SOCRATA_APP_TOKEN`) makes it faster but is not required.

**5. Notebook** (run it from inside the `notebooks` folder):

```bash
cd notebooks && ../.venv/bin/jupyter notebook eda.ipynb
```

**6. Dashboard:**

```bash
.venv/bin/streamlit run app/Overview.py
```

If the database cannot be reached, the dashboard shows a short message instead of crashing. A hosted free database sleeps when idle, so the first load can need a reload after about 10 seconds. The app tries each query twice before it gives up.

**Using a hosted database (for example Neon).** Put the host, user, password and database name your provider gives you in `.env` and add `PGSSLMODE=require`; `src/load.py` then loads the data the same way. The dashboard can be deployed on Streamlit Community Cloud with `app/Overview.py` as the main file. Enter the same settings in the app's **Secrets** box (TOML, values in quotes: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `PGSSLMODE`). Never write the password in the code, the README or the repo; `.env` and `.streamlit/secrets.toml` are git-ignored.

## Dataset and sampling

- Window: requests created 1 Jan to 31 Dec 2024. Extracted on 11 Nov 2026, so status and closed dates are as of that day.
- The year has about 3.46 million requests. We keep a systematic ~3% sample: rows whose `unique_key` ends in 03, 47 or 81. The ids are sequential, so the last digits are unrelated to time, agency or complaint type, and the sample covers every day and hour in proportion.
- Result: **103,841 rows**, 25 source fields, 0 duplicate keys. The brief says ~100,000 rows and to report the realised count.
- Details are in `docs/extraction_log.json`.

## The five KPIs

| KPI | Definition |
|---|---|
| Total requests | Distinct `unique_key` in the filtered data |
| Recorded closure | Share of filtered rows with a closed date |
| Open requests | Filtered rows without a closed date |
| Median resolution | Median hours from created to closed, valid cases only |
| Over 72 hours | Share of valid resolution times above 72 hours |

"Closed" only means a closed date is recorded. It does not mean the citizen was satisfied. The 72-hour line is our own cut-off, not an official service standard.

## Headline results (2024 sample)

- Most requests close quickly (median 8.2 hours), but the mean is 332.6 hours: the distribution is strongly right-skewed (skewness 6.7).
- NYPD receives 44.8% of requests, HPD 21.2%. Illegal Parking and Residential Noise are the top complaint types.
- The heavy and slow part of the workload is housing maintenance (doors/windows, water leaks, plumbing, unsanitary conditions).
- Several data-recording issues are documented (see the final report).

Full write-up: [`docs/final_report.md`](docs/final_report.md).

## Limitations

A 3% sample of one year, reported requests only, status as of the extraction date, closure is a recorded date and not verified resolution, and agencies handle different kinds of work, so comparisons are not performance rankings. More in the final report.

## Data files

`data/raw/` and `data/clean/` are not committed by default because of their size (about 47 MB and 55 MB). Run steps 4 to regenerate them, or ask the author for a copy.
