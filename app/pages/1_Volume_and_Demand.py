import pandas as pd
import plotly.express as px
import streamlit as st

import common

f = common.setup("Volume and demand")
st.caption("Analyst tasks 1 to 7, in order.")

total = common.q("SELECT COUNT(DISTINCT unique_key) AS n FROM service_requests WHERE {where}", f).loc[0, "n"]
st.metric("Total distinct requests", f"{total:,}")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Top 10 complaint types")
    top = common.q("""
        SELECT complaint_type, COUNT(*) AS requests FROM service_requests WHERE {where}
        GROUP BY 1 ORDER BY 2 DESC LIMIT 10""", f)
    fig = px.bar(top.sort_values("requests"), x="requests", y="complaint_type", orientation="h")
    fig.update_layout(yaxis_title=None)
    st.plotly_chart(fig, width="stretch")
with col2:
    st.subheader("Agency workload")
    ag = common.q("""
        SELECT agency, COUNT(*) AS requests,
               ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM service_requests WHERE {where}), 1) AS pct
        FROM service_requests WHERE {where} GROUP BY 1 ORDER BY 2 DESC""", f)
    st.plotly_chart(px.bar(ag, x="agency", y="requests", hover_data=["pct"]), width="stretch")

col3, col4 = st.columns(2)
with col3:
    st.subheader("Requests by borough")
    bo = common.q("""
        SELECT borough, COUNT(*) AS requests FROM service_requests WHERE {where}
        GROUP BY 1 ORDER BY 2 DESC""", f)
    st.plotly_chart(px.bar(bo, x="borough", y="requests"), width="stretch")
    st.caption("Raw counts, not adjusted for population.")
with col4:
    st.subheader("Requests per month")
    mon = common.q("""
        SELECT created_year_month AS month, COUNT(*) AS requests FROM service_requests WHERE {where}
        GROUP BY 1 ORDER BY 1""", f)
    fig = px.line(mon, x="month", y="requests", markers=True)
    fig.update_yaxes(rangemode="tozero")
    st.plotly_chart(fig, width="stretch")
    st.caption("February is shorter, which explains part of its dip. One year cannot show a seasonal pattern.")

grid = common.q("""
    SELECT created_weekday_num AS d, created_hour AS h, COUNT(*) AS requests
    FROM service_requests WHERE {where} GROUP BY 1, 2""", f)
days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
day_counts = [0] * 7
hour_counts = [0] * 24
for _, row in grid.iterrows():
    day_counts[int(row["d"])] += row["requests"]
    hour_counts[int(row["h"])] += row["requests"]
by_day = pd.DataFrame({"weekday": days, "requests": day_counts})
by_hour = pd.DataFrame({"hour": list(range(24)), "requests": hour_counts})

col5, col6 = st.columns(2)
col5.subheader("Requests by weekday")
col5.plotly_chart(px.bar(by_day, x="weekday", y="requests"), width="stretch")
col6.subheader("Requests by hour")
col6.plotly_chart(px.bar(by_hour, x="hour", y="requests"), width="stretch")
busiest = by_day.loc[by_day["requests"].idxmax(), "weekday"]
quietest = by_day.loc[by_day["requests"].idxmin(), "weekday"]
peak = int(by_hour.loc[by_hour["requests"].idxmax(), "hour"])
st.caption(f"Busiest day: {busiest}. Quietest day: {quietest}. Peak hour: {peak}:00. "
           "The bump at midnight may come from default timestamps, we have not checked.")

st.subheader("Request status")
stt = common.q("""
    SELECT status, COUNT(*) AS requests FROM service_requests WHERE {where}
    GROUP BY 1 ORDER BY 2 DESC""", f)
fig = px.bar(stt.sort_values("requests"), x="requests", y="status", orientation="h", log_x=True)
fig.update_layout(yaxis_title=None)
st.plotly_chart(fig, width="stretch")
st.caption("Log scale, so the small groups stay visible.")
