import plotly.express as px
import streamlit as st

import common

MIN_REQUESTS = 500   # agencies with fewer requests are left out of the closure chart, same rule as the SQL

f = common.setup("Geography and closure")
st.caption("Analyst tasks 13 and 14, in order.")

# ---- task 13 ----
st.subheader("Where requests are concentrated")
cover = common.q("""
    SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE NOT flag_missing_coordinates) AS usable
    FROM service_requests WHERE {where}""", f).iloc[0]
st.write(f"{cover['usable']:,} of {cover['total']:,} requests have usable coordinates ({cover['usable'] / cover['total'] * 100:.1f}%). "
         "The rest are left out.")

if cover["usable"] == 0:
    st.info("No coordinates for these filters. Borough totals are on the Volume and demand page.")
else:
    hot = common.q("""
        SELECT ROUND(latitude::numeric, 2) AS lat_cell, ROUND(longitude::numeric, 2) AS lon_cell,
               COUNT(*) AS requests,
               MODE() WITHIN GROUP (ORDER BY borough) AS borough,
               MODE() WITHIN GROUP (ORDER BY complaint_type) AS top_complaint
        FROM service_requests WHERE {where} AND NOT flag_missing_coordinates
        GROUP BY 1, 2 ORDER BY requests DESC LIMIT 10""", f)
    hot["area"] = hot["borough"].str.title() + " (" + hot["lat_cell"].astype(str) + ", " + hot["lon_cell"].astype(str) + ")"
    fig = px.bar(hot.iloc[::-1], x="requests", y="area", orientation="h", hover_data=["top_complaint"])
    fig.update_layout(yaxis_title=None)
    st.plotly_chart(fig, width="stretch")
    st.caption("The 10 busiest grid cells (about 1 km each), with latitude and longitude. Hover to see the most common complaint. "
               "One exact point in the Bronx (655 East 230 Street) holds over 1,600 requests, almost all Noise - Residential. "
               "It looks like a default location, not real concentration, so read the busiest areas with care.")

# ---- task 14 ----
st.subheader("How many requests have a closed date")
ag = common.q("""
    SELECT agency, COUNT(*) AS requests,
           ROUND(100.0 * SUM(is_closed) / COUNT(*), 1) AS closed_date_pct,
           ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'Closed') / COUNT(*), 1) AS status_closed_pct
    FROM service_requests WHERE {where}
    GROUP BY 1 HAVING COUNT(*) >= :min_rows ORDER BY closed_date_pct""", f, {"min_rows": MIN_REQUESTS})
bo = common.q("""
    SELECT borough, COUNT(*) AS requests, ROUND(100.0 * SUM(is_closed) / COUNT(*), 1) AS closed_date_pct
    FROM service_requests WHERE {where} GROUP BY 1 ORDER BY closed_date_pct""", f)

col1, col2 = st.columns(2)
with col1:
    st.write("By agency")
    if ag.empty:
        st.info(f"No agency has {MIN_REQUESTS} or more requests with these filters.")
    else:
        st.plotly_chart(px.bar(ag, x="closed_date_pct", y="agency", orientation="h",
                               hover_data=["requests", "status_closed_pct"],
                               labels={"closed_date_pct": "% with a closed date"}), width="stretch")
with col2:
    st.write("By borough")
    st.plotly_chart(px.bar(bo, x="closed_date_pct", y="borough", orientation="h", hover_data=["requests"],
                           labels={"closed_date_pct": "% with a closed date"}), width="stretch")
st.caption(f"Agencies with at least {MIN_REQUESTS} requests. For some agencies (DHS) the status says Closed but the closed date "
           "is missing, so a low rate can be a recording gap, not open work. Closure is not a measure of satisfaction or quality.")
