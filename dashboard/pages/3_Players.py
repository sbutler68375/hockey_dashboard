"""Player stats: filter by team/type, sort by any stat, see league leaders."""

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dashboard.data import default_season, load_player_stats, team_list

st.set_page_config(page_title="Players", page_icon="🏒", layout="wide")
st.title("Player Stats")

season = default_season()
col1, col2 = st.columns(2)
with col1:
    player_type = st.radio("Player type", ["skater", "goalie"], horizontal=True)
with col2:
    team_filter = st.selectbox("Team", ["All"] + team_list())

players = load_player_stats(season, player_type)
if players.empty:
    st.info("No player data yet -- go to Home and click 'Refresh all data'.")
    st.stop()

if team_filter != "All":
    players = players[players["team_abbrev"] == team_filter]

if player_type == "skater":
    st.subheader("Top scorers")
    top = players.sort_values("points", ascending=False).head(15)
    fig = px.bar(
        top, x="points", y="last_name", orientation="h", color="team_abbrev",
        labels={"points": "Points", "last_name": "Player"}, height=500,
    )
    fig.update_yaxes(categoryorder="total ascending")
    st.plotly_chart(fig, use_container_width=True)

    display_cols = ["first_name", "last_name", "team_abbrev", "position_code",
                     "games_played", "goals", "assists", "points", "plus_minus", "shots"]
else:
    st.subheader("Goalies by save %")
    top = players[players["games_played"] >= 5].sort_values("save_pctg", ascending=False).head(15)
    fig = px.bar(
        top, x="save_pctg", y="last_name", orientation="h", color="team_abbrev",
        labels={"save_pctg": "Save %", "last_name": "Goalie"}, height=500,
    )
    fig.update_yaxes(categoryorder="total ascending")
    st.plotly_chart(fig, use_container_width=True)

    display_cols = ["first_name", "last_name", "team_abbrev", "games_played", "games_started",
                     "wins", "losses", "save_pctg", "goals_against_average", "shutouts"]

st.divider()
st.subheader("Full table")
display_cols = [c for c in display_cols if c in players.columns]
sort_col = st.selectbox("Sort by", display_cols, index=display_cols.index("points") if "points" in display_cols else 0)
st.dataframe(
    players[display_cols].sort_values(sort_col, ascending=False),
    hide_index=True,
    use_container_width=True,
)
