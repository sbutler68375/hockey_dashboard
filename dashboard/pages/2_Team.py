"""Per-team profile: model rating, season totals, standings position, and a
rolling win-percentage trend chart over the season. With no team picked,
the league-wide model ratings: who's overrated, underrated, and playing
better or worse lately (src/models/team_ratings.py)."""

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
    load_team_rating_history,
    load_team_ratings,
    load_team_season_stats,
    load_team_special_teams_games,
    page_header,
    record_text,
    selected_team,
    team_results,
)
from dashboard.images import player_headshot_url, team_logo_url
from dashboard.ratings import model_explainer, ordinal, verdict_style
from dashboard.style import apply_theme, card, colors, result_style, section_label, style_chart
from src.features.team_form import add_rolling_form_features, build_team_game_log
from src.models import team_ratings as team_model

# Form chart settings.
FORM_WINDOW = 10           # games per rolling win % point
MIN_GAMES_FOR_TREND = 20   # fewer full-window points than this makes the slope noise
TREND_FLAT_POINTS = 5      # trend changes smaller than this (pct points) read as "flat"

# Special-teams arrows: last-10 changes smaller than this (3 pct points, about
# one power-play goal) show as "Steady" -- over ~30 chances that's just noise.
SPECIAL_TEAMS_STEADY_BAND = 0.03


def special_teams_chart(per_game: pd.DataFrame, successes: pd.Series, chances: pd.Series,
                        short_label: str, season_rate: float) -> tuple[go.Figure, str]:
    """Rolling FORM_WINDOW-game success rate (PP % or PK %) by game number, with
    the season rate as a dotted line and a linear trend -- the win % chart's
    layout. Rates are pooled (goals / chances over the window), not an average
    of per-game percentages, so a 1-chance game doesn't count like a 5-chance one.
    Returns the figure and a one-line trend note."""
    df = pd.DataFrame({
        "game_number": range(1, len(per_game) + 1),
        "game_date": pd.to_datetime(per_game["game_date"]).dt.strftime("%b %d").to_numpy(),
        "successes": successes.to_numpy(),
        "chances": chances.to_numpy(),
    })
    window_successes = df["successes"].rolling(FORM_WINDOW).sum()
    window_chances = df["chances"].rolling(FORM_WINDOW).sum()
    df["rate"] = window_successes / window_chances.where(window_chances > 0)
    df["window_text"] = (
        window_successes.astype("Int64").astype(str) + "/" + window_chances.astype("Int64").astype(str)
    )
    full = df.dropna(subset=["rate"])

    fig = go.Figure()
    hover = "Game %{x} (%{customdata[0]})<br>%{y:.1%} (%{customdata[1]})<extra></extra>"
    if not full.empty:
        line_df, name = full, f"{FORM_WINDOW}-game {short_label}"
    else:
        # Too early for a 10-game window -- show the running season rate instead.
        so_far_chances = df["chances"].cumsum()
        df["rate"] = df["successes"].cumsum() / so_far_chances.where(so_far_chances > 0)
        df["window_text"] = df["successes"].cumsum().astype(str) + "/" + so_far_chances.astype(str)
        line_df, name = df.dropna(subset=["rate"]), f"{short_label} so far"
    fig.add_scatter(
        x=line_df["game_number"], y=line_df["rate"], mode="lines+markers", name=name,
        line=dict(color=colors()["accent"], width=2),
        customdata=line_df[["game_date", "window_text"]].to_numpy(), hovertemplate=hover,
    )
    fig.add_scatter(
        x=[df["game_number"].min(), df["game_number"].max()], y=[season_rate, season_rate],
        mode="lines", name=f"Season ({season_rate:.1%})", hoverinfo="skip",
        line=dict(color=colors()["text_muted"], dash="dot", width=1),
    )

    if len(df) >= MIN_GAMES_FOR_TREND and len(full) >= 2:
        slope, intercept = np.polyfit(full["game_number"], full["rate"], 1)
        trend = (slope * full["game_number"] + intercept).clip(0, 1)
        fig.add_scatter(
            x=full["game_number"], y=trend, mode="lines", name="Trend", hoverinfo="skip",
            line=dict(color=colors()["warning"], dash="dash", width=2),
        )
        start, end = trend.iloc[0], trend.iloc[-1]
        if abs(end - start) * 100 < TREND_FLAT_POINTS:
            note = f"Trend: roughly flat ({start:.0%} to {end:.0%})."
        else:
            direction = "up" if slope > 0 else "down"
            note = (f"Trend: {direction} about {abs(slope) * 10 * 100:.1f} percentage points "
                    f"per 10 games ({start:.0%} to {end:.0%}).")
    elif full.empty:
        note = (f"The {FORM_WINDOW}-game line starts at game {FORM_WINDOW}, "
                f"the trend line at game {MIN_GAMES_FOR_TREND}.")
    else:
        note = f"A trend line appears once the team has played {MIN_GAMES_FOR_TREND} games."

    fig.update_xaxes(title="Game #")
    fig.update_yaxes(title=short_label, tickformat=".0%")
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
    return style_chart(fig), note

