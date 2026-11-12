import streamlit as st

import common

MIN_CASES = 100

f = common.setup("Complaint priorities")
st.caption("Analyst task 15.")

st.subheader("Frequent and slow complaint types")
by_type = common.q("""
    SELECT complaint_type, COUNT(resolution_hours) AS n_valid,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY resolution_hours) AS median_h
    FROM service_requests WHERE {where} AND resolution_hours IS NOT NULL
    GROUP BY 1 HAVING COUNT(resolution_hours) >= :min_n ORDER BY median_h DESC""", f, {"min_n": MIN_CASES})

if len(by_type) >= 4:
    vol_cut = by_type["n_valid"].quantile(0.75)
    med_cut = by_type["median_h"].quantile(0.75)
    both = by_type[(by_type["n_valid"] >= vol_cut) & (by_type["median_h"] >= med_cut)]
    st.write(f"Complaint types in the top quarter for both volume (at least {vol_cut:,.0f} valid cases) "
             f"and median time (at least {med_cut:,.0f} hours):")
    st.dataframe(both[["complaint_type", "n_valid", "median_h"]].round(1), width="stretch", hide_index=True)
    st.caption(f"Only complaint types with at least {MIN_CASES} valid cases are compared. "
               "A pattern in recorded times, not proof of poor service.")
else:
    st.info("Too few complaint types with enough valid cases. Widen the filters.")
