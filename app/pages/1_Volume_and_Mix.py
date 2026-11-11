import plotly.express as px
import streamlit as st

import common

f = common.setup("Volume and mix (tasks 1-5, 7)")
st.write("What people ask for, which agencies and boroughs get it, and how demand moves over the year.")

# task 1 + 7 in one row
total = common.q("SELECT COUNT(DISTINCT unique_key) AS n FROM service_requests WHERE {where}", f).loc[0, "n"]
st.metric("Task 1: total distinct requests", f"{total:,}")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Task 2: top 10 complaint types")
    top = common.q("""
        SELECT complaint_type, COUNT(*) AS requests FROM service_requests WHERE {where}
        GROUP BY 1 ORDER BY 2 DESC LIMIT 10""", f)
    fig = px.bar(top.iloc[::-1], x="requests", y="complaint_type", orientation="h")
    fig.update_layout(yaxis_title=None)
    st.plotly_chart(fig, width="stretch")
with col2:
    st.subheader("Task 3: agency workload")
    ag = common.q("""
        SELECT agency, COUNT(*) AS requests,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
        FROM service_requests WHERE {where} GROUP BY 1 ORDER BY 2 DESC""", f)
    fig = px.bar(ag, x="agency", y="requests", hover_data=["pct"])
    st.plotly_chart(fig, width="stretch")

col3, col4 = st.columns(2)
with col3:
    st.subheader("Task 4: volume by borough")
    bo = common.q("""
        SELECT borough, COUNT(*) AS requests FROM service_requests WHERE {where}
        GROUP BY 1 ORDER BY 2 DESC""", f)
    fig = px.bar(bo, x="borough", y="requests")
    st.plotly_chart(fig, width="stretch")
    st.caption("Raw counts, not adjusted for population.")
with col4:
    st.subheader("Task 7: status distribution")
    stt = common.q("""
        SELECT status, COUNT(*) AS requests FROM service_requests WHERE {where}
        GROUP BY 1 ORDER BY 2 DESC""", f)
    fig = px.bar(stt.iloc[::-1], x="requests", y="status", orientation="h", log_x=True)
    fig.update_layout(yaxis_title=None)
    st.plotly_chart(fig, width="stretch")
    st.caption("Log scale, because most requests are Closed and the small groups would disappear.")

st.subheader("Task 5: monthly trend")
mon = common.q("""
    SELECT created_year_month AS month, COUNT(*) AS requests FROM service_requests WHERE {where}
    GROUP BY 1 ORDER BY 1""", f)
fig = px.line(mon, x="month", y="requests", markers=True)
fig.update_yaxes(rangemode="tozero")
st.plotly_chart(fig, width="stretch")
st.caption("A shorter month (February) shows fewer requests partly because it has fewer days. One year of data cannot prove a seasonal pattern.")

with st.expander("Table: agency workload"):
    st.dataframe(ag, width="stretch", hide_index=True)
