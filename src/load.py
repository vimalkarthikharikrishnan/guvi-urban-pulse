import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from db import get_engine

ROOT = Path(__file__).resolve().parent.parent
CLEAN_CSV = ROOT / "data" / "clean" / "nyc311_clean_2024.csv"
SCHEMA_SQL = ROOT / "sql" / "schema.sql"
BATCH_SIZE = 1000

DATE_COLS = ["created_date", "closed_date", "due_date", "resolution_action_updated_date"]


def read_clean():
    df = pd.read_csv(CLEAN_CSV, parse_dates=DATE_COLS, dtype={"incident_zip": "string"})
    df["council_district"] = df["council_district"].astype("Int64")
    df["is_over_72h"] = df["is_over_72h"].astype("Int64")
    return df


def create_staging(engine):
    with engine.begin() as conn:
        conn.exec_driver_sql(SCHEMA_SQL.read_text())
        conn.execute(text("DROP TABLE IF EXISTS service_requests_staging"))
        conn.execute(text("CREATE TABLE service_requests_staging (LIKE service_requests INCLUDING ALL)"))


def fill_staging(engine, df):
    df.to_sql("service_requests_staging", engine, if_exists="append", index=False,
              chunksize=BATCH_SIZE, method="multi")
    print(f"  loaded {len(df):,} rows")


def check_staging(engine, df):
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


def publish(engine):
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE service_requests"))
        conn.execute(text("INSERT INTO service_requests SELECT * FROM service_requests_staging"))
        conn.execute(text("DROP TABLE service_requests_staging"))
    print("published to service_requests")


def same_hours(a, b):
    if pd.isna(a) and pd.isna(b):
        return True
    if pd.isna(a) or pd.isna(b):
        return False
    return abs(a - b) < 1e-6


def check_final(engine, df):
    with engine.connect() as conn:
        final = conn.execute(text("SELECT COUNT(*) FROM service_requests")).scalar()
        sample = pd.read_sql(text("SELECT unique_key, status, borough, resolution_hours FROM service_requests "
                                  "ORDER BY random() LIMIT 5"), conn)
    print(f"csv rows {len(df):,} | database rows {final:,}")
    if final != len(df):
        sys.exit("final count does not match the csv")

    csv_rows = df.set_index("unique_key")
    for _, r in sample.iterrows():
        c = csv_rows.loc[r["unique_key"]]
        same = (c["status"] == r["status"] and c["borough"] == r["borough"]
                and same_hours(c["resolution_hours"], r["resolution_hours"]))
        print(f"  sample {r['unique_key']}: {'match' if same else 'MISMATCH'}")
        if not same:
            sys.exit("sample check failed")


def main():
    engine = get_engine()
    df = read_clean()
    print(f"read {len(df):,} rows from {CLEAN_CSV.name}")

    create_staging(engine)
    fill_staging(engine, df)
    check_staging(engine, df)
    publish(engine)
    check_final(engine, df)
    print("done")


if __name__ == "__main__":
    main()
