import plotly.express as px
import streamlit as st

import common

f = common.setup("Demand by weekday and hour (task 6)")

grid = common.q("""
    SELECT created_weekday_num AS d, created_hour AS h, COUNT(*) AS requests
    FROM service_requests WHERE {where} GROUP BY 1, 2""", f)

days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
pivot = grid.pivot(index="d", columns="h", values="requests").reindex(index=range(7), columns=range(24)).fillna(0)
pivot.index = days

fig = px.imshow(pivot, aspect="auto", color_continuous_scale="YlOrRd",
                labels={"x": "hour of day", "y": "", "color": "requests"})
st.plotly_chart(fig, width="stretch")

col1, col2 = st.columns(2)
by_day = pivot.sum(axis=1).reset_index()
by_day.columns = ["weekday", "requests"]
col1.subheader("By weekday")
col1.plotly_chart(px.bar(by_day, x="weekday", y="requests"), width="stretch")
by_hour = pivot.sum(axis=0).reset_index()
by_hour.columns = ["hour", "requests"]
col2.subheader("By hour")
col2.plotly_chart(px.bar(by_hour, x="hour", y="requests"), width="stretch")

busiest = by_day.sort_values("requests", ascending=False).iloc[0]
quiet = by_day.sort_values("requests").iloc[0]
peak = by_hour.sort_values("requests", ascending=False).iloc[0]
st.caption(f"With the current filters, {busiest['weekday']} is the busiest day, {quiet['weekday']} the quietest, "
           f"and hour {int(peak['hour'])}:00 is the peak. Timestamps are the times recorded in the source data. "
           "A bump at midnight may come from default timestamps, we have not confirmed that.")
