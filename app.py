import streamlit as st
import plotly.express as px
import pandas as pd
import json

st.set_page_config(
    page_title="CHANDRA-SITE Mission Dashboard",
    layout="wide"
)

st.title("🌕 CHANDRA-SITE Mission Intelligence Dashboard")

st.markdown("### Stage 3 Mission Planning Dashboard")

# ------------------------------
# Load JSON
# ------------------------------

with open("sample_data.json") as f:
    data = json.load(f)

# ------------------------------
# Metrics
# ------------------------------

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Ice Deposits",
    len(data["ice_deposits"])
)

col2.metric(
    "Safety Score",
    data["landing_site"]["safety_score"]
)

col3.metric(
    "Feasibility",
    data["rover_path"]["feasibility_score"]
)

col4.metric(
    "Battery",
    str(data["rover_path"]["battery_at_rim_pct"])+"%"
)

st.divider()

# ------------------------------
# Placeholder Map
# ------------------------------

st.subheader("Mission Map")

df = pd.DataFrame({
    "Latitude":[-89.1,-89.3,-89.2],
    "Longitude":[45.2,45.6,45.8],
    "Type":["Ice","Landing","Waypoint"]
})

fig = px.scatter(
    df,
    x="Longitude",
    y="Latitude",
    color="Type",
    size=[20,25,15]
)

st.plotly_chart(fig,use_container_width=True)

st.divider()

st.subheader("Loaded JSON")

st.json(data)
