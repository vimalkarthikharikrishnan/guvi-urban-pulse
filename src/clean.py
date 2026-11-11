"""Step 3: clean the raw NYC 311 extract, add derived fields and quality flags.

Rules (from the project document):
  * raw data is never modified; output goes to data/clean/
  * meaningful nulls are preserved (no imputing)
  * impossible / implausible values are FLAGGED, not silently corrected or deleted
  * resolution_hours is derived only when creation and closure timestamps are valid
Outputs: data/clean/nyc311_clean_<year>.csv, docs/cleaning_log.json, docs/cleaning_log.md,
         docs/data_dictionary.md

Usage:  python src/clean.py [--year 2024]
"""
import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

TEXT_COLS = [
    "agency", "agency_name", "complaint_type", "descriptor", "location_type", "address_type",
    "incident_zip", "incident_address", "city", "borough", "status", "resolution_description",
    "community_board", "police_precinct", "open_data_channel_type",
]
DATE_COLS = ["created_date", "closed_date", "due_date", "resolution_action_updated_date"]
FLOAT_COLS = ["latitude", "longitude", "x_coordinate_state_plane", "y_coordinate_state_plane"]
NYC_LAT, NYC_LON = (40.4, 41.0), (-74.3, -73.6)  # generous bounding box around the five boroughs
THRESHOLD_HOURS = 72  # project-defined illustrative cut-off (not an official SLA)


