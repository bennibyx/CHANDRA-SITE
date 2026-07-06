"""
CHANDRASITE Dashboard — Setup and Dashboard Foundation
Placeholder Streamlit shell. Real outputs from the Stage 3 pipeline
(Ice Volume Estimation -> Scientific Confidence Analysis ->
Landing + Traverse Feasibility -> Mission Energy Assessment ->
Uncertainty Quantification -> Mission Intelligence Engine ->
Mission Recommendation Report) will populate this once the
shared JSON contract (see schema.json / sample_output.json) is wired in.
"""

import json
from pathlib import Path

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="CHANDRASITE — Lunar Ice Mission Dashboard", layout="wide")

SAMPLE_PATH = Path(__file__).parent / "sample_output.json"


def load_data():
    """Load pipeline output JSON. Falls back to placeholder data if not present yet."""
    if SAMPLE_PATH.exists():
        with open(SAMPLE_PATH, "r") as f:
            return json.load(f)
    return {
        "ice_deposits": [
            {
                "id": 1,
                "area_m2": 8640,
                "confidence": 0.87,
                "centroid": [-84.68, 77.0],
                "cpr_mean": 0.93,
                "dop_mean": 0.09,
            }
        ],
        "landing_site": {
            "coordinates": [-84.681, 77.05],
            "safety_score": 91,
            "halo_risk": False,
        },
        "rover_path": {
            "waypoints": [[-84.681, 77.05], [-84.678, 77.02]],
            "total_distance_m": 1240,
            "battery_at_rim_pct": 94,
            "charging_waypoint": [-84.679, 77.03],
            "feasibility_score": 0.87,
        },
    }


data = load_data()

st.title("🌗 CHANDRASITE — Faustini Crater Mission Dashboard")
st.caption("Rim-Sentry concept · Bayesian multi-instrument ice fusion · Placeholder shell (data not yet live)")

# ---- Top metric row ----
col1, col2, col3, col4 = st.columns(4)
col1.metric("Ice Deposits Detected", len(data["ice_deposits"]))
col2.metric("Landing Safety Score", f'{data["landing_site"]["safety_score"]}/100')
col3.metric("Rover Feasibility", f'{data["rover_path"]["feasibility_score"]*100:.0f}%')
col4.metric("Battery at Rim", f'{data["rover_path"]["battery_at_rim_pct"]}%')

st.divider()

# ---- Placeholder map ----
left, right = st.columns([2, 1])

with left:
    st.subheader("Site Map (placeholder)")
    fig = go.Figure()

    # ice deposit centroids
    ice_lats = [d["centroid"][0] for d in data["ice_deposits"]]
    ice_lons = [d["centroid"][1] for d in data["ice_deposits"]]
    fig.add_trace(go.Scatter(
        x=ice_lons, y=ice_lats, mode="markers",
        marker=dict(size=14, color="lightblue", symbol="diamond"),
        name="Ice deposits",
    ))

    # landing site
    ls = data["landing_site"]["coordinates"]
    fig.add_trace(go.Scatter(
        x=[ls[1]], y=[ls[0]], mode="markers",
        marker=dict(size=18, color="orange", symbol="star"),
        name="Landing site",
    ))

    # rover path
    wp = data["rover_path"]["waypoints"]
    fig.add_trace(go.Scatter(
        x=[p[1] for p in wp], y=[p[0] for p in wp], mode="lines+markers",
        line=dict(color="lime", width=2),
        name="Rover traverse",
    ))

    fig.update_layout(
        xaxis_title="Longitude", yaxis_title="Latitude",
        template="plotly_dark", height=500,
        legend=dict(orientation="h"),
    )
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Ice Deposit Table")
    df = pd.DataFrame(data["ice_deposits"])
    st.dataframe(df, use_container_width=True)

    st.subheader("Traverse Summary")
    st.write(f'Total distance: **{data["rover_path"]["total_distance_m"]} m**')
    st.write(f'Charging waypoint: **{data["rover_path"]["charging_waypoint"]}**')
    st.write(f'Halo risk at landing site: **{data["landing_site"]["halo_risk"]}**')

st.divider()
st.info(
    "This is the Stage 4 dashboard shell. Ice Volume Estimation, Confidence Analysis, "
    "Feasibility, Energy Assessment, Uncertainty Quantification, and the Mission "
    "Intelligence Engine will feed this via the shared JSON contract in schema.json."
)
