"""Full league standings, sortable and filterable by conference/division."""

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dashboard.data import load_standings

st.set_page_config(page_title="Standings", page_icon="🏒", layout="wide")
st.title("Standings")

standings = load_standings()
if standings.empty:
    st.info("No standings data yet -- go to Home and click 'Refresh all data'.")
    st.stop()

conf_col, div_col = st.columns(2)
conferences = ["All"] + sorted(standings["conference_name"].dropna().unique().tolist()) if "conference_name" in standings else ["All"]
divisions = ["All"] + sorted(standings["division_name"].dropna().unique().tolist()) if "division_name" in standings else ["All"]

with conf_col:
    conference = st.selectbox("Conference", conferences)
with div_col:
    division = st.selectbox("Division", divisions)

filtered = standings.copy()
if conference != "All":
    filtered = filtered[filtered["conference_name"] == conference]
if division != "All":
    filtered = filtered[filtered["division_name"] == division]

filtered = filtered.sort_values("points", ascending=False)

display_cols = [
    "team_abbrev", "wins", "losses", "ot_losses", "points", "point_pctg",
    "goal_for", "goal_against", "goal_differential", "streak_code", "streak_count",
]
display_cols = [c for c in display_cols if c in filtered.columns]

st.dataframe(
    filtered[display_cols],
    column_config={
        "team_abbrev": "Team", "wins": "W", "losses": "L", "ot_losses": "OTL",
        "points": "PTS", "point_pctg": st.column_config.NumberColumn("PT%", format="%.3f"),
        "goal_for": "GF", "goal_against": "GA", "goal_differential": "DIFF",
        "streak_code": "Streak", "streak_count": "#",
    },
    hide_index=True,
    use_container_width=True,
)

st.subheader("Points by team")
fig = px.bar(
    filtered.sort_values("points"), x="points", y="team_abbrev", orientation="h",
    labels={"points": "Points", "team_abbrev": "Team"}, height=max(400, len(filtered) * 22),
)
st.plotly_chart(fig, use_container_width=True)
