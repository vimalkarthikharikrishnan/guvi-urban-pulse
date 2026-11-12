import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from db import get_engine

THRESHOLD_HOURS = 72
FILTER_KEYS = ["flt_dates", "flt_boroughs", "flt_types"]

px.defaults.color_discrete_sequence = ["#1f5f8b", "#c9763d", "#7a8b99", "#6f9a7b"]
px.defaults.color_continuous_scale = ["#eef3f7", "#1f5f8b"]


@st.cache_resource
def engine():
    return get_engine(connect_args={"connect_timeout": 15})


@st.cache_data(ttl=600, show_spinner=False)
def run_query(sql, params):
    for attempt in (1, 2):
        try:
            with engine().connect() as conn:
                return pd.read_sql(text(sql), conn, params=params)
        except SQLAlchemyError:
            if attempt == 2:
                raise
            time.sleep(5)


def fetch(sql, params):
    try:
        return run_query(sql, params)
    except (SQLAlchemyError, KeyError) as exc:
        st.error("Could not reach the database, so there is nothing to show yet.")
        st.markdown("The database may be waking up (the free hosted one sleeps when idle). "
                    "Wait about 10 seconds and reload this page. If it keeps failing, check the connection settings "
                    "(`.env` when running locally, Secrets on Streamlit Cloud).")
        with st.expander("Technical detail"):
            st.code(type(exc).__name__)
        st.stop()


@dataclass
class Filters:
    where: str
    params: dict
    summary: str


def q(sql_with_where, f, extra=None):
    return fetch(sql_with_where.format(where=f.where), {**f.params, **(extra or {})})


def setup(title):
    st.set_page_config(page_title=f"Urban Pulse - {title}", layout="wide")
    st.title(title)

    bounds = fetch("SELECT MIN(created_date)::date AS lo, MAX(created_date)::date AS hi FROM service_requests", {})
    boroughs = fetch("SELECT DISTINCT borough FROM service_requests ORDER BY 1", {})["borough"].dropna().tolist()
    types = fetch("SELECT complaint_type FROM service_requests GROUP BY 1 ORDER BY COUNT(*) DESC", {})["complaint_type"].tolist()

    lo, hi = bounds.loc[0, "lo"], bounds.loc[0, "hi"]

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
    summary += f", {', '.join(sel_boroughs)}" if sel_boroughs else ", all boroughs"
    summary += f", {len(sel_types)} complaint types" if sel_types else ", all complaint types"
    f = Filters(where, params, summary)

    n = q("SELECT COUNT(*) AS n FROM service_requests WHERE {where}", f).loc[0, "n"]
    if n == 0:
        st.warning("No requests match these filters. Widen the date range or clear a borough / complaint type.")
        st.stop()
    st.caption(f"Showing {n:,} requests created {summary}")
    return f


def kpis(f):
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


def show_kpis(k):
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total requests", f"{k['total']:,}", help="Distinct request identifiers in the filtered data.")
    c2.metric("Recorded closure", f"{k['closed_pct']:.1f}%",
              help="Share of filtered rows that have a closed date. This is not a measure of citizen satisfaction.")
    c3.metric("Open requests", f"{k['open']:,}", help="Filtered rows without a recorded closed date.")
    c4.metric("Median resolution", "n/a" if k["median_h"] is None else f"{k['median_h']:.1f} h",
              help=f"Median hours from created to closed, valid cases only (n = {k['n_valid']:,}).")
    c5.metric(f"Over {THRESHOLD_HOURS} hours", "n/a" if k["over_pct"] is None else f"{k['over_pct']:.1f}%",
              help=f"Share of valid resolution times above {THRESHOLD_HOURS} hours. The {THRESHOLD_HOURS}-hour line is a project choice, not an official service standard.")