def main(year: int) -> None:
    raw_path = ROOT / "data" / "raw" / f"nyc311_raw_{year}.csv"
    extraction = json.loads((DOCS / "extraction_log.json").read_text())
    extraction_date = pd.Timestamp(extraction["extraction_finished_utc"]).tz_localize(None)

    raw = pd.read_csv(raw_path, dtype="string", keep_default_na=False)
    df = raw.copy()
    log = {"input_file": str(raw_path.relative_to(ROOT)), "raw_rows": int(len(raw)), "steps": []}

    def record(step, detail, n=None):
        log["steps"].append({"step": step, "detail": detail, "rows_or_cells_affected": None if n is None else int(n)})

    # ---- 1. whitespace + empty -> null (nulls are kept, never filled) --------------------
    ws_changed = {}
    for col in TEXT_COLS:
        before = df[col]
        after = before.str.replace(r"\s+", " ", regex=True).str.strip()
        ws_changed[col] = int(((before != after) & before.notna()).sum())
        df[col] = after
    ws_changed = {k: v for k, v in ws_changed.items() if v}
    record("Trim and collapse repeated whitespace in text fields", ws_changed, sum(ws_changed.values()))
    for col in TEXT_COLS + DATE_COLS + FLOAT_COLS + ["unique_key", "council_district"]:
        df[col] = df[col].replace("", pd.NA)
    record("Empty strings converted to proper nulls (values not imputed)", "all columns")

    # ---- 2. category label normalisation -------------------------------------------------
    case_fixes = {}
    for col in ["complaint_type", "descriptor"]:
        # canonical spelling = the most frequent spelling among case-insensitive matches
        key = df[col].str.lower()
        canon = df.groupby(key)[col].agg(lambda s: s.value_counts().idxmax())
        new = key.map(canon).astype("string")
        changed = int(((new != df[col]) & df[col].notna()).sum())
        df[col] = new.where(df[col].notna(), pd.NA)
        case_fixes[col] = changed
    for col in ["city", "borough", "status"]:
        new = df[col].str.upper() if col != "status" else df[col]
        changed = int(((new != df[col]) & df[col].notna()).sum())
        df[col] = new
        case_fixes[col] = changed
    record("Harmonised label case (complaint_type/descriptor -> most common spelling; city/borough -> UPPER)",
           {k: v for k, v in case_fixes.items() if v}, sum(case_fixes.values()))

    # ---- 3. types ------------------------------------------------------------------------
    for col in DATE_COLS:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in FLOAT_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["council_district"] = pd.to_numeric(df["council_district"], errors="coerce").astype("Int64")
    df["unique_key"] = pd.to_numeric(df["unique_key"], errors="raise").astype("int64")
    bad_dates = {c: int(df[c].isna().sum() - raw[c].eq("").sum()) for c in DATE_COLS}
    record("Parsed dates / coordinates / numeric ids safely (errors become null)",
           {"unparseable_dates": bad_dates})

    # ---- 4. duplicates -------------------------------------------------------------------
    dups = int(df["unique_key"].duplicated().sum())
    df = df.drop_duplicates("unique_key", keep="first")
    record("Checked duplicate unique_key (duplicates dropped, first kept)", f"{dups} duplicates found", dups)

    # ---- 5. quality flags (flag, never silently correct) --------------------------------
    c, cl, du = df["created_date"], df["closed_date"], df["due_date"]
    df["flag_closed_before_created"] = cl.notna() & (cl < c)
    df["flag_future_date"] = (
        (c > extraction_date) | (cl > extraction_date) | (du.notna() & (du > extraction_date + pd.Timedelta(days=3650)))
    )
    df["flag_status_closed_no_closed_date"] = (df["status"] == "Closed") & cl.isna()
    df["flag_closed_date_status_not_closed"] = cl.notna() & (df["status"] != "Closed")
    zip_ok = df["incident_zip"].str.fullmatch(r"\d{5}")
    df["flag_invalid_zip"] = df["incident_zip"].notna() & ~zip_ok.fillna(False)
    df["incident_zip"] = df["incident_zip"].where(~df["flag_invalid_zip"], pd.NA)  # value like 'NA' is not a ZIP
    df["flag_missing_coordinates"] = df[["latitude", "longitude"]].isna().any(axis=1)
    inside = df["latitude"].between(*NYC_LAT) & df["longitude"].between(*NYC_LON)
    df["flag_coordinates_outside_nyc"] = ~df["flag_missing_coordinates"] & ~inside
    flag_cols = [c_ for c_ in df.columns if c_.startswith("flag_")]
    record("Quality flags added (original values kept)", {f: int(df[f].sum()) for f in flag_cols})
    record("Invalid ZIP values set to null and flagged", "incident_zip not 5 digits", int(df["flag_invalid_zip"].sum()))

    # ---- 6. derived fields ---------------------------------------------------------------
    df["is_closed"] = cl.notna().astype("int8")  # per project definition: recorded closed date
    valid_res = cl.notna() & ~df["flag_closed_before_created"] & ~df["flag_future_date"]
    df["resolution_hours"] = ((cl - c).dt.total_seconds() / 3600).where(valid_res).round(4)
    df["is_over_72h"] = (df["resolution_hours"] > THRESHOLD_HOURS).astype("Int8").where(df["resolution_hours"].notna(), pd.NA)
    df["created_year"] = c.dt.year.astype("int16")
    df["created_month"] = c.dt.month.astype("int8")
    df["created_year_month"] = c.dt.strftime("%Y-%m")
    df["created_weekday"] = c.dt.day_name()
    df["created_weekday_num"] = c.dt.day_of_week.astype("int8")  # Monday=0
    df["created_hour"] = c.dt.hour.astype("int8")
    record("Derived fields added",
           ["is_closed", "resolution_hours (valid closed records only)", "is_over_72h",
            "created_year", "created_month", "created_year_month", "created_weekday", "created_weekday_num", "created_hour"])
    log["resolution_hours_valid"] = int(df["resolution_hours"].notna().sum())
    log["resolution_hours_excluded"] = {
        "no_closed_date": int(cl.isna().sum()),
        "closed_before_created": int(df["flag_closed_before_created"].sum()),
        "future_date": int((df["flag_future_date"] & cl.notna()).sum()),
    }

    # ---- 7. validation -------------------------------------------------------------------
    assert df["unique_key"].is_unique
    assert len(df) == len(raw) - dups
    val = {
        "raw_rows": int(len(raw)), "cleaned_rows": int(len(df)), "rows_removed": int(len(raw) - len(df)),
        "unique_keys": int(df["unique_key"].nunique()),
        "created_date_range": [str(c.min()), str(c.max())],
        "latitude_range": [float(df["latitude"].min()), float(df["latitude"].max())],
        "longitude_range": [float(df["longitude"].min()), float(df["longitude"].max())],
        "resolution_hours_range": [float(df["resolution_hours"].min()), float(df["resolution_hours"].max())],
    }
    log["validation"] = val

    out_path = ROOT / "data" / "clean" / f"nyc311_clean_{year}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, date_format="%Y-%m-%d %H:%M:%S")
    log["output_file"] = str(out_path.relative_to(ROOT))
    log["output_columns"] = list(df.columns)

    # sample check: reload and compare with the in-memory frame
    back = pd.read_csv(out_path, usecols=["unique_key", "resolution_hours", "is_closed"])
    assert len(back) == len(df) and back["unique_key"].is_unique
    log["validation"]["reload_check"] = "csv re-read: row count and unique_key match"

    (DOCS / "cleaning_log.json").write_text(json.dumps(log, indent=2, default=str))
    write_cleaning_md(log, extraction)
    write_dictionary(df, raw)
    print(f"raw {len(raw):,} -> clean {len(df):,} rows, {df.shape[1]} columns -> {out_path.relative_to(ROOT)}")
    print("flags:", {f: int(df[f].sum()) for f in flag_cols})
    print("valid resolution_hours:", log["resolution_hours_valid"], "| excluded:", log["resolution_hours_excluded"])


