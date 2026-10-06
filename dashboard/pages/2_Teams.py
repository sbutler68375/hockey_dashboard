"""Per-team profile: season totals, standings position, and a rolling
win-percentage trend chart over the season."""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dashboard.data import (
    load_completed_games,
    load_player_stats,
    load_standings,
    load_team_season_stats,
    page_header,
    team_selectbox,
)
from dashboard.images import player_headshot_url, team_logo_url
from dashboard.style import apply_theme, section_label, style_chart
from src.features.team_form import add_rolling_form_features, build_team_game_log

st.set_page_config(page_title="Teams", page_icon="🏒", layout="wide")
apply_theme()
season = page_header("Team Profile")

team = team_selectbox("Select a team", key="teams_page_team", include_all=False)

standings = load_standings(season)
team_standing = standings[standings["team_abbrev"] == team] if not standings.empty else standings
season_stats = load_team_season_stats(season)
team_season = season_stats[season_stats["team_abbrev"] == team] if not season_stats.empty else season_stats

if team_standing.empty:
    st.info("No standings data for this team yet -- go to Home and click 'Refresh all data'.")
    st.stop()

row = team_standing.iloc[0]

with st.container(border=True):
    logo_col, name_col = st.columns([1, 8])
    with logo_col:
        st.image(team_logo_url(team), width=64)
    with name_col:
        st.markdown(f"### {team}")
        st.caption(f"{row.get('conference_name', '')} Conference · {row.get('division_name', '')} Division")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Record", f"{row['wins']}-{row['losses']}-{row['ot_losses']}")
    c2.metric("Points", int(row["points"]))
    c3.metric("Goals For", int(row["goal_for"]))
    c4.metric("Goals Against", int(row["goal_against"]))
    c5.metric("Streak", f"{row.get('streak_code', '')}{row.get('streak_count', '')}")

if not team_season.empty:
    with st.container(border=True):
        section_label("Season totals")
        ts = team_season.iloc[0]
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Team shots", int(ts["total_shots"]))
        t2.metric("PP goals", int(ts["total_powerplay_goals"]))
        t3.metric("Save %", f"{ts['team_save_pct']:.3f}" if ts["team_save_pct"] == ts["team_save_pct"] else "n/a")
        t4.metric("Shutouts", int(ts["total_shutouts"]))

games = load_completed_games(season, game_type=2)
team_log = build_team_game_log(games)
form = add_rolling_form_features(team_log)
team_form = form[form["team_abbrev"] == team].sort_values("game_date")

if team_form.empty:
    st.info("No game log available for this team yet.")
else:
    with st.container(border=True):
        section_label("Form")
        st.markdown(f"###### Win % (last 10 games), {team}")
        # Plot ACTUAL (unshifted) rolling win% for a readable trend line --
        # the shifted version used for model training intentionally excludes
        # each game's own result, which would look one game "behind" here.
        team_form_display = team_form.copy()
        team_form_display["actual_win_pct_last_10"] = (
            team_form_display["win"].rolling(10, min_periods=1).mean()
        )
        fig = px.line(
            team_form_display, x="game_date", y="actual_win_pct_last_10",
            labels={"game_date": "Date", "actual_win_pct_last_10": "Win %"},
            markers=True,
        )
        fig.update_yaxes(range=[0, 1])
        st.plotly_chart(style_chart(fig), width="stretch")

    with st.container(border=True):
        section_label("Recent games")
        recent = team_form.sort_values("game_date", ascending=False).head(10)
        recent_display = recent[["game_date", "opponent", "is_home", "goals_for", "goals_against", "win"]].copy()
        recent_display["is_home"] = recent_display["is_home"].map({1: "Home", 0: "Away"})
        recent_display["win"] = recent_display["win"].map({1: "W", 0: "L"})
        st.dataframe(
            recent_display,
            column_config={
                "game_date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                "opponent": "Opponent", "is_home": "Venue",
                "goals_for": "GF", "goals_against": "GA", "win": "Result",
            },
            hide_index=True,
            width="stretch",
        )

    results = team_form.sort_values("game_date")["win"].tolist()

    # Current active streak: how many games in a row ending with the most
    # recent result (win or loss) -- computed from real per-game results.
    current_streak_len = 0
    for w in reversed(results):
        if w == results[-1]:
            current_streak_len += 1
        else:
            break
    current_streak_label = "W" if results[-1] == 1 else "L"

    # Longest win streak of the season so far.
    best_streak = running = 0
    for w in results:
        running = running + 1 if w == 1 else 0
        best_streak = max(best_streak, running)

    # Best 5-game scoring stretch (highest goals scored across any 5
    # consecutive games this season). NaN if fewer than 5 games played.
    best_5game_raw = team_form.sort_values("game_date")["goals_for"].rolling(5).sum().max()
    best_5game_display = f"{int(best_5game_raw)} goals" if pd.notna(best_5game_raw) else "n/a (fewer than 5 games)"

    with st.container(border=True):
        section_label("Recent form")
        s1, s2, s3 = st.columns(3)
        s1.metric("Current streak", f"{current_streak_label}{current_streak_len}")
        s2.metric("Longest win streak", best_streak)
        s3.metric("Best 5-game scoring stretch", best_5game_display)
        st.caption("Computed from this team's actual game-by-game results that season.")

    player_stats = load_player_stats(season)
    team_players = player_stats[player_stats["team_abbrev"] == team] if not player_stats.empty else player_stats
    skaters = team_players[team_players["player_type"] == "skater"]
    goalies = team_players[team_players["player_type"] == "goalie"]

    if not skaters.empty or not goalies.empty:
        with st.container(border=True):
            section_label("Player standouts")

            if not skaters.empty:
                p1, p2, p3 = st.columns(3)
                top_scorer = skaters.loc[skaters["points"].idxmax()]
                top_goals = skaters.loc[skaters["goals"].idxmax()]
                top_plus_minus = skaters.loc[skaters["plus_minus"].idxmax()]

                with p1:
                    st.image(player_headshot_url(top_scorer["player_id"], team, season), width=88)
                    st.metric("Points leader", f"{top_scorer['first_name']} {top_scorer['last_name']}", f"{int(top_scorer['points'])} pts")
                with p2:
                    st.image(player_headshot_url(top_goals["player_id"], team, season), width=88)
                    st.metric("Goals leader", f"{top_goals['first_name']} {top_goals['last_name']}", f"{int(top_goals['goals'])} g")
                with p3:
                    st.image(player_headshot_url(top_plus_minus["player_id"], team, season), width=88)
                    st.metric("Best +/-", f"{top_plus_minus['first_name']} {top_plus_minus['last_name']}", f"{int(top_plus_minus['plus_minus']):+d}")

            if not goalies.empty and goalies["save_pctg"].notna().any():
                best_goalie = goalies.loc[goalies["save_pctg"].idxmax()]
                g1, _, _ = st.columns(3)
                with g1:
                    st.image(player_headshot_url(best_goalie["player_id"], team, season), width=88)
                    st.metric(
                        "Best goalie save %",
                        f"{best_goalie['first_name']} {best_goalie['last_name']}",
                        f"{best_goalie['save_pctg']:.3f}",
                    )

            st.caption(
                "Player numbers are season totals, not recent-game trends -- this "
                "project only collects per-season player stats, not per-game logs, "
                "so a true 'hot streak' isn't buildable at the player level yet."
            )
