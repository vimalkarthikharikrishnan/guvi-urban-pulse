import streamlit as st

import common

f = common.setup("Urban Pulse: NYC 311 overview")

st.write("NYC 311 service requests created in 2024, a ~3% sample pulled in November 2026. "
         "The filters on the left apply to every page.")

common.show_kpis(common.kpis(f))
st.caption("Closure means a closed date is recorded, not that the citizen was satisfied. "
           "The 72-hour line is our own cut-off, not an official standard.")

st.subheader("Filtered record preview")
preview = common.q("""
    SELECT unique_key, created_date, closed_date, agency, complaint_type, borough, status,
           ROUND(resolution_hours::numeric, 1) AS resolution_hours
    FROM service_requests WHERE {where}
    ORDER BY created_date DESC LIMIT 200""", f)
st.dataframe(preview, width="stretch", hide_index=True)
st.caption("The 200 most recent matching requests.")
st.download_button("Download this preview as CSV", preview.to_csv(index=False), "urban_pulse_preview.csv", "text/csv")
