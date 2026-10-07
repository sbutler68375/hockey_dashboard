"""Per-team profile: season totals, standings position, and a rolling
win-percentage trend chart over the season."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dashboard.data import (
    load_completed_games,
    load_player_stats,
    load_standings,
    load_team_season_stats,
    page_header,
    record_text,
    selected_team,
    team_results,
)
from dashboard.images import player_headshot_url, team_logo_url
from dashboard.style import COLORS, apply_theme, result_style, section_label, style_chart
from src.features.team_form import add_rolling_form_features, build_team_game_log

# Form chart settings.
FORM_WINDOW = 10           # games per rolling win % point
MIN_GAMES_FOR_TREND = 20   # fewer full-window points than this makes the slope noise
TREND_FLAT_POINTS = 5      # trend changes smaller than this (pct points) read as "flat"

# Special-teams arrows: last-10 changes smaller than this (3 pct points, about
# one power-play goal) show as "Steady" -- over ~30 chances that's just noise.
SPECIAL_TEAMS_STEADY_BAND = 0.03

st.set_page_config(page_title="Team", page_icon="🏒", layout="wide")
apply_theme()
season = page_header("Team")

team = selected_team()
if team is None:
    st.info("Choose a team with the logo button in the top-right corner to see its profile.")
    st.stop()

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

    # Special teams: PP % and PK % with the team's league rank (higher is
    # better for both), plus a green/red arrow for whether the last 10 games
    # beat the season rate. Older databases may not have these columns yet.
    special_columns = {"power_play_pct", "penalty_kill_pct", "power_play_pct_last_10", "penalty_kill_pct_last_10"}
    if special_columns <= set(season_stats.columns) and pd.notna(ts["power_play_pct"]):
        # With 10 or fewer games played, "last 10" is the whole season -- nothing to compare.
        has_trend = int(row["games_played"]) > 10
        with st.container(border=True):
            section_label("Special teams")
            sp1, sp2, _, _ = st.columns(4)
            for col, label, column in [
                (sp1, "Power play %", "power_play_pct"),
                (sp2, "Penalty kill %", "penalty_kill_pct"),
            ]:
                ranks = season_stats[column].rank(ascending=False, method="min")
                rank = int(ranks[season_stats["team_abbrev"] == team].iloc[0])
                suffix = "th" if 11 <= rank % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(rank % 10, "th")
                last_10 = ts[f"{column}_last_10"]
                with col:
                    change = last_10 - ts[column] if pd.notna(last_10) else None
                    if has_trend and change is not None and abs(change) >= SPECIAL_TEAMS_STEADY_BAND:
                        # A leading "-" makes Streamlit show a red down arrow; "+" a green up one.
                        st.metric(label, f"{ts[column]:.1%}", f"{change:+.1%} last 10 games ({last_10:.1%})")
                    elif has_trend and change is not None:
                        st.metric(label, f"{ts[column]:.1%}", f"Steady last 10 games ({last_10:.1%})", delta_color="off", delta_arrow="off")
                    else:
                        st.metric(label, f"{ts[column]:.1%}", "Trend after 10+ games", delta_color="off", delta_arrow="off")
                    st.caption(f"{rank}{suffix} of {ranks.notna().sum()} in NHL")

games = load_completed_games(season, game_type=2)
team_log = build_team_game_log(games)
form = add_rolling_form_features(team_log)
team_form = form[form["team_abbrev"] == team].sort_values("game_date")

if team_form.empty:
    st.info("No game log available for this team yet.")
else:
    with st.container(border=True):
        section_label("Form")
        # Plot ACTUAL (unshifted) rolling win% -- the shifted version used
        # for model training intentionally excludes each game's own result,
        # which would look one game "behind" here.
        form_df = team_form.sort_values("game_date").reset_index(drop=True).copy()
        form_df["game_number"] = range(1, len(form_df) + 1)
        form_df["game_date"] = pd.to_datetime(form_df["game_date"])
        # NaN until game FORM_WINDOW, so every plotted point really is a
        # full 10-game average (a 1-3 game "average" swings to 0%/100%).
        form_df["form"] = form_df["win"].rolling(FORM_WINDOW).mean()
        season_avg = form_df["win"].mean()
        full = form_df.dropna(subset=["form"])

        fig = go.Figure()
        hover = "Game %{x} (%{customdata[0]}, vs %{customdata[1]})<br>%{y:.0%}<extra></extra>"
        if not full.empty:
            st.markdown(f"###### Win % over the last {FORM_WINDOW} games, {team}")
            fig.add_scatter(
                x=full["game_number"], y=full["form"], mode="lines+markers",
                name=f"{FORM_WINDOW}-game win %", line=dict(color=COLORS["accent"], width=2),
                customdata=full[["game_date", "opponent"]].assign(
                    game_date=full["game_date"].dt.strftime("%b %d")
                ).to_numpy(),
                hovertemplate=hover,
            )
        else:
            # Too early in the season for a 10-game average -- show the
            # running season win % instead.
            st.markdown(f"###### Win % so far, {team}")
            fig.add_scatter(
                x=form_df["game_number"], y=form_df["win"].expanding().mean(), mode="lines+markers",
                name="Win % so far", line=dict(color=COLORS["accent"], width=2),
                customdata=form_df[["game_date", "opponent"]].assign(
                    game_date=form_df["game_date"].dt.strftime("%b %d")
                ).to_numpy(),
                hovertemplate=hover,
            )

        # Season average as a flat reference line -- the trend line below
        # shows direction, this shows the overall level.
        x_range = [form_df["game_number"].min(), form_df["game_number"].max()]
        fig.add_scatter(
            x=x_range, y=[season_avg, season_avg], mode="lines",
            name=f"Season average ({season_avg:.0%})", hoverinfo="skip",
            line=dict(color=COLORS["text_muted"], dash="dot", width=1),
        )

        # Linear trend line: least-squares fit of 10-game win % against game
        # number (not date, so schedule breaks don't count as time passing).
        if len(form_df) >= MIN_GAMES_FOR_TREND:
            slope, intercept = np.polyfit(full["game_number"], full["form"], 1)
            trend = (slope * full["game_number"] + intercept).clip(0, 1)
            fig.add_scatter(
                x=full["game_number"], y=trend, mode="lines", name="Trend", hoverinfo="skip",
                line=dict(color="#f59e0b", dash="dash", width=2),
            )
            start, end = trend.iloc[0], trend.iloc[-1]
            if abs(end - start) * 100 < TREND_FLAT_POINTS:
                trend_note = (
                    f"Trend: roughly flat -- form held around {season_avg:.0%} "
                    f"(trend line {start:.0%} to {end:.0%})."
                )
            else:
                direction = "up" if slope > 0 else "down"
                trend_note = (
                    f"Trend: {direction} about {abs(slope) * 10 * 100:.1f} percentage points "
                    f"per 10 games ({start:.0%} to {end:.0%})."
                )
        elif full.empty:
            trend_note = (
                f"The {FORM_WINDOW}-game line starts at game {FORM_WINDOW}, and the trend line "
                f"once the team has played {MIN_GAMES_FOR_TREND} games."
            )
        else:
            trend_note = f"A trend line appears once the team has played {MIN_GAMES_FOR_TREND} games."

        fig.update_xaxes(title="Game #")
        fig.update_yaxes(title="Win %", range=[0, 1], tickformat=".0%")
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
        st.plotly_chart(style_chart(fig), width="stretch")
        st.caption(trend_note)

    with st.container(border=True):
        recent = team_results(games, team).head(10)
        section_label(f"Last 10 games ({record_text(recent)})")
        st.dataframe(
            recent[["game_date", "opponent", "home_away", "result"]]
            .style.map(result_style, subset=["result"]),
            column_config={
                "game_date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                "opponent": "Opponent", "home_away": "Home/Away",
                "result": f"Result ({team}-opp)",
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

            # Starter and backup = the two goalies with the most starts (ties
            # broken by games played, then ice time). Picking by save % instead
            # let a goalie who mopped up part of one game outrank the real tandem.
            if not goalies.empty:
                tandem = goalies.sort_values(
                    ["games_started", "games_played", "goalie_time_on_ice_seconds"], ascending=False
                ).head(2)
                # The tandem's better save % gets the same green highlight as the
                # skater leaders; the other stays gray (both green on a tie).
                best_save_pct = tandem["save_pctg"].max()
                goalie_cols = st.columns(3)
                for col, role, (_, goalie) in zip(goalie_cols, ["Starter", "Backup"], tandem.iterrows()):
                    save_pct = f"{goalie['save_pctg']:.3f}" if pd.notna(goalie["save_pctg"]) else "n/a"
                    starts = int(goalie["games_started"])
                    is_better = pd.notna(goalie["save_pctg"]) and goalie["save_pctg"] == best_save_pct
                    with col:
                        st.image(player_headshot_url(goalie["player_id"], team, season), width=88)
                        st.metric(
                            f"{role} goalie",
                            f"{goalie['first_name']} {goalie['last_name']}",
                            f"{save_pct} SV% · {starts} start{'' if starts == 1 else 's'}",
                            delta_color="normal" if is_better else "off",
                        )

            st.caption(
                "Player numbers are season totals, not recent-game trends -- this "
                "project only collects per-season player stats, not per-game logs, "
                "so a true 'hot streak' isn't buildable at the player level yet."
            )
