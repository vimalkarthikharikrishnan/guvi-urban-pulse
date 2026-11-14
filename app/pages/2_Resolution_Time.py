import plotly.express as px
import streamlit as st

import common

MIN_CASES = 100

f = common.setup("Resolution time")
st.caption("Analyst tasks 8 to 12, in order.")
st.write("Only requests with a valid resolution time are used here: a closed date that is present and not before the created date.")

res = common.q("SELECT resolution_hours FROM service_requests WHERE {where} AND resolution_hours IS NOT NULL", f)["resolution_hours"]
if res.empty:
    st.warning("None of the filtered requests has a valid resolution time.")
    st.stop()

st.subheader("How long requests take")
q1, q3 = res.quantile(0.25), res.quantile(0.75)
a1, a2, a3, a4 = st.columns(4)
a1.metric("valid cases", f"{len(res):,}")
a2.metric("mean (h)", f"{res.mean():.1f}")
a3.metric("median (h)", f"{res.median():.1f}")
a4.metric("Q1 (h)", f"{q1:.2f}")
b1, b2, b3, b4 = st.columns(4)
b1.metric("Q3 (h)", f"{q3:.1f}")
b2.metric("95th percentile (h)", f"{res.quantile(0.95):,.0f}")
b3.metric("max (h)", f"{res.max():,.0f}")
b4.metric("std dev (h)", f"{res.std():,.1f}")

st.subheader("Median time by complaint type and by agency")
by_type = common.q("""
    SELECT complaint_type, COUNT(resolution_hours) AS n_valid,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY resolution_hours) AS median_h
    FROM service_requests WHERE {where} AND resolution_hours IS NOT NULL
    GROUP BY 1 HAVING COUNT(resolution_hours) >= :min_n ORDER BY median_h DESC""", f, {"min_n": MIN_CASES})
by_agency = common.q("""
    SELECT agency, COUNT(resolution_hours) AS n_valid,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY resolution_hours) AS median_h
    FROM service_requests WHERE {where} AND resolution_hours IS NOT NULL
    GROUP BY 1 HAVING COUNT(resolution_hours) >= :min_n ORDER BY median_h DESC""", f, {"min_n": MIN_CASES})

col1, col2 = st.columns(2)
with col1:
    if by_type.empty:
        st.info(f"No complaint type has {MIN_CASES} or more valid cases with these filters.")
    else:
        st.write("Slowest 12 complaint types (hours, log scale)")
        top = by_type.head(12).sort_values("median_h")
        fig = px.bar(top, x="median_h", y="complaint_type", orientation="h", log_x=True, hover_data=["n_valid"])
        st.plotly_chart(fig.update_layout(yaxis_title=None), width="stretch")
with col2:
    if by_agency.empty:
        st.info(f"No agency has {MIN_CASES} or more valid cases with these filters.")
    else:
        st.write("Agencies (hours, log scale)")
        fig = px.bar(by_agency.sort_values("median_h"), x="median_h", y="agency", orientation="h", log_x=True, hover_data=["n_valid"])
        st.plotly_chart(fig.update_layout(yaxis_title=None), width="stretch")
st.caption(f"Only groups with at least {MIN_CASES} valid cases. Agencies do different kinds of work, so this is about typical "
           "waiting time, not who performs better. A median of 0 hours (Rodent, for example) means many requests were "
           "closed in the same minute they were created.")

st.subheader("Unusually long cases (IQR rule)")
iqr = q3 - q1
high, low = q3 + 1.5 * iqr, q1 - 1.5 * iqr
n_high = int((res > high).sum())
c1, c2, c3, c4 = st.columns(4)
c1.metric("Upper fence", f"{high:.1f} h")
c2.metric("Lower fence", f"{low:.1f} h")
c3.metric("High outliers", f"{n_high:,}")
c4.metric("Share of valid", f"{n_high / len(res) * 100:.1f}%")
by_agency_out = common.q("""
    SELECT agency, COUNT(*) AS n_valid,
           COUNT(*) FILTER (WHERE resolution_hours > :hi) AS high_outliers,
           ROUND(100.0 * COUNT(*) FILTER (WHERE resolution_hours > :hi) / COUNT(*), 1) AS pct_outliers
    FROM service_requests WHERE {where} AND resolution_hours IS NOT NULL
    GROUP BY 1 HAVING COUNT(*) >= :min_n ORDER BY pct_outliers DESC""", f, {"hi": float(high), "min_n": MIN_CASES})
if not by_agency_out.empty:
    st.plotly_chart(px.bar(by_agency_out, x="agency", y="pct_outliers", hover_data=["high_outliers", "n_valid"],
                           labels={"pct_outliers": "% above upper fence"}), width="stretch")
st.caption("Outliers are a prompt to look closer, not rows to delete. A long case can be real, like a repair or a permit. "
           "The lower fence is negative, so there are no low outliers.")

st.subheader("How the times are spread")
bands = ["under 1 hour", "1 to 4 hours", "4 to 24 hours", "1 to 3 days", "3 to 7 days", "7 to 30 days", "over 30 days"]
limits = [1, 4, 24, 72, 168, 720]
counts = [0] * 7
for hours in res:
    band = 0
    while band < 6 and hours >= limits[band]:
        band += 1
    counts[band] += 1
st.plotly_chart(px.bar(x=bands, y=counts, labels={"x": "", "y": "requests"}), width="stretch")
st.caption(f"Skewness is {res.skew():.1f}. The mean is far above the median because a few very long cases pull it up, "
           "so the median is the better typical value.")
