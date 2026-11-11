import numpy as np
import plotly.express as px
import streamlit as st

import common

f = common.setup("Resolution time (tasks 8-12, 15)")
st.write("Only requests with a valid resolution time are used here: a closed date that is present and not before the created date.")

min_n = st.sidebar.slider("Minimum valid cases per group", 20, 500, 100, step=10, key="min_n")

res = common.q("SELECT resolution_hours FROM service_requests WHERE {where} AND resolution_hours IS NOT NULL", f)["resolution_hours"]
if res.empty:
    st.warning("None of the filtered requests has a valid resolution time.")
    st.stop()

# ---- task 8 ----
st.subheader("Task 8: descriptive statistics")
q1, q3 = res.quantile(0.25), res.quantile(0.75)
stats_tbl = {
    "valid cases": f"{len(res):,}", "mean (h)": f"{res.mean():.1f}", "median (h)": f"{res.median():.1f}",
    "Q1 (h)": f"{q1:.2f}", "Q3 (h)": f"{q3:.1f}", "95th percentile (h)": f"{res.quantile(0.95):.0f}",
    "max (h)": f"{res.max():,.0f}", "std dev (h)": f"{res.std():.1f}",
}
cols = st.columns(len(stats_tbl))
for c, (k, v) in zip(cols, stats_tbl.items()):
    c.metric(k, v)
skew = res.skew()
st.caption(f"Skewness is {skew:.1f}. When the mean is far above the median a few very long cases pull the average up, so the median is the safer typical value.")

# ---- task 12 ----
st.subheader("Task 12: distribution")
col1, col2 = st.columns(2)
bands = ["under 1 hour", "1 to 4 hours", "4 to 24 hours", "1 to 3 days", "3 to 7 days", "7 to 30 days", "over 30 days"]
cut = np.digitize(res, [1, 4, 24, 72, 168, 720])
band_counts = np.bincount(cut, minlength=7)
col1.plotly_chart(px.bar(x=bands, y=band_counts, labels={"x": "", "y": "requests"}), width="stretch")
hist = px.histogram(x=np.log10(res + 1), nbins=50, labels={"x": "log10(hours + 1)"})
col2.plotly_chart(hist, width="stretch")

# ---- task 9 + 10 ----
st.subheader("Tasks 9 and 10: median resolution time")
col3, col4 = st.columns(2)
by_type = common.q("""
    SELECT complaint_type, COUNT(resolution_hours) AS n_valid,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY resolution_hours) AS median_h
    FROM service_requests WHERE {where} AND resolution_hours IS NOT NULL
    GROUP BY 1 HAVING COUNT(resolution_hours) >= :min_n ORDER BY median_h DESC""", f, {"min_n": min_n})
by_agency = common.q("""
    SELECT agency, COUNT(resolution_hours) AS n_valid,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY resolution_hours) AS median_h
    FROM service_requests WHERE {where} AND resolution_hours IS NOT NULL
    GROUP BY 1 HAVING COUNT(resolution_hours) >= :min_n ORDER BY median_h DESC""", f, {"min_n": min_n})
with col3:
    if by_type.empty:
        st.info("No complaint type has enough valid cases. Lower the minimum in the sidebar.")
    else:
        st.write("Slowest complaint types (hours, log scale)")
        top = by_type.head(12).iloc[::-1]
        st.plotly_chart(px.bar(top, x="median_h", y="complaint_type", orientation="h", log_x=True, hover_data=["n_valid"]).update_layout(yaxis_title=None), width="stretch")
with col4:
    if by_agency.empty:
        st.info("No agency has enough valid cases. Lower the minimum in the sidebar.")
    else:
        st.write("Agencies (hours, log scale)")
        st.plotly_chart(px.bar(by_agency.iloc[::-1], x="median_h", y="agency", orientation="h", log_x=True, hover_data=["n_valid"]).update_layout(yaxis_title=None), width="stretch")
st.caption("Agencies handle different kinds of work, so these medians show typical waiting times, not who performs better. "
           "A median of 0 hours (for example Rodent) means many records were closed at the same minute they were created, which may be a recording habit.")

# ---- task 11 ----
st.subheader("Task 11: IQR outliers")
iqr = q3 - q1
high, low = q3 + 1.5 * iqr, q1 - 1.5 * iqr
n_high, n_low = int((res > high).sum()), int((res < low).sum())
c1, c2, c3, c4 = st.columns(4)
c1.metric("Upper fence", f"{high:.1f} h")
c2.metric("Lower fence", f"{low:.1f} h")
c3.metric("High outliers", f"{n_high:,}")
c4.metric("Share of valid", f"{n_high / len(res) * 100:.1f}%")
st.caption("Outliers are flagged for a closer look, not removed. A long case can be real (a repair, a permit). A negative lower fence means no low outliers are possible.")
out_by_agency = common.q("""
    SELECT agency, COUNT(*) AS n_valid,
           COUNT(*) FILTER (WHERE resolution_hours > :hi) AS high_outliers,
           ROUND(100.0 * COUNT(*) FILTER (WHERE resolution_hours > :hi) / COUNT(*), 1) AS pct_outliers
    FROM service_requests WHERE {where} AND resolution_hours IS NOT NULL
    GROUP BY 1 HAVING COUNT(*) >= :min_n ORDER BY pct_outliers DESC""", f, {"hi": float(high), "min_n": min_n})
if not out_by_agency.empty:
    st.plotly_chart(px.bar(out_by_agency, x="agency", y="pct_outliers", hover_data=["high_outliers", "n_valid"],
                           labels={"pct_outliers": "% above upper fence"}), width="stretch")

# ---- task 15 ----
st.subheader("Task 15: high volume and slow")
if len(by_type) >= 4:
    vol_cut = by_type["n_valid"].quantile(0.75)
    med_cut = by_type["median_h"].quantile(0.75)
    by_type["quadrant"] = np.where((by_type["n_valid"] >= vol_cut) & (by_type["median_h"] >= med_cut),
                                   "high volume and slow", "other")
    scatter = px.scatter(by_type, x="n_valid", y=by_type["median_h"].clip(lower=0.05), color="quadrant", hover_name="complaint_type",
                         log_x=True, log_y=True, labels={"n_valid": "valid cases", "y": "median hours"},
                         color_discrete_map={"high volume and slow": "#e45756", "other": "#9ecae9"})
    scatter.add_vline(x=vol_cut, line_dash="dot", line_color="grey")
    scatter.add_hline(y=med_cut, line_dash="dot", line_color="grey")
    st.plotly_chart(scatter, width="stretch")
    hits = by_type[by_type["quadrant"] != "other"][["complaint_type", "n_valid", "median_h"]]
    st.write("Both high (75th percentile or above on volume and on median time):")
    st.dataframe(hits.round(1), width="stretch", hide_index=True)
else:
    st.info("Too few complaint types with enough valid cases for this chart. Widen the filters or lower the minimum.")
