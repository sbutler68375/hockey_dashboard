"""Shared, cached data access for the dashboard.

Every dashboard page imports from here rather than calling
src.database.queries directly, so caching and the refresh pipeline stay
in one place instead of duplicated across pages.
"""

import html
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import DB_PATH
from src.database.queries import (
    get_completed_games,
    get_metadata,
    get_player_ratings,
    get_player_stats,
    get_standings,
    get_team_games,
    get_team_rating_history,
    get_team_ratings,
    get_team_season_stats,
    get_team_special_teams_games,
    get_teams,
)
from dashboard.images import nhl_logo_url, team_logo_url
from src.utils.constants import COLLECTED_SEASONS, CURRENT_SEASON, TEAM_ABBREVIATIONS

CACHE_TTL_SECONDS = 300  # data only changes when the user hits "Refresh", but
                          # cap staleness in case the app is left open for days

# Session-state key holding the season picked in the page-header season picker.
# Kept separate from the widget's own key because Streamlit drops a
# widget's state when you switch to a page that hasn't rendered it yet --
# this plain key survives page switches, so the choice sticks app-wide.
_SEASON_STATE_KEY = "selected_season"
_SEASON_WIDGET_KEY = "_season_picker"

# Same pattern for the team picked with the header's logo button.
# None means no team selected (all teams).
_TEAM_STATE_KEY = "selected_team"


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_standings(season: int) -> pd.DataFrame:
    """Latest standings snapshot within a season -- today's standings for
    the current season, final standings for a completed one."""
    return get_standings(season=season)


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_completed_games(season: int, game_type: int | None = 2) -> pd.DataFrame:
    return get_completed_games(game_type=game_type, season=season)


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_team_games(team_abbrev: str, season: int) -> pd.DataFrame:
    return get_team_games(team_abbrev, season=season)


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_player_stats(season: int, player_type: str | None = None) -> pd.DataFrame:
    return get_player_stats(season, player_type)


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_team_season_stats(season: int) -> pd.DataFrame:
    return get_team_season_stats(season)


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_team_special_teams_games(team_abbrev: str, season: int) -> pd.DataFrame:
    return get_team_special_teams_games(team_abbrev, season)


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_team_ratings(season: int) -> pd.DataFrame:
    return get_team_ratings(season)


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_team_rating_history(team_abbrev: str, season: int) -> pd.DataFrame:
    return get_team_rating_history(team_abbrev, season)


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_player_ratings(season: int) -> pd.DataFrame:
    return get_player_ratings(season)


def team_results(games: pd.DataFrame, team: str) -> pd.DataFrame:
    """One team's games from that team's point of view, newest first.

    Adds: opponent, home_away ("Home"/"Away"), outcome ("W", "L", or "OT"
    for a loss in overtime or a shootout -- the NHL's "OT loss", worth a
    point in the standings) and result, e.g. "W 3-2" (team's goals first).
    """
    games = games[(games["home_team"] == team) | (games["away_team"] == team)]
    games = games.sort_values("game_date", ascending=False).copy()
    is_home = games["home_team"] == team
    team_score = games["home_score"].where(is_home, games["away_score"]).astype(int)
    opp_score = games["away_score"].where(is_home, games["home_score"]).astype(int)
    games["opponent"] = games["away_team"].where(is_home, games["home_team"])
    games["home_away"] = is_home.map({True: "Home", False: "Away"})
    went_past_regulation = games["last_period_type"].isin(["OT", "SO"])
    outcome = (team_score > opp_score).map({True: "W", False: "L"})
    games["outcome"] = outcome.mask((outcome == "L") & went_past_regulation, "OT")
    games["result"] = games["outcome"] + " " + team_score.astype(str) + "-" + opp_score.astype(str)
    return games


def record_text(results: pd.DataFrame) -> str:
    """W-L-OT record for team_results() rows, e.g. "6-3-1"."""
    return "-".join(str(int((results["outcome"] == o).sum())) for o in ("W", "L", "OT"))


def team_list() -> list[str]:
    return sorted(TEAM_ABBREVIATIONS)


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def team_names() -> dict[str, str]:
    """{abbreviation: full team name}, e.g. {"TOR": "Toronto Maple Leafs"}."""
    try:
        teams = get_teams()
    except Exception:  # no database yet -- fall back to abbreviations
        return {}
    return dict(zip(teams["team_abbrev"], teams["team_name"]))


def team_display_name(team: str) -> str:
    return team_names().get(team, team)


def selected_team() -> str | None:
    """The team chosen with the header's logo button, or None for all teams."""
    return st.session_state.get(_TEAM_STATE_KEY)


def _select_team(team: str | None) -> None:
    st.session_state[_TEAM_STATE_KEY] = team


def _logo_label(url: str, alt: str) -> str:
    """Markdown image for a button/popover label (Streamlit renders it as an icon)."""
    return f"![{alt}]({url})"