def write_cleaning_md(log: dict, extraction: dict) -> None:
    v = log["validation"]
    lines = [
        "# Cleaning and validation log",
        "",
        f"Input: `{log['input_file']}` ({log['raw_rows']:,} rows, extracted {extraction['extraction_finished_utc']} UTC).",
        f"Output: `{log['output_file']}` ({v['cleaned_rows']:,} rows, {len(log['output_columns'])} columns).",
        "",
        "Principles: raw data is never edited; nulls are preserved; impossible or implausible values are flagged, not corrected; no rows are dropped except exact duplicate keys.",
        "",
        "## Steps",
        "",
        "| # | Step | Detail | Affected |",
        "|---|---|---|---|",
    ]
    for i, s in enumerate(log["steps"], 1):
        detail = json.dumps(s["detail"], default=str) if not isinstance(s["detail"], str) else s["detail"]
        n = "" if s["rows_or_cells_affected"] is None else f"{s['rows_or_cells_affected']:,}"
        lines.append(f"| {i} | {s['step']} | {detail.replace('|', '/')} | {n} |")
    lines += [
        "",
        "## Validation",
        "",
        "| Check | Result |",
        "|---|---|",
        f"| Raw rows -> cleaned rows | {v['raw_rows']:,} -> {v['cleaned_rows']:,} (removed {v['rows_removed']}) |",
        f"| `unique_key` unique | {v['unique_keys']:,} distinct of {v['cleaned_rows']:,} |",
        f"| created_date range | {v['created_date_range'][0]} to {v['created_date_range'][1]} |",
        f"| Latitude / longitude range | {v['latitude_range'][0]:.4f}..{v['latitude_range'][1]:.4f} / {v['longitude_range'][0]:.4f}..{v['longitude_range'][1]:.4f} |",
        f"| resolution_hours range (valid only) | {v['resolution_hours_range'][0]:.2f} to {v['resolution_hours_range'][1]:,.2f} hours |",
        f"| Re-read of cleaned file | {v['reload_check']} |",
        "",
        "## resolution_hours coverage",
        "",
        f"Valid values: {log['resolution_hours_valid']:,}. Excluded: {log['resolution_hours_excluded']['no_closed_date']:,} with no closed date, "
        f"{log['resolution_hours_excluded']['closed_before_created']:,} with closed date before created date (flagged, not corrected), "
        f"{log['resolution_hours_excluded']['future_date']:,} with a date after the extraction date.",
        "",
        "Zero-hour resolutions (closed at the creation minute) are kept: they are plausible instant closures, not errors.",
        "Rows with status = Closed but no closed date, or a closed date but a non-Closed status, are flagged; `is_closed` follows the project definition (a recorded closed date).",
        "Long resolutions (several months) are kept; IQR outliers are investigated in Step 4, not deleted.",
    ]
    (DOCS / "cleaning_log.md").write_text("\n".join(lines) + "\n")


