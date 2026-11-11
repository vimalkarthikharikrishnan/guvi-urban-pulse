import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import MetaData, text
from sqlalchemy.dialects.postgresql import insert

from db import get_engine

ROOT = Path(__file__).resolve().parent.parent
CLEAN_CSV = ROOT / "data" / "clean" / "nyc311_clean_2024.csv"
SCHEMA_SQL = ROOT / "sql" / "schema.sql"
BATCH_SIZE = 5000
RETRIES = 3

DATE_COLS = ["created_date", "closed_date", "due_date", "resolution_action_updated_date"]


def read_clean():
    df = pd.read_csv(CLEAN_CSV, parse_dates=DATE_COLS, dtype={"incident_zip": "string"})
    df["council_district"] = df["council_district"].astype("Int64")
    df["is_over_72h"] = df["is_over_72h"].astype("Int64")
    return df


def to_records(chunk):
    # pandas NaN / NaT / <NA> have to become None so postgres gets a real NULL
    chunk = chunk.astype(object).where(chunk.notna(), None)
    return chunk.to_dict("records")


def insert_batch(engine, table, rows):
    for attempt in range(1, RETRIES + 1):
        try:
            with engine.begin() as conn:   # one transaction per batch
                # many rows per INSERT, so a remote database (cloud) needs few round trips
                for i in range(0, len(rows), 1000):
                    conn.execute(insert(table).values(rows[i:i + 1000]).on_conflict_do_nothing(index_elements=["unique_key"]))
            return
        except Exception as e:
            print(f"  batch failed (try {attempt}/{RETRIES}): {type(e).__name__}")
            if attempt == RETRIES:
                raise
            time.sleep(2 * attempt)


def main():
    engine = get_engine()
    df = read_clean()
    print(f"read {len(df):,} rows from {CLEAN_CSV.name}")

    # 1. make sure the real table exists, then build an empty staging copy
    with engine.begin() as conn:
        conn.exec_driver_sql(SCHEMA_SQL.read_text())
        conn.execute(text("DROP TABLE IF EXISTS service_requests_staging"))
        conn.execute(text("CREATE TABLE service_requests_staging (LIKE service_requests INCLUDING ALL)"))

    meta = MetaData()
    meta.reflect(bind=engine, only=["service_requests_staging"])
    staging = meta.tables["service_requests_staging"]

    # 2. load into staging in batches
    for start in range(0, len(df), BATCH_SIZE):
        insert_batch(engine, staging, to_records(df.iloc[start:start + BATCH_SIZE]))
        print(f"  loaded {min(start + BATCH_SIZE, len(df)):,} / {len(df):,}")

    # 3. check the staging table before touching the real one
    with engine.connect() as conn:
        staged, distinct, null_res, min_d, max_d = conn.execute(text("""
            SELECT COUNT(*), COUNT(DISTINCT unique_key), COUNT(*) - COUNT(resolution_hours),
                   MIN(created_date), MAX(created_date)
            FROM service_requests_staging""")).one()
    problems = []
    if staged != len(df):
        problems.append(f"row count: csv {len(df)} vs staging {staged}")
    if distinct != staged:
        problems.append(f"duplicate keys in staging ({staged - distinct})")
    if null_res != df["resolution_hours"].isna().sum():
        problems.append("resolution_hours null count differs from csv")
    if pd.Timestamp(min_d) != df["created_date"].min() or pd.Timestamp(max_d) != df["created_date"].max():
        problems.append("created_date range differs from csv")
    if problems:
        sys.exit("Validation failed, real table not touched: " + "; ".join(problems))
    print(f"staging OK: {staged:,} rows, {distinct:,} distinct keys, {min_d} to {max_d}")

    # 4. publish in one transaction: either the new data is fully in, or nothing changes
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE service_requests"))
        conn.execute(text("INSERT INTO service_requests SELECT * FROM service_requests_staging"))
        conn.execute(text("DROP TABLE service_requests_staging"))
    print("published to service_requests")

    # 5. final check on the real table + a small random sample against the csv
    with engine.connect() as conn:
        final = conn.execute(text("SELECT COUNT(*) FROM service_requests")).scalar()
        sample = pd.read_sql(text("SELECT unique_key, status, borough, resolution_hours FROM service_requests "
                                  "ORDER BY random() LIMIT 5"), conn)
    print(f"source rows {len(df):,} | cleaned rows {len(df):,} | database rows {final:,}")
    if final != len(df):
        sys.exit("final count does not match the csv")

    csv_rows = df.set_index("unique_key")
    for _, r in sample.iterrows():
        c = csv_rows.loc[r["unique_key"]]
        same = (c["status"] == r["status"] and c["borough"] == r["borough"]
                and (pd.isna(c["resolution_hours"]) and pd.isna(r["resolution_hours"])
                     or abs(c["resolution_hours"] - r["resolution_hours"]) < 1e-6))
        print(f"  sample {r['unique_key']}: {'match' if same else 'MISMATCH'}")
        if not same:
            sys.exit("sample check failed")
    print("done")


if __name__ == "__main__":
    main()