def _team_picker() -> None:
    """The header's logo button: shows the selected team's logo (NHL logo when
    none is selected) and opens a grid of every team's logo to pick from."""
    team = selected_team()
    label = _logo_label(team_logo_url(team), team) if team else _logo_label(nhl_logo_url(), "NHL")
    with st.container(key="team_picker"):
        with st.popover(label, help="Choose a team"):
            with st.container(key="team_picker_grid"):
                st.button(
                    _logo_label(nhl_logo_url(), "NHL") + " All teams",
                    key="team_pick_all", on_click=_select_team, args=(None,),
                    type="primary" if team is None else "secondary", width="stretch",
                )
                columns = st.columns(8, gap="small")
                for i, abbrev in enumerate(team_list()):
                    with columns[i % 8]:
                        st.button(
                            _logo_label(team_logo_url(abbrev), abbrev),
                            key=f"team_pick_{abbrev}", help=team_display_name(abbrev),
                            on_click=_select_team, args=(abbrev,),
                            type="primary" if abbrev == team else "secondary", width="stretch",
                        )


def current_season() -> int:
    return int(CURRENT_SEASON)


def season_label(season: int) -> str:
    """20252026 -> '2025-26'."""
    text = str(season)
    return f"{text[:4]}-{text[6:]}"


def short_season_label(season: int) -> str:
    """20252026 -> '25/26'."""
    text = str(season)
    return f"{text[2:4]}/{text[6:]}"


def previous_season() -> int:
    """The most recent completed season -- the season picker's other option."""
    return max(int(s) for s in COLLECTED_SEASONS if int(s) != current_season())


def selected_season() -> int:
    """The season chosen in the page-header season picker (last completed season by default)."""
    return st.session_state.get(_SEASON_STATE_KEY, previous_season())


def _store_season_choice() -> None:
    st.session_state[_SEASON_STATE_KEY] = st.session_state[_SEASON_WIDGET_KEY]


def _season_option_label(season: int) -> str:
    return "Current" if season == current_season() else short_season_label(season)


def page_header(title: str, title_html: str | None = None) -> int:
    """Render a page title with the team logo button and the season picker
    (last season | Current, two labeled buttons) in the top-right corner,
    and return the selected season. Every page calls this in place of
    st.title() so the controls sit in the same spot everywhere; use
    selected_team() for the team. title_html, if given, is rendered in place
    of the plain title (the Home page's styled wordmark)."""
    st.session_state[_SEASON_WIDGET_KEY] = selected_season()

    title_col, team_col, season_col = st.columns([3, 0.35, 1], vertical_alignment="center")
    with title_col:
        st.markdown(
            title_html or f'<div class="brand"><span class="brand-word brand-word--page">'
                          f'{html.escape(title)}</span></div>',
            unsafe_allow_html=True,
        )
    with team_col:
        _team_picker()
    with season_col:
        st.segmented_control(
            "Season",
            options=[previous_season(), current_season()],
            format_func=_season_option_label,
            required=True,
            key=_SEASON_WIDGET_KEY,
            on_change=_store_season_choice,
            label_visibility="collapsed",
        )
    return selected_season()


def last_refreshed() -> datetime | None:
    """When the database was last rebuilt (stored by build_database.py, so it
    also covers refreshes run from the command line), or None if it hasn't
    been built yet. Falls back to the file's modified time for a database
    built before that was stored."""
    if not DB_PATH.exists():
        return None
    stored = get_metadata("last_refreshed")
    if stored:
        return datetime.fromisoformat(stored)
    return datetime.fromtimestamp(DB_PATH.stat().st_mtime)


def read_only() -> bool:
    """True on the hosted (public) dashboard, which hides the Refresh button:
    any visitor could click it, and what it pulled would be lost whenever the
    host restarts the app. Set SESPN_READ_ONLY=true in the host's secrets
    (Streamlit Community Cloud exposes them as environment variables). As a
    fallback, Community Cloud runs apps from /mount/src/ -- observed, not
    documented."""
    flag = os.environ.get("SESPN_READ_ONLY", "").strip().lower()
    if flag in {"1", "true", "yes"}:
        return True
    if flag in {"0", "false", "no"}:
        return False
    return PROJECT_ROOT.as_posix().startswith("/mount/src/")


def format_refresh_time(when: datetime) -> str:
    """e.g. 'Oct 13, 2026 at 5:48 PM'."""
    hour = when.hour % 12 or 12
    return f"{when:%b} {when.day}, {when.year} at {hour}:{when:%M %p}"


def refresh_all_data(progress_callback=None) -> list[str]:
    """Rerun the full pipeline: collectors -> build_database -> build_ratings
    (scores with the saved models; retraining is a separate, deliberate step --
    see scripts/build_ratings.py).

    Runs each step as a subprocess (same approach as running them
    manually from the command line) so a failure in one step is caught
    and reported without crashing the dashboard process itself.

    Args:
        progress_callback: optional callable(step_name: str) invoked
            before each step starts, for UI progress updates.

    Returns:
        List of log lines describing what happened, success or failure.
    """
    steps = [
        ("Collecting team data", "collectors/collect_teams.py"),
        ("Collecting player data", "collectors/collect_players.py"),
        ("Collecting game data", "collectors/collect_games.py"),
        ("Collecting player game logs", "collectors/collect_player_games.py"),
        ("Building database", "scripts/build_database.py"),
        ("Rating teams and players", "scripts/build_ratings.py"),
    ]
    python_exe = sys.executable
    log: list[str] = []

    for label, script in steps:
        if progress_callback:
            progress_callback(label)
        result = subprocess.run(
            [python_exe, str(PROJECT_ROOT / script)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            log.append(f"FAILED: {label}\n{result.stderr[-2000:]}")
            break
        log.append(f"OK: {label}")

    st.cache_data.clear()
    return log