# (meaning, analytical use, transformation)
DICT = {
    "unique_key": ("Unique 311 request identifier", "Primary key; distinct request count", "Cast to integer"),
    "created_date": ("When the request was created", "Time trends, weekday/hour demand, start of resolution time", "Parsed to datetime"),
    "closed_date": ("When the request was closed (blank if not closed)", "Closure indicator and resolution time", "Parsed to datetime; nulls kept"),
    "due_date": ("Date the agency planned to respond by (rarely filled)", "Not used in KPIs (almost entirely missing)", "Parsed to datetime; nulls kept"),
    "agency": ("Responsible agency code (e.g. NYPD, HPD)", "Workload and resolution comparison by agency", "Whitespace trimmed"),
    "agency_name": ("Full agency name", "Labels for charts", "Whitespace trimmed"),
    "complaint_type": ("Main complaint category", "Top categories, resolution by category", "Whitespace trimmed; case variants merged"),
    "descriptor": ("Sub-category detail of the complaint", "Drill-down within a complaint type", "Whitespace collapsed; case variants merged"),
    "location_type": ("Type of place where the problem occurred", "Context for complaint patterns", "Whitespace trimmed; nulls kept"),
    "address_type": ("How the location was recorded (ADDRESS, INTERSECTION ...)", "Location data quality", "Whitespace trimmed"),
    "incident_zip": ("ZIP code of the incident", "Local geographic summaries", "Not 5 digits -> null and flagged"),
    "incident_address": ("Street address of the incident", "Not used in analysis (identifying detail)", "Whitespace collapsed"),
    "city": ("City name as recorded", "Secondary location label", "Upper-cased; whitespace trimmed"),
    "borough": ("NYC borough (BROOKLYN, QUEENS, BRONX, MANHATTAN, STATEN ISLAND, UNSPECIFIED)", "Borough volume, filters, geographic summary", "Upper-cased"),
    "status": ("Recorded request status", "Status distribution, closure rate", "Whitespace trimmed"),
    "resolution_description": ("Agency's text explanation of the outcome", "Reference only; not used in KPIs", "Whitespace collapsed"),
    "resolution_action_updated_date": ("Last time the agency updated the resolution", "Reference only", "Parsed to datetime"),
    "community_board": ("Community board of the incident", "Optional local grouping", "Whitespace trimmed"),
    "council_district": ("City council district number", "Optional local grouping", "Cast to nullable integer"),
    "police_precinct": ("Police precinct label", "Optional local grouping", "Whitespace trimmed"),
    "open_data_channel_type": ("How the request was submitted (ONLINE, PHONE, MOBILE ...)", "Channel mix", "Whitespace trimmed"),
    "x_coordinate_state_plane": ("NY State Plane X coordinate", "Not used (latitude/longitude used instead)", "Numeric conversion"),
    "y_coordinate_state_plane": ("NY State Plane Y coordinate", "Not used (latitude/longitude used instead)", "Numeric conversion"),
    "latitude": ("Latitude of the incident", "Maps and geographic concentration", "Numeric conversion; nulls kept"),
    "longitude": ("Longitude of the incident", "Maps and geographic concentration", "Numeric conversion; nulls kept"),
    "flag_closed_before_created": ("Derived flag: closed date earlier than created date", "Excludes the row from resolution statistics", "closed_date < created_date"),
    "flag_future_date": ("Derived flag: a date after the extraction date", "Excludes the row from resolution statistics", "Compared with extraction timestamp"),
    "flag_status_closed_no_closed_date": ("Derived flag: status Closed but no closed date", "Explains closure-rate gaps", "status == Closed and closed_date null"),
    "flag_closed_date_status_not_closed": ("Derived flag: has a closed date but status is not Closed", "Explains closure-rate gaps", "closed_date present and status != Closed"),
    "flag_invalid_zip": ("Derived flag: ZIP was not a 5-digit value", "Data-quality reporting", "Original value replaced by null"),
    "flag_missing_coordinates": ("Derived flag: latitude or longitude missing", "Geography coverage", "Null check"),
    "flag_coordinates_outside_nyc": ("Derived flag: coordinates outside the NYC bounding box", "Data-quality reporting", "Bounding box 40.4-41.0 N, -74.3 to -73.6 E"),
    "is_closed": ("1 if a closed date is recorded, else 0", "Recorded closure KPI, open requests KPI", "closed_date notna"),
    "resolution_hours": ("Hours from created to closed (valid closed records only)", "Median resolution KPI, outliers, skewness", "(closed - created) in hours; null if invalid"),
    "is_over_72h": ("1 if resolution_hours > 72 (project-defined cut-off)", "Over-72-hours KPI", "Null when resolution_hours is null"),
    "created_year": ("Year of creation", "Trend grouping", "From created_date"),
    "created_month": ("Month number of creation (1-12)", "Seasonality", "From created_date"),
    "created_year_month": ("Year-month label, e.g. 2024-03", "Monthly trend", "From created_date"),
    "created_weekday": ("Day name of creation", "Weekday demand", "From created_date"),
    "created_weekday_num": ("Weekday number, Monday=0 .. Sunday=6", "Sorting weekdays", "From created_date"),
    "created_hour": ("Hour of creation (0-23)", "Hourly demand", "From created_date"),
}
SQL_TYPES = lambda s: ("integer" if pd.api.types.is_integer_dtype(s) else "float" if pd.api.types.is_float_dtype(s)
                       else "datetime" if pd.api.types.is_datetime64_any_dtype(s) else "boolean flag" if s.dtype == bool else "text")


def write_dictionary(df: pd.DataFrame, raw: pd.DataFrame) -> None:
    n = len(df)
    lines = [
        "# Data dictionary",
        "",
        f"Cleaned table: {n:,} rows, {df.shape[1]} columns. Missingness is measured on the cleaned file. "
        "Source fields come from the NYC 311 API (`erm2-nwe9`); fields marked *derived* are created in `src/clean.py`.",
        "",
        "| Field | Origin | Meaning | Type | Missing | Transformation | Analytical use |",
        "|---|---|---|---|---|---|---|",
    ]
    for col in df.columns:
        meaning, use, how = DICT.get(col, ("", "", ""))
        origin = "source" if col in raw.columns else "derived"
        miss = int(df[col].isna().sum())
        lines.append(f"| `{col}` | {origin} | {meaning} | {SQL_TYPES(df[col])} | {miss:,} ({miss / n:.1%}) | {how} | {use} |")
    lines += ["", "Do not assume every field is populated: `due_date` is almost always empty and `location_type` is missing for about 12% of rows."]
    (DOCS / "data_dictionary.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    main(ap.parse_args().year)