# PDO (shooting % + save %) this far from the league average reads as luck
# running hot/cold -- about 1.5 percentage points between the two.
PDO_LUCK_BAND = 0.015
# Before this many games, ratings still lean on last season.
EARLY_SEASON_GAMES = 20

MODEL_PREDICTS = "each team's points % over the rest of the season"


def explain_rating(r: pd.Series) -> list[str]:
    """Plain-language reasons behind one team's rating, one sentence each."""
    standings, model = ordinal(int(r["standings_rank"])), ordinal(int(r["model_rank"]))
    if r["verdict"] == "Overrated":
        lines = [f"**Overrated:** {standings} in the standings but {model} by the model -- "
                 "their record is ahead of how they've played."]
    elif r["verdict"] == "Underrated":
        lines = [f"**Underrated:** {standings} in the standings but {model} by the model -- "
                 "they've played better than their record shows."]
    else:
        lines = [f"**Fairly rated:** {standings} in the standings, {model} by the model -- "
                 "their record matches how they've played."]
    pdo_gap = r["pdo"] - r["league_pdo"]
    if pdo_gap >= PDO_LUCK_BAND:
        lines.append(f"Shooting % + save % (PDO) is {r['pdo']:.3f} vs a league average of "
                     f"{r['league_pdo']:.3f} -- running hot, which usually cools off.")
    elif pdo_gap <= -PDO_LUCK_BAND:
        lines.append(f"Shooting % + save % (PDO) is {r['pdo']:.3f} vs a league average of "
                     f"{r['league_pdo']:.3f} -- running cold, which usually bounces back.")
    if r["trend"] == "Playing better":
        lines.append(f"**Playing better lately:** the model rates their last 10 games {abs(r['form_change']):.3f} "
                     f"PT% above their season as a whole ({r['recent_points_pct']:.3f} PT% in those games).")
    elif r["trend"] == "Playing worse":
        lines.append(f"**Playing worse lately:** the model rates their last 10 games {abs(r['form_change']):.3f} "
                     f"PT% below their season as a whole ({r['recent_points_pct']:.3f} PT% in those games).")
    if r["games_played"] < EARLY_SEASON_GAMES and pd.notna(r["prior_points_pct"]):
        lines.append(f"Early season: after {int(r['games_played'])} games the rating still leans on "
                     f"last season ({r['prior_points_pct']:.3f} PT%) and firms up as games are played.")
    return lines


def ratings_table(df: pd.DataFrame, columns: dict) -> None:
    """A ratings table with team logos and colored verdict/trend words."""
    df = df.assign(logo=df["team_abbrev"].map(team_logo_url), trend=df["trend"].fillna("—"))
    style_cols = [c for c in ("verdict", "trend") if c in columns]
    st.dataframe(
        df[["logo", *columns]].style.map(verdict_style, subset=style_cols),
        column_config={"logo": st.column_config.ImageColumn(""), **columns},
        hide_index=True, width="stretch",
    )


