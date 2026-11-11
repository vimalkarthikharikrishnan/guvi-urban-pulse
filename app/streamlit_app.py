import plotly.express as px
import streamlit as st

import common

f = common.setup("Urban Pulse: NYC 311 overview")

st.write("Citizen complaint intelligence from NYC 311 requests created in 2024 "
         "(a ~3% sample, extracted Nov 2026). Use the filters on the left; every page follows them.")

common.show_kpis(common.kpis(f))
st.caption("Closure means a closed date is recorded, it says nothing about satisfaction. "
           "The 72-hour line is our own analysis cut-off, not an official service standard.")

st.subheader("Requests per month")
monthly = common.q("""
    SELECT created_year_month AS month, COUNT(*) AS requests
    FROM service_requests WHERE {where}
    GROUP BY 1 ORDER BY 1""", f)
fig = px.line(monthly, x="month", y="requests", markers=True)
fig.update_yaxes(rangemode="tozero")
st.plotly_chart(fig, width="stretch")

st.subheader("Filtered record preview")
preview = common.q("""
    SELECT unique_key, created_date, closed_date, agency, complaint_type, borough, status,
           ROUND(resolution_hours::numeric, 1) AS resolution_hours
    FROM service_requests WHERE {where}
    ORDER BY created_date DESC LIMIT 200""", f)
st.dataframe(preview, width="stretch", hide_index=True)
st.caption("Showing the 200 most recent matching requests.")
st.download_button("Download this preview as CSV", preview.to_csv(index=False), "urban_pulse_preview.csv", "text/csv")
