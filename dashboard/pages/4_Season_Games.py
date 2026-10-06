"""Season games: every game the selected team has played this season,
newest first, shown from that team's point of view (opponent, home/away, color-coded result)."""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dashboard.data import (
    current_season,
    load_completed_games,
    page_header,
    record_text,
    season_label,
    selected_team,
    team_display_name,
    team_results,
)
from dashboard.style import apply_theme, result_style, section_label

st.set_page_config(page_title="Season Games", page_icon="🏒", layout="wide")
apply_theme()
season = page_header("Season Games")

team = selected_team()
if team is None:
    st.info("Choose a team with the logo button in the top-right corner to see its games.")
    st.stop()

game_type_labels = {2: "Regular season", 3: "Playoffs", 1: "Preseason"}
col1, _ = st.columns(2)
with col1:
    game_type = st.selectbox(
        "Game type", options=list(game_type_labels.keys()),
        format_func=lambda v: game_type_labels[v], index=0,
    )

games = team_results(load_completed_games(season, game_type=game_type), team)
if games.empty:
    game_kind = {2: "regular-season", 3: "playoff", 1: "preseason"}[game_type]
    yet = " yet" if season == current_season() else ""
    st.info(f"{team_display_name(team)} played no {game_kind} games in {season_label(season)}{yet}.")
    st.stop()

with st.container(border=True):
    section_label(f"{team_display_name(team)} -- {len(games)} games ({record_text(games)})")
    st.dataframe(
        games[["game_date", "opponent", "home_away", "result", "venue"]]
        .style.map(result_style, subset=["result"]),
        column_config={
            "game_date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
            "opponent": "Opponent", "home_away": "Home/Away",
            "result": f"Result ({team}-opp)", "venue": "Venue",
        },
        hide_index=True,
        width="stretch",
    )