def league_ratings(ratings: pd.DataFrame) -> None:
    """The no-team-picked view: every team's model rating."""
    if ratings.empty:
        st.info("No model ratings yet -- go to Home and click 'Refresh all data'.")
        return
    pct = lambda label: st.column_config.NumberColumn(label, format="%.3f")
    if ratings["games_played"].median() < EARLY_SEASON_GAMES:
        st.caption(f"Early season: with about {int(ratings['games_played'].median())} games played, "
                   "ratings still lean on last season and firm up as games are played.")

    with card("ratings_overview"):
        section_label("Record vs how they've played")
        fig = go.Figure()
        # Fit the x-axis to the expected values -- actual records spread much
        # wider early in a season and would squeeze the teams into a clump.
        low = ratings["expected_points_pct"].min() - 0.02
        high = ratings["expected_points_pct"].max() + 0.02
        fig.add_scatter(x=[low, high], y=[low, high], mode="lines", hoverinfo="skip",
                        line=dict(color=colors()["text_muted"], dash="dot", width=1), showlegend=False)
        fig.add_scatter(
            x=ratings["expected_points_pct"], y=ratings["points_pct"], mode="markers+text",
            text=ratings["team_abbrev"], textposition="top center", textfont=dict(size=11),
            showlegend=False, marker=dict(color=colors()["accent"], size=9),
            hovertemplate="%{text}<br>Expected %{x:.3f}<br>Actual %{y:.3f}<extra></extra>",
        )
        fig.update_xaxes(title="Expected points % (model)", tickformat=".3f", range=[low, high])
        fig.update_yaxes(title="Actual points %", tickformat=".3f")
        fig.update_layout(height=520)
        st.plotly_chart(style_chart(fig), width="stretch")
        st.caption("Above the dotted line: a better record than their play suggests. "
                   "Below it: they've played better than their record.")

    columns = {
        "team_abbrev": "Team", "standings_rank": "Standings rank", "model_rank": "Model rank",
        "points_pct": pct("PT%"), "expected_points_pct": pct("Expected PT%"),
    }
    with card("verdicts"):
        section_label("Overrated and underrated")
        over_col, under_col = st.columns(2, gap="large")
        for col, verdict, sort_ascending, empty in [
            (over_col, "Overrated", False, "No team's record is far ahead of its play."),
            (under_col, "Underrated", True, "No team's record is far behind its play."),
        ]:
            with col:
                st.markdown(f"##### {verdict}")
                rows = ratings[ratings["verdict"] == verdict].sort_values("rank_gap", ascending=sort_ascending)
                if rows.empty:
                    st.caption(empty)
                else:
                    ratings_table(rows, columns)
        st.caption(f"Overrated / underrated: {team_model.OVERRATED_RANK_GAP}+ places apart in "
                   "the standings and the model's ranking.")

    with card("trends"):
        section_label("Playing better and worse lately")
        if ratings["trend"].isna().all():
            st.caption(f"Shows up once teams have played {2 * team_model.RECENT_GAMES} games.")
        else:
            better_col, worse_col = st.columns(2, gap="large")
            change = {"form_change": st.column_config.NumberColumn("Last 10 vs season", format="%+.3f"),
                      "recent_points_pct": pct("PT% last 10")}
            for col, trend, sort_ascending in [(better_col, "Playing better", False),
                                               (worse_col, "Playing worse", True)]:
                with col:
                    st.markdown(f"##### {trend}")
                    rows = ratings[ratings["trend"] == trend].sort_values("form_change", ascending=sort_ascending)
                    if rows.empty:
                        st.caption("No team right now.")
                    else:
                        ratings_table(rows, {"team_abbrev": "Team", **change})
            st.caption("How the model rates each team's last 10 games compared with its season as a whole.")

    with card("all_team_ratings"):
        section_label("All teams, by model rank")
        ratings_table(ratings, {
            **columns, "verdict": "Verdict", "trend": "Lately",
            "pdo": st.column_config.NumberColumn("PDO", format="%.3f",
                                                 help="Shooting % + save %. Far from 1.000 usually means luck."),
            "games_played": "GP",
        })
        model_explainer(team_model.SPEC.name, MODEL_PREDICTS, team_model.FEATURE_LABELS)


st.set_page_config(page_title="Team", page_icon="🏒", layout="wide", initial_sidebar_state="expanded")
apply_theme()
season = page_header("Team")

team = selected_team()
ratings = load_team_ratings(season)
if team is None:
    st.caption("Choose a team with the logo button in the top-right corner to see its full profile.")
    league_ratings(ratings)
    st.stop()

