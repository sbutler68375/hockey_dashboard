"""Player stats: model ratings (who's good right now, overrated, underrated,
playing better or worse -- src/models/player_ratings.py), then filter by
type, sort by any stat, see league leaders."""

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dashboard.data import (
    load_player_ratings,
    load_player_stats,
    page_header,
    selected_team,
    team_display_name,
)
from dashboard.images import player_headshot_url
from dashboard.ratings import model_explainer, verdict_style
from dashboard.style import apply_theme, card, section_label, style_chart
from src.models import player_ratings as player_model

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

# Model ratings lists: how many players each shows league-wide (a team's
# list shows all of its players that qualify).
LEAGUE_LIST_LENGTH = 10

MODEL_PREDICTS = "each skater's points per game over his next 20 games"

RATING_COLUMNS = {
    "player_name": "Player", "team_abbrev": "Team", "position_code": "Pos", "games_played": "GP",
    "points_per_game": st.column_config.NumberColumn("P/GP", format="%.2f"),
    "expected_points_per_game": st.column_config.NumberColumn(
        "Expected P/GP", format="%.2f", help="The model's estimate of his true scoring rate."),
    "verdict": "Verdict", "trend": "Lately",
    "shooting_pct": st.column_config.NumberColumn("Sh%", format="%.1f%%"),
    "toi_per_game": st.column_config.NumberColumn("TOI", format="%.1f", help="Ice time per game, minutes."),
}


def ratings_table(df, season: int, extra: dict | None = None) -> None:
    """A player ratings table with headshots and colored verdict/trend words."""
    columns = {**RATING_COLUMNS, **(extra or {})}
    df = df.assign(
        headshot=[player_headshot_url(p, t, season) for p, t in zip(df["player_id"], df["team_abbrev"])],
        shooting_pct=df["shooting_pct"] * 100,
        trend=df["trend"].fillna("—"),  # no trend before 20 games
    )
    st.dataframe(
        df[["headshot", *columns]].style.map(verdict_style, subset=["verdict", "trend"]),
        column_config={"headshot": st.column_config.ImageColumn(""), **columns},
        hide_index=True, width="stretch",
    )


def model_ratings(season: int, team: str | None) -> None:
    """The model ratings card: one tab per question, league-wide or for one team."""
    ratings = load_player_ratings(season)
    with card("model_ratings"):
        section_label("Model ratings -- skaters")
        if ratings.empty:
            st.info("No model ratings yet -- go to Home and click 'Refresh all data'.")
            return
        rated = ratings[ratings["qualified"] == 1]
        if team is not None:
            rated = rated[rated["team_abbrev"] == team]
        limit = LEAGUE_LIST_LENGTH if team is None else len(rated)
        gap = rated["points_percentile"] - rated["expected_percentile"]
        change = {"form_change": st.column_config.NumberColumn(
            "Last 10 vs season", format="%+.2f", help="Expected points per game, last 10 games vs whole season.")}

        tabs = st.tabs(["Best right now", "Overrated", "Underrated", "Playing better", "Playing worse"])
        lists = [
            (rated.sort_values("expected_points_per_game", ascending=False),
             "The highest expected points per game -- who the model trusts most to produce.", None, None),
            (rated[rated["verdict"] == "Overrated"].assign(gap=gap).sort_values("gap", ascending=False),
             "Ranked far higher by points per game than by the model -- usually a hot shooting % "
             "or a small role producing more than it normally does.",
             "No overrated skaters right now -- points mostly match how they've played.", None),
            (rated[rated["verdict"] == "Underrated"].assign(gap=gap).sort_values("gap"),
             "Ranked far higher by the model than by points per game -- getting the ice time "
             "and shots, but the points haven't come yet.",
             "No underrated skaters right now -- points mostly match how they've played.", None),
            (rated[rated["trend"] == "Playing better"].sort_values("form_change", ascending=False),
             "His last 10 games rate well above his season as a whole.",
             f"Nobody yet -- shows up after {2 * player_model.RECENT_GAMES} games.", change),
            (rated[rated["trend"] == "Playing worse"].sort_values("form_change"),
             "His last 10 games rate well below his season as a whole.",
             f"Nobody yet -- shows up after {2 * player_model.RECENT_GAMES} games.", change),
        ]
        for tab, (rows, caption, empty, extra) in zip(tabs, lists):
            with tab:
                if rows.empty:
                    st.caption(empty or "No qualified skaters yet.")
                else:
                    st.caption(caption)
                    ratings_table(rows.head(limit), season, extra)
        st.caption(f"Rated: skaters with {player_model.MIN_GAMES}+ games and at least "
                   f"{player_model.QUALIFY_SHARE:.0%} of the most games anyone has played. "
                   "Goalies aren't rated.")
        model_explainer(player_model.SPEC.name, MODEL_PREDICTS, player_model.FEATURE_LABELS)


st.set_page_config(page_title="Players", page_icon="🏒", layout="wide", initial_sidebar_state="expanded")
apply_theme()
# Title names the team picked with the header's logo button, or the whole league.
title_team = team_display_name(selected_team()) if selected_team() else "NHL"
season = page_header(f"Player Stats · {title_team}")

model_ratings(season, selected_team())

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
