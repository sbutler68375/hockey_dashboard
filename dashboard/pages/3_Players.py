"""Player stats: filter by team/type, sort by any stat, see league leaders."""

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dashboard.data import load_player_stats, page_header, selected_team
from dashboard.images import player_headshot_url
from dashboard.style import apply_theme, card, section_label, style_chart

# Stats the page can sort by (drives both the chart and the table), per
# player type, with display labels. First entry is the default.
SORT_STATS = {
    "skater": {
        "points": "Points", "goals": "Goals", "assists": "Assists",
        "plus_minus": "+/-", "shots": "Shots", "games_played": "Games played",
    },
    "goalie": {
        "save_pctg": "Save %", "goals_against_average": "GAA", "wins": "Wins",
        "shutouts": "Shutouts", "losses": "Losses", "games_started": "Games started",
        "games_played": "Games played",
    },
}

# Lower is better for these, so "top" means smallest.
LOWER_IS_BETTER = {"goals_against_average"}

# Rate stats are meaningless over a handful of games (a goalie with one
# 30-save shutout would lead save %), so the chart requires a minimum sample.
RATE_STATS = {"save_pctg", "goals_against_average"}
MIN_GAMES_FOR_RATE_STATS = 5

TABLE_COLUMNS = {
    "skater": ["first_name", "last_name", "team_abbrev", "position_code",
               "games_played", "goals", "assists", "points", "plus_minus", "shots"],
    "goalie": ["first_name", "last_name", "team_abbrev", "games_played", "games_started",
               "wins", "losses", "save_pctg", "goals_against_average", "shutouts"],
}

st.set_page_config(page_title="Players", page_icon="🏒", layout="wide")
apply_theme()
season = page_header("Player Stats")

with card("filters"):
    section_label("Filters")
    col1, col2 = st.columns(2)
    with col1:
        player_type = st.radio(
            "Player type", ["skater", "goalie"], horizontal=True,
            format_func=lambda t: f"{t.capitalize()}s",
        )
    with col2:
        sort_options = SORT_STATS[player_type]
        sort_col = st.selectbox(
            "Sort by", list(sort_options), format_func=sort_options.get,
            key=f"players_sort_{player_type}",  # separate choice per player type
            help="Ranks both the chart and the table by this stat.",
        )
sort_label = sort_options[sort_col]
ascending = sort_col in LOWER_IS_BETTER

players = load_player_stats(season, player_type)
if players.empty:
    st.info("No player data yet -- go to Home and click 'Refresh all data'.")
    st.stop()

team_filter = selected_team()
if team_filter is not None:
    players = players[players["team_abbrev"] == team_filter]

players = players.copy()
players["name"] = players["first_name"] + " " + players["last_name"]

with card("leaders_chart"):
    chart_players = players
    min_games = 0
    if sort_col in RATE_STATS and not players.empty:
        # Early in a season nobody has 5 games yet, so cap the minimum at
        # half the most games anyone has played (rounded up).
        most_games = int(players["games_played"].max())
        min_games = min(MIN_GAMES_FOR_RATE_STATS, -(-most_games // 2))
        chart_players = players[players["games_played"] >= min_games]
    direction = "lowest" if ascending else "top"
    section_label(f"{player_type.capitalize()}s -- {direction} {sort_label}")

    top = chart_players.sort_values(sort_col, ascending=ascending).head(15)
    fig = px.bar(
        top, x=sort_col, y="name", orientation="h", color="team_abbrev",
        labels={sort_col: sort_label, "name": "Player", "team_abbrev": "Team"}, height=500,
    )
    # Best at the top of the chart either way.
    fig.update_yaxes(categoryorder="total descending" if ascending else "total ascending")
    st.plotly_chart(style_chart(fig), width="stretch")
    if min_games > 1:
        st.caption(f"Chart limited to goalies with at least {min_games} games played.")

with card("full_table"):
    section_label(f"Full table -- sorted by {sort_label}")
    display_cols = [c for c in TABLE_COLUMNS[player_type] if c in players.columns]

    players["headshot"] = players.apply(
        lambda r: player_headshot_url(r["player_id"], r["team_abbrev"], season), axis=1
    )
    st.dataframe(
        players[["headshot"] + display_cols].sort_values(sort_col, ascending=ascending),
        column_config={"headshot": st.column_config.ImageColumn("")},
        hide_index=True,
        width="stretch",
    )
