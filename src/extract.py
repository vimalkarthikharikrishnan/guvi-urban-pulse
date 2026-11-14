import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
YEAR = 2024
ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PARTS_DIR = RAW_DIR / "parts"
LOG_PATH = ROOT / "docs" / "extraction_log.json"

FIELDS = [
    "unique_key", "created_date", "closed_date", "due_date",
    "agency", "agency_name", "complaint_type", "descriptor",
    "location_type", "address_type", "incident_zip", "incident_address", "city", "borough",
    "status", "resolution_description", "resolution_action_updated_date",
    "community_board", "council_district", "police_precinct", "open_data_channel_type",
    "x_coordinate_state_plane", "y_coordinate_state_plane", "latitude", "longitude",
]

SUFFIXES = ["03", "47", "81"]
PAGE_SIZE = 5000
TIMEOUT = 120


def get_page(session, params):
    resp = session.get(URL, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def make_where(year, month):
    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1
    start = f"{year}-{month:02d}-01T00:00:00"
    end = f"{next_year}-{next_month:02d}-01T00:00:00"

    endings = []
    for suffix in SUFFIXES:
        endings.append(f"unique_key like '%{suffix}'")
    return f"created_date >= '{start}' AND created_date < '{end}' AND (" + " OR ".join(endings) + ")"


def extract_month(session, year, month):
    where = make_where(year, month)
    rows = []
    offset = 0
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

    return pd.DataFrame(rows).reindex(columns=FIELDS).astype("string")


def read_part(path):
    return pd.read_csv(path, dtype="string", keep_default_na=False)


def download_all_months(session, year):
    month_counts = {}
    reused = []
    for month in range(1, 13):
        name = f"{year}-{month:02d}"
        part = PARTS_DIR / f"{name}.csv"
        if part.exists():
            df = read_part(part)
            reused.append(month)
            print(f"{name}: reused existing part ({len(df):,} rows)", flush=True)
        else:
            t0 = time.time()
            df = extract_month(session, year, month)
            df.to_csv(part, index=False)
            print(f"{name}: {len(df):,} rows in {time.time() - t0:.0f}s", flush=True)
        month_counts[name] = len(df)
    return month_counts, reused


def main():
    year = YEAR

    PARTS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    token = os.environ.get("SOCRATA_APP_TOKEN", "").strip()
    if token:
        session.headers["X-App-Token"] = token
    started = datetime.now(timezone.utc)

    month_counts, reused = download_all_months(session, year)

    parts = []
    for path in sorted(PARTS_DIR.glob(f"{year}-*.csv")):
        parts.append(read_part(path))
    raw = pd.concat(parts, ignore_index=True)
    dup_keys = int(raw["unique_key"].duplicated().sum())
    out_path = RAW_DIR / f"nyc311_raw_{year}.csv"
    raw.to_csv(out_path, index=False)

    created = pd.to_datetime(raw["created_date"], errors="coerce")
    log = {
        "extraction_started_utc": started.isoformat(timespec="seconds"),
        "extraction_finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "NYC Open Data 311 Service Requests from 2020 to Present (erm2-nwe9)",
        "endpoint": URL,
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
        "app_token_used": bool(token),
        "fields": FIELDS,
        "rows_per_month": month_counts,
        "months_reused_from_previous_run": reused,
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
    main()
