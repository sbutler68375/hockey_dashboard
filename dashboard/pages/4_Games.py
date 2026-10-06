"""Game history: browse and filter completed games."""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dashboard.data import load_completed_games, page_header, team_selectbox
from dashboard.style import apply_theme, section_label

st.set_page_config(page_title="Games", page_icon="🏒", layout="wide")
apply_theme()
season = page_header("Games")

game_type_labels = {2: "Regular season", 3: "Playoffs", 1: "Preseason"}
col1, col2 = st.columns(2)
with col1:
    game_type = st.selectbox(
        "Game type", options=list(game_type_labels.keys()),
        format_func=lambda v: game_type_labels[v], index=0,
    )

games = load_completed_games(season, game_type=game_type)
if games.empty:
    st.info("No games for this filter yet -- go to Home and click 'Refresh all data'.")
    st.stop()

with col2:
    team_filter = team_selectbox("Team", key="games_page_team")
if team_filter is not None:
    games = games[(games["home_team"] == team_filter) | (games["away_team"] == team_filter)]

games_display = games.sort_values("game_date", ascending=False).copy()
games_display["matchup"] = games_display["away_team"] + " @ " + games_display["home_team"]
games_display["score"] = (
    games_display["away_score"].astype(int).astype(str) + " - " + games_display["home_score"].astype(int).astype(str)
)

with st.container(border=True):
    section_label(f"{len(games_display)} games")
    st.dataframe(
        games_display[["game_date", "matchup", "score", "venue"]],
        column_config={
            "game_date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
            "matchup": "Matchup", "score": "Score (away-home)", "venue": "Venue",
        },
        hide_index=True,
        width="stretch",
    )
