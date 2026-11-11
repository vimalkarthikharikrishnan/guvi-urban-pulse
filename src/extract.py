"""Step 2: extract NYC 311 records from the NYC Open Data (Socrata) API.

Sampling design (documented in docs/extraction_log.json):
  * Window: one calendar year (default 2024), requested month by month.
  * The full year has ~3.46M rows, so we keep a systematic ~3% sample: rows whose
    unique_key ends in one of SUFFIXES (last two digits). unique_key is an
    auto-increment id, so its last digits are unrelated to time, agency or complaint
    type; the sample therefore spreads across every day and hour in proportion to demand.
  * Each month is paged with $order=created_date,unique_key (deterministic, no
    duplicate/missed rows between pages) and saved to data/raw/parts/ so a re-run resumes.

Usage:  python src/extract.py [--year 2024]
"""
import argparse
import calendar
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PARTS_DIR = RAW_DIR / "parts"
LOG_PATH = ROOT / "docs" / "extraction_log.json"

# ~25 source fields, verified against the live schema (api/views/erm2-nwe9.json).
FIELDS = [
    "unique_key", "created_date", "closed_date", "due_date",
    "agency", "agency_name", "complaint_type", "descriptor",
    "location_type", "address_type", "incident_zip", "incident_address", "city", "borough",
    "status", "resolution_description", "resolution_action_updated_date",
    "community_board", "council_district", "police_precinct", "open_data_channel_type",
    "x_coordinate_state_plane", "y_coordinate_state_plane", "latitude", "longitude",
]
SUFFIXES = ["03", "47", "81"]  # ~3 of 100 id endings => ~3% of rows
PAGE_SIZE = 5000
TIMEOUT = 120
MAX_RETRIES = 6


def get_page(session: requests.Session, params: dict) -> list[dict]:
    """GET one page with timeout and exponential-backoff retries."""
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(BASE_URL, params=params, timeout=TIMEOUT)
            if resp.status_code == 200:
                return resp.json()
            last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except requests.RequestException as exc:
            last_err = f"{type(exc).__name__}: {exc}"
        wait = min(2 ** attempt, 60)
        print(f"    retry {attempt}/{MAX_RETRIES} in {wait}s ({last_err})", flush=True)
        time.sleep(wait)
    raise RuntimeError(f"API request failed after {MAX_RETRIES} attempts: {last_err}")


def extract_month(session: requests.Session, year: int, month: int) -> pd.DataFrame:
    start = f"{year}-{month:02d}-01T00:00:00"
    nxt_y, nxt_m = (year + 1, 1) if month == 12 else (year, month + 1)
    end = f"{nxt_y}-{nxt_m:02d}-01T00:00:00"
    like = " OR ".join(f"unique_key like '%{s}'" for s in SUFFIXES)
    where = f"created_date >= '{start}' AND created_date < '{end}' AND ({like})"
    rows, offset = [], 0
    while True:
        page = get_page(session, {
            "$select": ",".join(FIELDS),
            "$where": where,
            "$order": "created_date,unique_key",
            "$limit": PAGE_SIZE,
            "$offset": offset,
        })
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    # Keep the raw values as returned (all strings); only enforce the column order.
    return pd.DataFrame(rows).reindex(columns=FIELDS).astype("string")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2024)
    args = parser.parse_args()
    year = args.year

    PARTS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    token = os.environ.get("SOCRATA_APP_TOKEN", "").strip()
    if token:
        session.headers["X-App-Token"] = token
    started = datetime.now(timezone.utc)

    month_counts, resumed = {}, []
    for month in range(1, 13):
        part = PARTS_DIR / f"{year}-{month:02d}.csv"
        if part.exists():
            df = pd.read_csv(part, dtype="string", keep_default_na=False)
            resumed.append(month)
            print(f"{year}-{month:02d}: reused existing part ({len(df):,} rows)", flush=True)
        else:
            t0 = time.time()
            df = extract_month(session, year, month)
            df.to_csv(part, index=False)
            print(f"{year}-{month:02d}: {len(df):,} rows in {time.time() - t0:.0f}s", flush=True)
        month_counts[f"{year}-{month:02d}"] = len(df)

    parts = [pd.read_csv(p, dtype="string", keep_default_na=False) for p in sorted(PARTS_DIR.glob(f"{year}-*.csv"))]
    raw = pd.concat(parts, ignore_index=True)
    dup_keys = int(raw["unique_key"].duplicated().sum())
    out_path = RAW_DIR / f"nyc311_raw_{year}.csv"
    raw.to_csv(out_path, index=False)

    created = pd.to_datetime(raw["created_date"], errors="coerce")
    log = {
        "extraction_started_utc": started.isoformat(timespec="seconds"),
        "extraction_finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "NYC Open Data 311 Service Requests from 2020 to Present (erm2-nwe9)",
        "endpoint": BASE_URL,
        "window": {"from": f"{year}-01-01", "to": f"{year}-12-31"},
        "sampling": {
            "method": "systematic: unique_key ending in one of the listed 2-digit suffixes",
            "suffixes": SUFFIXES,
            "approx_fraction_of_population": f"{len(SUFFIXES)}%",
            "ordering": "created_date, unique_key",
            "note": "Re-runs resume from data/raw/parts/; delete that folder to re-extract.",
        },
        "page_size": PAGE_SIZE,
        "timeout_seconds": TIMEOUT,
        "max_retries": MAX_RETRIES,
        "app_token_used": bool(token),
        "fields": FIELDS,
        "rows_per_month": month_counts,
        "months_reused_from_previous_run": resumed,
        "actual_row_count": int(len(raw)),
        "duplicate_unique_keys": dup_keys,
        "created_date_min": str(created.min()),
        "created_date_max": str(created.max()),
        "output_file": str(out_path.relative_to(ROOT)),
        "limitations": [
            "Sample (~3%) of the year, not the full population; the exact count depends on API data at extraction time.",
            "Dataset is updated daily; records can be re-opened/closed after extraction, so closed_date and status are as of the extraction date.",
            "Raw values are kept exactly as returned (all text); typing and cleaning happen in the cleaning step.",
        ],
    }
    LOG_PATH.write_text(json.dumps(log, indent=2))
    print(f"\nDone: {len(raw):,} rows -> {out_path.relative_to(ROOT)}")
    print(f"Window: {log['created_date_min']} .. {log['created_date_max']}; duplicate keys: {dup_keys}")
    print(f"Log: {LOG_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.exit(f"Extraction failed: {exc}")
