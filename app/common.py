"""Things every page of the dashboard needs: DB access, the sidebar filters and the KPI query."""
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from db import get_engine  # noqa: E402

THRESHOLD_HOURS = 72   # our own cut-off for "slow", not an official standard
FILTER_KEYS = ["flt_dates", "flt_boroughs", "flt_types"]


@st.cache_resource
def engine():
    return get_engine(connect_args={"connect_timeout": 5})


@st.cache_data(ttl=600, show_spinner=False)
def run_query(sql: str, params: dict) -> pd.DataFrame:
    with engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


@dataclass
class Filters:
    where: str     # e.g. "created_date >= :d0 AND ..." (only fixed text, values go in params)
    params: dict
    summary: str


def q(sql_with_where: str, f: Filters, extra: dict | None = None) -> pd.DataFrame:
    """Run a query that contains the placeholder {where}."""
    return run_query(sql_with_where.format(where=f.where), {**f.params, **(extra or {})})


def setup(title: str) -> Filters:
    """Page config, DB check and sidebar filters. Call first on every page."""
    st.set_page_config(page_title=f"Urban Pulse | {title}", page_icon="🏙️", layout="wide")
    st.title(title)

    try:
        bounds = run_query("SELECT MIN(created_date)::date AS lo, MAX(created_date)::date AS hi FROM service_requests", {})
        boroughs = run_query("SELECT DISTINCT borough FROM service_requests ORDER BY 1", {})["borough"].dropna().tolist()
        types = run_query("SELECT complaint_type FROM service_requests GROUP BY 1 ORDER BY COUNT(*) DESC", {})["complaint_type"].tolist()
    except Exception as exc:
        st.error("Could not connect to the database, so there is nothing to show yet.")
        st.markdown("Check that the Docker PostgreSQL container is running and that `.env` has the right host, port, user and password. "
                    "Then reload this page.")
        with st.expander("Technical detail"):
            st.code(f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else ''}")
        st.stop()

    lo, hi = bounds.loc[0, "lo"], bounds.loc[0, "hi"]

    # keep the filter choices when the user moves to another page
    for k in FILTER_KEYS:
        if k in st.session_state:
            st.session_state[k] = st.session_state[k]
    st.session_state.setdefault("flt_dates", (lo, hi))
    st.session_state.setdefault("flt_boroughs", [])
    st.session_state.setdefault("flt_types", [])

    st.sidebar.header("Filters")
    picked = st.sidebar.date_input("Created between", min_value=lo, max_value=hi, key="flt_dates")
    sel_boroughs = st.sidebar.multiselect("Borough (empty = all)", boroughs, key="flt_boroughs")
    sel_types = st.sidebar.multiselect("Complaint type (empty = all)", types, key="flt_types")
    if st.sidebar.button("Reset filters"):
        for k in FILTER_KEYS:
            del st.session_state[k]
        st.rerun()

    if not isinstance(picked, (tuple, list)) or len(picked) != 2:
        st.info("Pick an end date to finish the date range.")
        st.stop()
    start, end = picked

    where = "created_date >= :d0 AND created_date < :d1"
    params = {"d0": start, "d1": pd.Timestamp(end) + pd.Timedelta(days=1)}
    if sel_boroughs:
        where += " AND borough = ANY(:boroughs)"
        params["boroughs"] = sel_boroughs
    if sel_types:
        where += " AND complaint_type = ANY(:types)"
        params["types"] = sel_types

    summary = f"{start} to {end}"
    summary += f" | {', '.join(sel_boroughs)}" if sel_boroughs else " | all boroughs"
    summary += f" | {len(sel_types)} complaint types" if sel_types else " | all complaint types"
    f = Filters(where, params, summary)

    n = q("SELECT COUNT(*) AS n FROM service_requests WHERE {where}", f).loc[0, "n"]
    if n == 0:
        st.warning("No requests match these filters. Widen the date range or clear a borough / complaint type.")
        st.stop()
    st.caption(f"Filters: {summary} ({n:,} requests)")
    return f


def kpis(f: Filters) -> dict:
    row = q("""
        SELECT COUNT(DISTINCT unique_key)                       AS total,
               COUNT(*)                                          AS row_count,
               COALESCE(SUM(is_closed), 0)                       AS closed,
               COUNT(*) FILTER (WHERE is_closed = 0)             AS open_n,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY resolution_hours) AS median_h,
               COUNT(resolution_hours)                           AS n_valid,
               COUNT(*) FILTER (WHERE resolution_hours > :thr)   AS over_thr
        FROM service_requests WHERE {where}""", f, {"thr": THRESHOLD_HOURS}).iloc[0]
    return {
        "total": int(row["total"]),
        "closed_pct": row["closed"] / row["row_count"] * 100,
        "open": int(row["open_n"]),
        "median_h": None if pd.isna(row["median_h"]) else float(row["median_h"]),
        "over_pct": None if row["n_valid"] == 0 else row["over_thr"] / row["n_valid"] * 100,
        "n_valid": int(row["n_valid"]),
    }


def show_kpis(k: dict) -> None:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total requests", f"{k['total']:,}", help="Distinct request identifiers in the filtered data.")
    c2.metric("Recorded closure", f"{k['closed_pct']:.1f}%",
              help="Share of filtered rows that have a closed date. This is not a measure of citizen satisfaction.")
    c3.metric("Open requests", f"{k['open']:,}", help="Filtered rows without a recorded closed date.")
    c4.metric("Median resolution", "n/a" if k["median_h"] is None else f"{k['median_h']:.1f} h",
              help=f"Median hours from created to closed, valid cases only (n = {k['n_valid']:,}).")
    c5.metric(f"Over {THRESHOLD_HOURS} hours", "n/a" if k["over_pct"] is None else f"{k['over_pct']:.1f}%",
              help=f"Share of valid resolution times above {THRESHOLD_HOURS} hours. The {THRESHOLD_HOURS}-hour line is a project choice, not an official service standard.")
