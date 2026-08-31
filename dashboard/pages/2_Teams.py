"""Per-team profile: season totals, standings position, and a rolling
win-percentage trend chart over the season."""

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dashboard.data import default_season, load_completed_games, load_standings, load_team_season_stats, team_list
from src.features.team_form import add_rolling_form_features, build_team_game_log

st.set_page_config(page_title="Teams", page_icon="🏒", layout="wide")
st.title("Team Profile")

team = st.selectbox("Select a team", team_list())

standings = load_standings()
team_standing = standings[standings["team_abbrev"] == team] if not standings.empty else standings
season_stats = load_team_season_stats(default_season())
team_season = season_stats[season_stats["team_abbrev"] == team] if not season_stats.empty else season_stats

if team_standing.empty:
    st.info("No standings data for this team yet -- go to Home and click 'Refresh all data'.")
    st.stop()

row = team_standing.iloc[0]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Record", f"{row['wins']}-{row['losses']}-{row['ot_losses']}")
c2.metric("Points", int(row["points"]))
c3.metric("Goals For", int(row["goal_for"]))
c4.metric("Goals Against", int(row["goal_against"]))
c5.metric("Streak", f"{row.get('streak_code', '')}{row.get('streak_count', '')}")

if not team_season.empty:
    st.subheader("Season totals")
    ts = team_season.iloc[0]
    t1, t2, t3, t4 = st.columns(4)
    t1.metric("Team shots", int(ts["total_shots"]))
    t2.metric("PP goals", int(ts["total_powerplay_goals"]))
    t3.metric("Save %", f"{ts['team_save_pct']:.3f}" if ts["team_save_pct"] == ts["team_save_pct"] else "n/a")
    t4.metric("Shutouts", int(ts["total_shutouts"]))

st.divider()
st.subheader(f"{team} rolling win % over the season")

games = load_completed_games(game_type=2)
team_log = build_team_game_log(games)
form = add_rolling_form_features(team_log)
team_form = form[form["team_abbrev"] == team].sort_values("game_date")

if team_form.empty:
    st.info("No game log available for this team yet.")
else:
    # Plot ACTUAL (unshifted) rolling win% for a readable trend line --
    # the shifted version used for model training intentionally excludes
    # each game's own result, which would look one game "behind" here.
    team_form_display = team_form.copy()
    team_form_display["actual_win_pct_last_10"] = (
        team_form_display["win"].rolling(10, min_periods=1).mean()
    )
    fig = px.line(
        team_form_display, x="game_date", y="actual_win_pct_last_10",
        labels={"game_date": "Date", "actual_win_pct_last_10": "Win % (last 10 games)"},
        markers=True,
    )
    fig.update_yaxes(range=[0, 1])
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Recent games")
    recent = team_form.sort_values("game_date", ascending=False).head(10)
    recent_display = recent[["game_date", "opponent", "is_home", "goals_for", "goals_against", "win"]].copy()
    recent_display["is_home"] = recent_display["is_home"].map({1: "Home", 0: "Away"})
    recent_display["win"] = recent_display["win"].map({1: "W", 0: "L"})
    st.dataframe(
        recent_display,
        column_config={
            "game_date": "Date", "opponent": "Opponent", "is_home": "Venue",
            "goals_for": "GF", "goals_against": "GA", "win": "Result",
        },
        hide_index=True,
        use_container_width=True,
    )
