import plotly.express as px
import streamlit as st

import common

f = common.setup("Geography and closure (tasks 13-14)")

# ---- task 13 ----
st.subheader("Task 13: geographic concentration")
pts = common.q("""
    SELECT latitude, longitude, borough FROM service_requests
    WHERE {where} AND NOT flag_missing_coordinates""", f)
total = common.q("SELECT COUNT(*) AS n FROM service_requests WHERE {where}", f).loc[0, "n"]
st.write(f"{len(pts):,} of {total:,} filtered requests have usable coordinates ({len(pts) / total * 100:.1f}%). The rest are left off the map.")

if pts.empty:
    st.info("No coordinates for these filters. Borough totals are on the Volume and mix page.")
else:
    fig = px.density_map(pts, lat="latitude", lon="longitude", radius=6, zoom=9.3,
                         center={"lat": 40.72, "lon": -73.95}, map_style="open-street-map", height=550)
    fig.update_layout(margin={"l": 0, "r": 0, "t": 0, "b": 0})
    st.plotly_chart(fig, width="stretch")

    hot = common.q("""
        SELECT ROUND(latitude::numeric, 2) AS lat_cell, ROUND(longitude::numeric, 2) AS lon_cell,
               COUNT(*) AS requests,
               MODE() WITHIN GROUP (ORDER BY borough) AS borough,
               MODE() WITHIN GROUP (ORDER BY complaint_type) AS top_complaint
        FROM service_requests WHERE {where} AND NOT flag_missing_coordinates
        GROUP BY 1, 2 ORDER BY requests DESC LIMIT 10""", f)
    st.write("Busiest grid cells (about 1 km each)")
    st.dataframe(hot, width="stretch", hide_index=True)
    st.caption("One exact point in the Bronx (655 East 230 Street) holds over 1,600 requests, mostly Illegal Parking. "
               "It looks like a default location rather than real concentration, so treat the map hot spots with care.")

# ---- task 14 ----
st.subheader("Task 14: recorded closure rate")
min_rows = st.sidebar.slider("Minimum requests per agency", 50, 1000, 500, step=50, key="min_rows")
col1, col2 = st.columns(2)
ag = common.q("""
    SELECT agency, COUNT(*) AS requests,
           ROUND(100.0 * SUM(is_closed) / COUNT(*), 1) AS closed_date_pct,
           ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'Closed') / COUNT(*), 1) AS status_closed_pct
    FROM service_requests WHERE {where}
    GROUP BY 1 HAVING COUNT(*) >= :min_rows ORDER BY closed_date_pct""", f, {"min_rows": min_rows})
bo = common.q("""
    SELECT borough, COUNT(*) AS requests, ROUND(100.0 * SUM(is_closed) / COUNT(*), 1) AS closed_date_pct
    FROM service_requests WHERE {where} GROUP BY 1 ORDER BY closed_date_pct""", f)
with col1:
    st.write("By agency")
    if ag.empty:
        st.info("No agency has enough requests. Lower the minimum in the sidebar.")
    else:
        long = ag.melt(id_vars=["agency", "requests"], value_vars=["closed_date_pct", "status_closed_pct"],
                       var_name="measure", value_name="percent")
        long["measure"] = long["measure"].map({"closed_date_pct": "closed date recorded", "status_closed_pct": "status says Closed"})
        st.plotly_chart(px.bar(long, x="percent", y="agency", color="measure", barmode="group", orientation="h",
                               hover_data=["requests"]), width="stretch")
with col2:
    st.write("By borough")
    st.plotly_chart(px.bar(bo, x="closed_date_pct", y="borough", orientation="h", hover_data=["requests"]), width="stretch")
st.caption("Recorded closure is the share of requests with a closed date. For some agencies (DHS in the full data) the status says "
           "Closed but the date is missing, so a low rate can be a recording gap, not open work. It is not a measure of satisfaction or quality.")