standings = load_standings(season)
team_standing = standings[standings["team_abbrev"] == team] if not standings.empty else standings
season_stats = load_team_season_stats(season)
team_season = season_stats[season_stats["team_abbrev"] == team] if not season_stats.empty else season_stats

if team_standing.empty:
    st.info("No standings data for this team yet -- go to Home and click 'Refresh all data'.")
    st.stop()

row = team_standing.iloc[0]

with card("team_header"):
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

team_rating = ratings[ratings["team_abbrev"] == team] if not ratings.empty else ratings
with card("model_rating"):
    section_label("Is their record for real?")
    st.caption("A machine-learning model looks at how this team has played -- its share of shots and "
               "goals, shooting and save %, special teams, and last season -- and predicts the points % "
               "it should earn from here on. Compare that with its actual points % to see whether the "
               "record looks earned, lucky, or unlucky.")
    if team_rating.empty:
        st.caption(f"Rated after {team_model.MIN_GAMES} games -- check back soon."
                   if not ratings.empty else "No model ratings yet -- go to Home and click 'Refresh all data'.")
    else:
        r = team_rating.iloc[0]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Expected PT%", f"{r['expected_points_pct']:.3f}", f"{ordinal(int(r['model_rank']))} by the model",
                  delta_color="off", delta_arrow="off",
                  help="The share of possible points the model expects this team to earn for the rest of the season.")
        m2.metric("Actual PT%", f"{r['points_pct']:.3f}", f"{ordinal(int(r['standings_rank']))} in the standings",
                  delta_color="off", delta_arrow="off",
                  help="The share of possible points they've actually earned (2 per game).")
        m3.metric("Verdict", r["verdict"])
        m4.metric("Lately", r["trend"] or "After 20 games")
        for line in explain_rating(r):
            st.markdown(line)

        history = load_team_rating_history(team, season)
        if len(history) > 1:
            fig = go.Figure()
            fig.add_scatter(x=history["games_played"], y=history["expected_points_pct"], mode="lines",
                            name="Expected PT% (model)", line=dict(color=colors()["accent"], width=2),
                            hovertemplate="Game %{x}<br>Expected %{y:.3f}<extra></extra>")
            fig.add_scatter(x=history["games_played"], y=history["points_pct"], mode="lines",
                            name="Actual PT% so far", line=dict(color=colors()["text_muted"], dash="dot", width=2),
                            hovertemplate="Game %{x}<br>Actual %{y:.3f}<extra></extra>")
            fig.update_xaxes(title="Game #")
            fig.update_yaxes(title="Points %", tickformat=".3f")
            fig.update_layout(height=320, legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
            st.plotly_chart(style_chart(fig), width="stretch")
            st.caption("How the model's view of the team changed after each game, next to its actual record.")
    model_explainer(team_model.SPEC.name, MODEL_PREDICTS, team_model.FEATURE_LABELS)

if not team_season.empty:
    with card("season_totals"):
        section_label("Season totals")
        ts = team_season.iloc[0]
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Team shots", int(ts["total_shots"]))
        t2.metric("PP goals", int(ts["total_powerplay_goals"]))
        t3.metric("Save %", f"{ts['team_save_pct']:.3f}" if ts["team_save_pct"] == ts["team_save_pct"] else "n/a")
        t4.metric("Shutouts", int(ts["total_shutouts"]))

    # Special teams: PP % and PK % over the last 10 games (big number), with a
    # green/red arrow vs the season rate, the season rate and league rank
    # (higher is better for both) below, and a rolling 10-game chart.
    # Older databases may not have these columns yet.
    if {"power_play_pct", "penalty_kill_pct"} <= set(season_stats.columns) and pd.notna(ts["power_play_pct"]):
        special_games = load_team_special_teams_games(team, season)
        # With 10 or fewer games played, "last 10" is the whole season -- nothing to compare.
        has_trend = len(special_games) > FORM_WINDOW
        with card("special_teams"):
            section_label("Special teams")
            sp1, sp2 = st.columns(2, gap="large")
            for col, label, short_label, column, successes, chances in [
                (sp1, "Power play %", "PP %", "power_play_pct",
                 special_games["pp_goals"], special_games["pp_opportunities"]),
                (sp2, "Penalty kill %", "PK %", "penalty_kill_pct",
                 special_games["times_shorthanded"] - special_games["pp_goals_against"],
                 special_games["times_shorthanded"]),
            ]:
                ranks = season_stats[column].rank(ascending=False, method="min")
                rank = int(ranks[season_stats["team_abbrev"] == team].iloc[0])
                suffix = "th" if 11 <= rank % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(rank % 10, "th")
                rank_text = f"{rank}{suffix} of {ranks.notna().sum()} in NHL"
                recent_chances = chances.tail(FORM_WINDOW).sum()
                last_10 = successes.tail(FORM_WINDOW).sum() / recent_chances if recent_chances else None
                with col, st.container(key=f"special_{column}"):
                    if has_trend and last_10 is not None:
                        change = last_10 - ts[column]
                        # One card: last 10 games (big, with the arrow vs the season) on
                        # the left, the season rate (smaller, styled in style.py) and its
                        # league rank on the right.
                        with st.container(key=f"metric_pair_{column}"):
                            recent_col, season_col = st.columns([3, 2], vertical_alignment="top")
                            with recent_col:
                                if abs(change) >= SPECIAL_TEAMS_STEADY_BAND:
                                    # A leading "-" makes Streamlit show a red down arrow; "+" a green up one.
                                    st.metric(f"{label} · last 10 games", f"{last_10:.1%}", f"{change:+.1%} vs season")
                                else:
                                    st.metric(f"{label} · last 10 games", f"{last_10:.1%}", "Steady",
                                              delta_color="off", delta_arrow="off")
                            with season_col, st.container(key=f"metric_secondary_{column}"):
                                st.metric("Season", f"{ts[column]:.1%}")
                                st.caption(rank_text)
                    else:
                        # 10 or fewer games: last 10 is the whole season, so show the season alone.
                        st.metric(label, f"{ts[column]:.1%}", "Trend after 10+ games",
                                  delta_color="off", delta_arrow="off")
                        st.caption(rank_text)
                    if not special_games.empty:
                        fig, note = special_teams_chart(special_games, successes, chances, short_label, ts[column])
                        st.plotly_chart(fig, width="stretch", key=f"chart_{column}")
                        st.caption(note)

games = load_completed_games(season, game_type=2)
team_log = build_team_game_log(games)
form = add_rolling_form_features(team_log)
team_form = form[form["team_abbrev"] == team].sort_values("game_date")

if team_form.empty:
    st.info("No game log available for this team yet.")
else:
    with card("form"):
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
            st.markdown(f"##### Win % over the last {FORM_WINDOW} games, {team}")
            fig.add_scatter(
                x=full["game_number"], y=full["form"], mode="lines+markers",
                name=f"{FORM_WINDOW}-game win %", line=dict(color=colors()["accent"], width=2),
                customdata=full[["game_date", "opponent"]].assign(
                    game_date=full["game_date"].dt.strftime("%b %d")
                ).to_numpy(),
                hovertemplate=hover,
            )
        else:
            # Too early in the season for a 10-game average -- show the
            # running season win % instead.
            st.markdown(f"##### Win % so far, {team}")
            fig.add_scatter(
                x=form_df["game_number"], y=form_df["win"].expanding().mean(), mode="lines+markers",
                name="Win % so far", line=dict(color=colors()["accent"], width=2),
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
            line=dict(color=colors()["text_muted"], dash="dot", width=1),
        )

        # Linear trend line: least-squares fit of 10-game win % against game
        # number (not date, so schedule breaks don't count as time passing).
        if len(form_df) >= MIN_GAMES_FOR_TREND:
            slope, intercept = np.polyfit(full["game_number"], full["form"], 1)
            trend = (slope * full["game_number"] + intercept).clip(0, 1)
            fig.add_scatter(
                x=full["game_number"], y=trend, mode="lines", name="Trend", hoverinfo="skip",
                line=dict(color=colors()["warning"], dash="dash", width=2),
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

    with card("last_10_games"):
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

    with card("recent_form"):
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
        with card("player_standouts"):
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
                "Season totals. For who's playing better or worse lately, see the "
                "model ratings on the Players page."
            )
